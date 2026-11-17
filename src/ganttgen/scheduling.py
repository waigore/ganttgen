"""Task scheduling: capacity, ASAP placement, compress and align modes."""

from __future__ import annotations

from datetime import date, timedelta

from .calendar_util import (
    add_working_days,
    is_working,
    snap_back_to_working,
    snap_forward_to_working,
    shift_working_days,
    working_day_delta,
)
from .models import PHASES, Config, Schedule, SubTask, TaskRow

Occupancy = dict[str, dict[date, int]]  # phase -> day -> count


def _make_subtasks(tasks: list[TaskRow], config: Config) -> list[SubTask]:
    out: list[SubTask] = []
    for t in tasks:
        for phase in PHASES:
            out.append(
                SubTask(
                    sp_id=t.id,
                    sp_name=t.name,
                    milestone=t.milestone,
                    phase=phase,
                    size=t.size,
                    duration=config.sizing[t.size][phase],
                )
            )
    return out


def _empty_occupancy() -> Occupancy:
    return {p: {} for p in PHASES}


def iter_working_days(start: date, end: date, config: Config):
    d = start
    while d <= end:
        if is_working(d, config):
            yield d
        d += timedelta(days=1)


def _capacity_fits(
    occupancy: Occupancy,
    phase: str,
    start: date,
    end: date,
    capacity: int,
    config: Config,
) -> bool:
    for d in iter_working_days(start, end, config):
        if occupancy[phase].get(d, 0) >= capacity:
            return False
    return True


def _capacity_book(
    occupancy: Occupancy,
    phase: str,
    start: date,
    end: date,
    config: Config,
) -> None:
    for d in iter_working_days(start, end, config):
        occupancy[phase][d] = occupancy[phase].get(d, 0) + 1


def _find_slot(
    phase: str,
    not_before: date,
    duration: int,
    occupancy: Occupancy,
    capacity: int,
    config: Config,
) -> tuple[date, date]:
    start = snap_forward_to_working(not_before, config)
    # Bound search: durations are small; avoid infinite loops on bad input.
    for _ in range(20000):
        end = add_working_days(start, duration - 1, config)
        if _capacity_fits(occupancy, phase, start, end, capacity, config):
            return start, end
        start = add_working_days(start, 1, config)
    raise SystemExit(
        f"could not place {phase} ({duration}d) under capacity {capacity} "
        f"starting from {not_before.isoformat()}"
    )


def _place_asap(
    tasks: list[TaskRow],
    config: Config,
    by_key: dict[str, SubTask],
    occupancy: Occupancy,
    earliest: date,
) -> dict[str, tuple[date, date]]:
    """Greedy CSV-order ASAP placement; books into occupancy."""
    placements: dict[str, tuple[date, date]] = {}
    for t in tasks:
        prev_phase_end: date | None = None
        for phase in PHASES:
            k = f"{t.id}:{phase}"
            dur = by_key[k].duration
            not_before = earliest
            if prev_phase_end is not None:
                after_pred = add_working_days(prev_phase_end, 1, config)
                if after_pred > not_before:
                    not_before = after_pred
            start, end = _find_slot(
                phase,
                not_before,
                dur,
                occupancy,
                config.teams[phase].capacity,
                config,
            )
            _capacity_book(occupancy, phase, start, end, config)
            placements[k] = (start, end)
            prev_phase_end = end
    return placements


def _apply_placements(
    placements: dict[str, tuple[date, date]],
    by_key: dict[str, SubTask],
    delta: int,
    config: Config,
) -> None:
    for k, (start, end) in placements.items():
        by_key[k].start = shift_working_days(start, delta, config)
        by_key[k].end = shift_working_days(end, delta, config)


def _schedule_align(
    tasks: list[TaskRow],
    config: Config,
    by_key: dict[str, SubTask],
) -> None:
    """Per-milestone capacity; ASAP pack then shift so pin hits milestone."""
    if not tasks:
        return
    ms = tasks[0].milestone
    pin_key = f"{tasks[-1].id}:{config.milestone_align}"
    pin_end = snap_back_to_working(config.milestones[ms], config)
    placements = _place_asap(tasks, config, by_key, _empty_occupancy(), pin_end)
    if pin_key not in placements:
        raise SystemExit(f"pin key missing from schedule: {pin_key}")
    delta = working_day_delta(placements[pin_key][1], pin_end, config)
    _apply_placements(placements, by_key, delta, config)
    if by_key[pin_key].end != pin_end:
        raise SystemExit(
            f"failed to align {pin_key} to {pin_end.isoformat()} "
            f"(got {by_key[pin_key].end.isoformat()})"
        )


def _schedule_compress(
    tasks: list[TaskRow],
    config: Config,
    by_key: dict[str, SubTask],
) -> None:
    """Global capacity; ready-queue ASAP from project_start across milestones."""
    assert config.project_start is not None
    project_start = snap_forward_to_working(config.project_start, config)
    csv_index = {t.id: t.index for t in tasks}
    phase_index = {p: i for i, p in enumerate(PHASES)}
    pred_phase = {"design": None, "implement": "design", "test": "implement"}

    occupancy = _empty_occupancy()
    pending = {f"{t.id}:{p}" for t in tasks for p in PHASES}
    placed: dict[str, tuple[date, date]] = {}

    while pending:
        best: tuple[date, int, int, str, date] | None = None
        for key in pending:
            st = by_key[key]
            pred = pred_phase[st.phase]
            if pred is None:
                not_before = project_start
            else:
                pred_key = f"{st.sp_id}:{pred}"
                if pred_key not in placed:
                    continue
                not_before = add_working_days(placed[pred_key][1], 1, config)
            start, end = _find_slot(
                st.phase,
                not_before,
                st.duration,
                occupancy,
                config.teams[st.phase].capacity,
                config,
            )
            cand = (start, csv_index[st.sp_id], phase_index[st.phase], key, end)
            if best is None or cand < best:
                best = cand
        if best is None:
            raise SystemExit(
                "compress schedule stuck — dependency cycle or empty task set"
            )
        start, _csv, _ph, key, end = best
        st = by_key[key]
        _capacity_book(occupancy, st.phase, start, end, config)
        placed[key] = (start, end)
        by_key[key].start = start
        by_key[key].end = end
        pending.remove(key)


def build_schedule(tasks: list[TaskRow], config: Config) -> Schedule:
    subtasks = _make_subtasks(tasks, config)
    by_key = {s.key: s for s in subtasks}

    by_ms: dict[str, list[TaskRow]] = {}
    for t in tasks:
        by_ms.setdefault(t.milestone, []).append(t)

    ms_order: list[str] = []
    for t in tasks:
        if t.milestone not in ms_order:
            ms_order.append(t.milestone)

    if config.schedule_mode == "compress":
        _schedule_compress(tasks, config, by_key)
    else:
        for ms in ms_order:
            _schedule_align(by_ms[ms], config, by_key)

    starts = [s.start for s in subtasks if s.start]
    ends = [s.end for s in subtasks if s.end]
    ends.extend(config.milestones.values())
    if not starts:
        raise SystemExit("schedule produced no dates")
    range_start = min(starts)
    range_end = max(ends)
    range_start -= timedelta(days=range_start.weekday())
    while range_start.weekday() != 0:
        range_start -= timedelta(days=1)
    return Schedule(
        subtasks=subtasks,
        by_key=by_key,
        tasks=tasks,
        config=config,
        range_start=range_start,
        range_end=range_end,
    )
