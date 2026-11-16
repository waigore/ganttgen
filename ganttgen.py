#!/usr/bin/env python3
"""Pure-stdlib Gantt chart generator for SP/program delivery plans.

Requires Python 3.14+. No third-party packages.
"""

from __future__ import annotations

import argparse
import csv
import html
import sys
import tomllib
from dataclasses import dataclass, field
from datetime import date, timedelta
from pathlib import Path

PHASES = ("design", "implement", "test")
DEFAULT_TASKS = Path("tasks.csv")
DEFAULT_CONFIG = Path("config.toml")
DEFAULT_OUT = Path("gantt.html")

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Holiday:
    date: date
    name: str


@dataclass(frozen=True)
class TeamStyle:
    key: str
    label: str
    color: str


@dataclass(frozen=True)
class TaskRow:
    id: str
    name: str
    milestone: str
    size: str
    index: int  # CSV order


@dataclass
class Config:
    title: str
    milestone_align: str
    allow_team_overload: bool
    weekends: set[int]
    milestones: dict[str, date]
    sizing: dict[str, dict[str, int]]
    teams: dict[str, TeamStyle]
    holidays: list[Holiday]
    holiday_dates: set[date] = field(default_factory=set)

    def __post_init__(self) -> None:
        self.holiday_dates = {h.date for h in self.holidays}


@dataclass
class SubTask:
    sp_id: str
    sp_name: str
    milestone: str
    phase: str
    size: str
    duration: int
    start: date | None = None
    end: date | None = None

    @property
    def key(self) -> str:
        return f"{self.sp_id}:{self.phase}"


@dataclass
class Schedule:
    subtasks: list[SubTask]
    by_key: dict[str, SubTask]
    tasks: list[TaskRow]
    config: Config
    range_start: date
    range_end: date


# ---------------------------------------------------------------------------
# Loading
# ---------------------------------------------------------------------------


def _parse_date(value: object, label: str) -> date:
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        return date.fromisoformat(value)
    raise SystemExit(f"Invalid date for {label}: {value!r}")


def load_config(path: Path) -> Config:
    if not path.is_file():
        raise SystemExit(f"Config not found: {path}")
    with path.open("rb") as fh:
        raw = tomllib.load(fh)

    align = str(raw.get("milestone_align", "implement")).lower()
    if align not in {"implement", "test"}:
        raise SystemExit('milestone_align must be "implement" or "test"')

    weekends = {int(d) for d in raw.get("weekends", [5, 6])}
    if any(d < 0 or d > 6 for d in weekends):
        raise SystemExit("weekends entries must be 0 (Mon) … 6 (Sun)")

    milestones_raw = raw.get("milestones") or {}
    if not milestones_raw:
        raise SystemExit("config.milestones is required")
    milestones = {
        str(k): _parse_date(v, f"milestones.{k}") for k, v in milestones_raw.items()
    }

    sizing_raw = raw.get("sizing") or {}
    sizing: dict[str, dict[str, int]] = {}
    for size, phases in sizing_raw.items():
        if not isinstance(phases, dict):
            raise SystemExit(f"sizing.{size} must be a table")
        entry = {str(p): int(phases[p]) for p in PHASES if p in phases}
        for p in PHASES:
            if p not in entry or entry[p] < 1:
                raise SystemExit(f"sizing.{size}.{p} must be an integer >= 1")
        sizing[str(size).upper()] = entry
    if not sizing:
        raise SystemExit("config.sizing is required")

    teams_raw = raw.get("teams") or {}
    teams: dict[str, TeamStyle] = {}
    for phase in PHASES:
        t = teams_raw.get(phase) or {}
        teams[phase] = TeamStyle(
            key=phase,
            label=str(t.get("label", phase.title())),
            color=str(t.get("color", "#666666")),
        )

    holidays: list[Holiday] = []
    for item in raw.get("holidays") or []:
        if not isinstance(item, dict) or "date" not in item:
            raise SystemExit("each [[holidays]] entry needs a date")
        holidays.append(
            Holiday(
                date=_parse_date(item["date"], "holiday"),
                name=str(item.get("name", "Holiday")),
            )
        )
    holidays.sort(key=lambda h: h.date)

    return Config(
        title=str(raw.get("title", "Delivery Plan")),
        milestone_align=align,
        allow_team_overload=bool(raw.get("allow_team_overload", False)),
        weekends=weekends,
        milestones=milestones,
        sizing=sizing,
        teams=teams,
        holidays=holidays,
    )


def load_tasks(path: Path, config: Config) -> list[TaskRow]:
    if not path.is_file():
        raise SystemExit(f"Tasks CSV not found: {path}")
    required = {"id", "name", "milestone", "size"}
    tasks: list[TaskRow] = []
    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise SystemExit("tasks CSV is empty")
        fields = {f.strip().lower() for f in reader.fieldnames}
        missing = required - fields
        if missing:
            raise SystemExit(f"tasks CSV missing columns: {', '.join(sorted(missing))}")
        for i, row in enumerate(reader):
            norm = {k.strip().lower(): (v or "").strip() for k, v in row.items()}
            tid = norm["id"]
            name = norm["name"]
            milestone = norm["milestone"]
            size = norm["size"].upper()
            if not tid or not name or not milestone or not size:
                raise SystemExit(f"tasks CSV row {i + 2}: blank required field")
            if milestone not in config.milestones:
                raise SystemExit(
                    f"tasks CSV row {i + 2}: unknown milestone {milestone!r}"
                )
            if size not in config.sizing:
                raise SystemExit(f"tasks CSV row {i + 2}: unknown size {size!r}")
            tasks.append(
                TaskRow(id=tid, name=name, milestone=milestone, size=size, index=i)
            )
    if not tasks:
        raise SystemExit("tasks CSV has no data rows")
    ids = [t.id for t in tasks]
    if len(ids) != len(set(ids)):
        raise SystemExit("tasks CSV contains duplicate id values")
    return tasks


# ---------------------------------------------------------------------------
# Calendar
# ---------------------------------------------------------------------------


def is_working(d: date, config: Config) -> bool:
    return d.weekday() not in config.weekends and d not in config.holiday_dates


def snap_back_to_working(d: date, config: Config) -> date:
    while not is_working(d, config):
        d -= timedelta(days=1)
    return d


def prev_working(d: date, config: Config) -> date:
    d -= timedelta(days=1)
    return snap_back_to_working(d, config)


def add_working_days(start: date, n: int, config: Config) -> date:
    """Return the date n working days after start (n >= 0). n=0 => start."""
    if n < 0:
        raise ValueError("n must be >= 0")
    d = start
    stepped = 0
    while stepped < n:
        d += timedelta(days=1)
        if is_working(d, config):
            stepped += 1
    return d


def span_ending_on(end: date, duration: int, config: Config) -> tuple[date, date]:
    """Working-day span of `duration` days ending on `end` (must be working)."""
    if duration < 1:
        raise ValueError("duration must be >= 1")
    end = snap_back_to_working(end, config)
    start = end
    remaining = duration - 1
    while remaining > 0:
        start -= timedelta(days=1)
        if is_working(start, config):
            remaining -= 1
    return start, end


def iter_days(start: date, end: date):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


# ---------------------------------------------------------------------------
# Scheduling
# ---------------------------------------------------------------------------


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


def _successors_pipeline(tasks: list[TaskRow]) -> dict[str, list[str]]:
    """Finish-to-start edges for mode A (no overload)."""
    succ: dict[str, list[str]] = {}

    def link(a: str, b: str) -> None:
        succ.setdefault(a, []).append(b)

    for t in tasks:
        link(f"{t.id}:design", f"{t.id}:implement")
        link(f"{t.id}:implement", f"{t.id}:test")
    for a, b in zip(tasks, tasks[1:]):
        for phase in PHASES:
            link(f"{a.id}:{phase}", f"{b.id}:{phase}")
    return succ


def _successors_independent(tasks: list[TaskRow]) -> dict[str, list[str]]:
    """Finish-to-start edges for mode B (overload allowed)."""
    succ: dict[str, list[str]] = {}
    for t in tasks:
        succ.setdefault(f"{t.id}:design", []).append(f"{t.id}:implement")
        succ.setdefault(f"{t.id}:implement", []).append(f"{t.id}:test")
    return succ


def _topo_reverse(keys: list[str], succ: dict[str, list[str]]) -> list[str]:
    """Reverse topological order (sinks first)."""
    indeg = {k: 0 for k in keys}
    for u in keys:
        for v in succ.get(u, []):
            if v in indeg:
                indeg[v] += 1
    # Kahn forward, then reverse
    queue = [k for k, d in indeg.items() if d == 0]
    order: list[str] = []
    pending = dict(indeg)
    head = 0
    while head < len(queue):
        u = queue[head]
        head += 1
        order.append(u)
        for v in succ.get(u, []):
            if v not in pending:
                continue
            pending[v] -= 1
            if pending[v] == 0:
                queue.append(v)
    if len(order) != len(keys):
        raise SystemExit("dependency cycle detected in schedule graph")
    order.reverse()
    return order


def _schedule_milestone(
    tasks: list[TaskRow],
    config: Config,
    by_key: dict[str, SubTask],
) -> None:
    if not tasks:
        return
    ms = tasks[0].milestone
    milestone_date = config.milestones[ms]
    pin_phase = config.milestone_align
    pin_key = f"{tasks[-1].id}:{pin_phase}"

    if config.allow_team_overload:
        succ = _successors_independent(tasks)
    else:
        succ = _successors_pipeline(tasks)

    keys = [f"{t.id}:{p}" for t in tasks for p in PHASES]
    # Latest finish / latest start
    lf: dict[str, date] = {}
    ls: dict[str, date] = {}

    pin_end = snap_back_to_working(milestone_date, config)
    lf[pin_key] = pin_end
    start, end = span_ending_on(pin_end, by_key[pin_key].duration, config)
    ls[pin_key] = start
    assert end == pin_end

    for key in _topo_reverse(keys, succ):
        if key == pin_key:
            continue
        successors = [s for s in succ.get(key, []) if s in ls]
        if not successors and key not in lf:
            # Floating sink (e.g. test when align=implement on last SP only,
            # or unused). Schedule immediately after its predecessor later.
            continue
        if successors:
            # Must finish the working day before the earliest successor start.
            candidate_end = min(prev_working(ls[s], config) for s in successors)
            if key in lf:
                lf[key] = min(lf[key], candidate_end)
            else:
                lf[key] = candidate_end
        if key not in lf:
            continue
        st, en = span_ending_on(lf[key], by_key[key].duration, config)
        ls[key] = st
        lf[key] = en

    # Forward-fill any remaining (e.g. test after implement pin on last SP,
    # and any earlier tests already constrained). For overload mode each SP
    # is independent — pin every SP's align phase to the milestone.
    if config.allow_team_overload:
        for t in tasks:
            pk = f"{t.id}:{pin_phase}"
            if pk not in ls:
                st, en = span_ending_on(pin_end, by_key[pk].duration, config)
                ls[pk] = st
                lf[pk] = en
            # design / other phases via reverse from implement/test chain
            for phase in reversed(PHASES):
                k = f"{t.id}:{phase}"
                if k in ls:
                    continue
                # find successor within SP
                if phase == "design":
                    succ_k = f"{t.id}:implement"
                elif phase == "implement":
                    succ_k = f"{t.id}:test"
                else:
                    # test with no lf: starts day after implement ends
                    pred = f"{t.id}:implement"
                    if pred not in lf:
                        raise SystemExit(f"cannot schedule {k}")
                    st = add_working_days(lf[pred], 1, config)
                    en = add_working_days(st, by_key[k].duration - 1, config)
                    ls[k] = st
                    lf[k] = en
                    continue
                if succ_k not in ls:
                    raise SystemExit(f"cannot schedule {k}: missing {succ_k}")
                end = prev_working(ls[succ_k], config)
                st, en = span_ending_on(end, by_key[k].duration, config)
                ls[k] = st
                lf[k] = en

    # Pipeline mode: tests after an implement pin still need dates.
    # Any key still missing: if it has a direct predecessor finished, place after.
    missing = [k for k in keys if k not in ls]
    # Iterate until stable (short chains).
    for _ in range(len(keys) + 1):
        progress = False
        still = []
        for k in missing:
            stask = by_key[k]
            phase = stask.phase
            # Prefer predecessor within SP
            pred = None
            if phase == "implement":
                pred = f"{stask.sp_id}:design"
            elif phase == "test":
                pred = f"{stask.sp_id}:implement"
            # Same-team previous SP
            team_pred = None
            idx = next(i for i, t in enumerate(tasks) if t.id == stask.sp_id)
            if idx > 0:
                team_pred = f"{tasks[idx - 1].id}:{phase}"

            pred_end_candidates: list[date] = []
            if pred and pred in lf:
                pred_end_candidates.append(lf[pred])
            if team_pred and team_pred in lf and not config.allow_team_overload:
                pred_end_candidates.append(lf[team_pred])

            # Also constrained by successors already placed
            succ_starts = [ls[s] for s in succ.get(k, []) if s in ls]
            if succ_starts:
                end = min(prev_working(s, config) for s in succ_starts)
                st, en = span_ending_on(end, stask.duration, config)
                # Ensure after predecessors
                if pred_end_candidates:
                    earliest_start = add_working_days(
                        max(pred_end_candidates), 1, config
                    )
                    if st < earliest_start:
                        st = earliest_start
                        en = add_working_days(st, stask.duration - 1, config)
                ls[k] = st
                lf[k] = en
                progress = True
            elif pred_end_candidates:
                st = add_working_days(max(pred_end_candidates), 1, config)
                en = add_working_days(st, stask.duration - 1, config)
                ls[k] = st
                lf[k] = en
                progress = True
            else:
                still.append(k)
        missing = [k for k in still if k not in ls]
        if not progress:
            break

    if missing:
        raise SystemExit(
            f"could not schedule subtasks for milestone {ms}: {', '.join(missing)}"
        )

    for k in keys:
        by_key[k].start = ls[k]
        by_key[k].end = lf[k]


def build_schedule(tasks: list[TaskRow], config: Config) -> Schedule:
    subtasks = _make_subtasks(tasks, config)
    by_key = {s.key: s for s in subtasks}

    by_ms: dict[str, list[TaskRow]] = {}
    for t in tasks:
        by_ms.setdefault(t.milestone, []).append(t)

    # Preserve milestone order as first appearance in CSV
    ms_order: list[str] = []
    for t in tasks:
        if t.milestone not in ms_order:
            ms_order.append(t.milestone)

    for ms in ms_order:
        _schedule_milestone(by_ms[ms], config, by_key)

    starts = [s.start for s in subtasks if s.start]
    ends = [s.end for s in subtasks if s.end]
    ends.extend(config.milestones.values())
    if not starts:
        raise SystemExit("schedule produced no dates")
    range_start = min(starts)
    range_end = max(ends)
    # pad a few calendar days for chart margins
    range_start -= timedelta(days=range_start.weekday())  # back to week start-ish
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


# ---------------------------------------------------------------------------
# HTML
# ---------------------------------------------------------------------------


def _esc(s: str) -> str:
    return html.escape(s, quote=True)


def _day_class(d: date, config: Config) -> str:
    classes = ["day"]
    if d.weekday() in config.weekends:
        classes.append("weekend")
    if d in config.holiday_dates:
        classes.append("holiday")
    return " ".join(classes)


def _holiday_name(d: date, config: Config) -> str:
    for h in config.holidays:
        if h.date == d:
            return h.name
    return ""


def _bar_style(start: date, end: date, range_start: date, color: str) -> str:
    left = (start - range_start).days
    width = (end - start).days + 1
    return (
        f"left:calc({left} * var(--day-w));"
        f"width:calc({width} * var(--day-w));"
        f"background:{color};"
    )


def _milestone_groups(tasks: list[TaskRow]) -> list[tuple[str, list[TaskRow]]]:
    groups: list[tuple[str, list[TaskRow]]] = []
    for t in tasks:
        if not groups or groups[-1][0] != t.milestone:
            groups.append((t.milestone, [t]))
        else:
            groups[-1][1].append(t)
    return groups


def render_html(schedule: Schedule) -> str:
    cfg = schedule.config
    days = list(iter_days(schedule.range_start, schedule.range_end))
    day_count = len(days)
    holiday_map = {h.date: h.name for h in cfg.holidays}

    # Month header spans
    months: list[tuple[str, int]] = []
    for d in days:
        label = d.strftime("%b %Y")
        if not months or months[-1][0] != label:
            months.append((label, 1))
        else:
            months[-1] = (label, months[-1][1] + 1)

    align_note = (
        "Milestone marker aligns to <strong>Implement</strong> end; "
        "Test may run after the marker."
        if cfg.milestone_align == "implement"
        else "Milestone marker aligns to <strong>Test</strong> end."
    )
    mode_note = (
        "Team overload allowed — SPs scheduled independently."
        if cfg.allow_team_overload
        else "Per-team pipeline — no same-team overlap."
    )

    css = f"""
:root {{
  --ink: #1c1916;
  --muted: #6b645c;
  --paper: #f4f0e8;
  --panel: #faf8f4;
  --rule: #d4cdc2;
  --weekend: #ebe4d8;
  --holiday: #f0d8d0;
  --milestone: #9b2c2c;
  --day-w: 22px;
  --label-w: 220px;
  --row-h: 34px;
  --bar-h: 22px;
  --font-display: "Iowan Old Style", "Palatino Linotype", Palatino, "Book Antiqua", Georgia, serif;
  --font-ui: "Avenir Next", "Segoe UI", "Helvetica Neue", sans-serif;
  --font-mono: "SF Mono", Menlo, Consolas, monospace;
}}
* {{ box-sizing: border-box; }}
html {{ font-size: 14px; }}
body {{
  margin: 0;
  padding: 2rem 1.5rem 3rem;
  background:
    radial-gradient(ellipse 80% 50% at 10% -10%, #e8e0d2 0%, transparent 55%),
    radial-gradient(ellipse 60% 40% at 100% 0%, #ddd5c8 0%, transparent 50%),
    var(--paper);
  color: var(--ink);
  font-family: var(--font-ui);
  line-height: 1.45;
}}
header.page {{
  max-width: 100%;
  margin: 0 0 1.75rem;
  padding-bottom: 1rem;
  border-bottom: 2px solid var(--ink);
}}
header.page h1 {{
  margin: 0 0 0.35rem;
  font-family: var(--font-display);
  font-weight: 600;
  font-size: 2rem;
  letter-spacing: -0.02em;
}}
header.page .meta {{
  color: var(--muted);
  font-size: 0.92rem;
  max-width: 62rem;
}}
header.page .meta strong {{ color: var(--ink); font-weight: 600; }}
.legend {{
  display: flex;
  flex-wrap: wrap;
  gap: 1rem 1.5rem;
  margin: 1rem 0 0;
  padding: 0;
  list-style: none;
  font-size: 0.85rem;
}}
.legend li {{ display: flex; align-items: center; gap: 0.45rem; }}
.swatch {{
  width: 0.85rem; height: 0.85rem; border-radius: 2px;
  display: inline-block;
}}
.swatch.weekend {{ background: var(--weekend); border: 1px solid var(--rule); }}
.swatch.holiday {{ background: var(--holiday); border: 1px solid var(--rule); }}
.swatch.milestone {{ background: var(--milestone); }}
section.view {{
  margin: 2.25rem 0 0;
}}
section.view h2 {{
  margin: 0 0 0.75rem;
  font-family: var(--font-display);
  font-size: 1.35rem;
  font-weight: 600;
}}
.chart-shell {{
  overflow-x: auto;
  border: 1px solid var(--rule);
  background: var(--panel);
  box-shadow: 0 1px 0 rgba(28,25,22,0.04);
}}
.chart {{
  --cols: {day_count};
  position: relative;
  min-width: calc(var(--label-w) + var(--cols) * var(--day-w));
}}
.head, .row, .ms-banner {{
  display: grid;
  grid-template-columns: var(--label-w) 1fr;
  border-bottom: 1px solid var(--rule);
}}
.ms-banner {{
  background: #e8e2d6;
  font-size: 0.78rem;
  font-weight: 600;
  letter-spacing: 0.04em;
  text-transform: uppercase;
}}
.ms-banner .label {{
  padding: 0.4rem 0.75rem;
  border-right: 1px solid var(--rule);
}}
.ms-banner .track {{
  position: relative;
  min-height: 1.6rem;
}}
.head {{
  position: sticky;
  top: 0;
  z-index: 3;
  background: #efe9dd;
  font-size: 0.68rem;
}}
.head .label {{
  padding: 0.5rem 0.75rem;
  border-right: 1px solid var(--rule);
  display: flex;
  align-items: flex-end;
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.05em;
  color: var(--muted);
}}
.timeline {{
  position: relative;
  display: flex;
  flex-direction: column;
}}
.months, .dates {{
  display: grid;
  grid-template-columns: repeat(var(--cols), var(--day-w));
}}
.months span {{
  border-right: 1px solid var(--rule);
  padding: 0.35rem 0.25rem 0.15rem;
  font-weight: 600;
  color: var(--ink);
  white-space: nowrap;
  overflow: hidden;
}}
.dates span {{
  border-right: 1px solid var(--rule);
  text-align: center;
  padding: 0.15rem 0 0.35rem;
  color: var(--muted);
  font-family: var(--font-mono);
  font-size: 0.62rem;
}}
.dates span.weekend {{ background: var(--weekend); }}
.dates span.holiday {{ background: var(--holiday); color: var(--ink); }}
.row .label {{
  padding: 0.35rem 0.75rem;
  border-right: 1px solid var(--rule);
  display: flex;
  flex-direction: column;
  justify-content: center;
  min-height: var(--row-h);
  background: var(--panel);
  position: sticky;
  left: 0;
  z-index: 2;
}}
.row .label .id {{
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 600;
}}
.row .label .name {{
  font-size: 0.72rem;
  color: var(--muted);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}}
.row.team-row .label .id {{ font-family: var(--font-ui); font-size: 0.8rem; }}
.track {{
  position: relative;
  min-height: var(--row-h);
  display: grid;
  grid-template-columns: repeat(var(--cols), var(--day-w));
}}
.track .cell {{
  border-right: 1px solid color-mix(in srgb, var(--rule) 70%, transparent);
}}
.track .cell.weekend {{ background: var(--weekend); }}
.track .cell.holiday {{ background: var(--holiday); }}
.bar {{
  position: absolute;
  top: calc((var(--row-h) - var(--bar-h)) / 2);
  height: var(--bar-h);
  border-radius: 2px;
  color: #fff;
  font-family: var(--font-mono);
  font-size: 0.62rem;
  font-weight: 600;
  letter-spacing: 0.02em;
  display: flex;
  align-items: center;
  padding: 0 0.35rem;
  white-space: nowrap;
  overflow: hidden;
  box-shadow: inset 0 0 0 1px rgba(0,0,0,0.12);
  z-index: 1;
}}
.bar.seg-design {{ opacity: 0.95; }}
.milestone-line {{
  position: absolute;
  top: 0;
  bottom: 0;
  width: 2px;
  background: var(--milestone);
  z-index: 2;
  pointer-events: none;
}}
.milestone-line::after {{
  content: attr(data-label);
  position: absolute;
  top: 0.15rem;
  left: 4px;
  color: var(--milestone);
  font-size: 0.62rem;
  font-weight: 700;
  letter-spacing: 0.03em;
  white-space: nowrap;
  background: color-mix(in srgb, var(--panel) 85%, transparent);
  padding: 0 0.2rem;
}}
.footnote {{
  margin: 0.6rem 0 0;
  font-size: 0.78rem;
  color: var(--muted);
}}
@media print {{
  body {{ background: white; padding: 0.5cm; }}
  .chart-shell {{ overflow: visible; box-shadow: none; }}
}}
"""

    def milestone_lines(scoped_ms: set[str] | None = None) -> str:
        parts: list[str] = []
        for ms, md in cfg.milestones.items():
            if scoped_ms is not None and ms not in scoped_ms:
                continue
            if md < schedule.range_start or md > schedule.range_end:
                continue
            # line at the end of the milestone day column
            offset = (md - schedule.range_start).days
            left = f"calc({offset} * var(--day-w) + var(--day-w) - 1px)"
            label = f"{ms} {md.isoformat()}"
            parts.append(
                f'<div class="milestone-line" style="left:{left}" '
                f'data-label="{_esc(label)}"></div>'
            )
        return "".join(parts)

    def timeline_head(label: str) -> str:
        month_cells = "".join(
            f'<span style="grid-column:span {span}">{_esc(name)}</span>'
            for name, span in months
        )
        date_cells = []
        for d in days:
            title = holiday_map.get(d, "")
            title_attr = f' title="{_esc(title)}"' if title else ""
            date_cells.append(
                f'<span class="{_day_class(d, cfg)}"{title_attr}>{d.day}</span>'
            )
        return f"""
<div class="head">
  <div class="label">{_esc(label)}</div>
  <div class="timeline">
    <div class="months">{month_cells}</div>
    <div class="dates">{"".join(date_cells)}</div>
  </div>
</div>"""

    def track_cells() -> str:
        return "".join(
            f'<div class="cell {_day_class(d, cfg)}"></div>' for d in days
        )

    # ---- View 1: by SP ----
    sp_rows: list[str] = [timeline_head("SP / Program")]
    for ms, group in _milestone_groups(schedule.tasks):
        md = cfg.milestones[ms]
        sp_rows.append(
            f'<div class="ms-banner"><div class="label">{_esc(ms)} · '
            f'{md.isoformat()}</div><div class="track">'
            f"{milestone_lines({ms})}</div></div>"
        )
        for t in group:
            bars = []
            for phase in PHASES:
                st = schedule.by_key[f"{t.id}:{phase}"]
                assert st.start and st.end
                color = cfg.teams[phase].color
                short = phase[:1].upper()
                bars.append(
                    f'<div class="bar seg-{phase}" style="'
                    f'{_bar_style(st.start, st.end, schedule.range_start, color)}" '
                    f'title="{_esc(t.id)} {_esc(phase)} '
                    f'{st.start.isoformat()} → {st.end.isoformat()} '
                    f'({st.duration}d)">{_esc(short)}</div>'
                )
            sp_rows.append(
                f'<div class="row"><div class="label">'
                f'<span class="id">{_esc(t.id)}</span>'
                f'<span class="name">{_esc(t.name)} · {t.size}</span>'
                f"</div><div class=\"track\">{track_cells()}"
                f"{''.join(bars)}{milestone_lines({ms})}</div></div>"
            )

    # ---- View 2: by team ----
    team_rows: list[str] = [timeline_head("Team")]
    all_ms = set(cfg.milestones)
    for phase in PHASES:
        team = cfg.teams[phase]
        bars = []
        for t in schedule.tasks:
            st = schedule.by_key[f"{t.id}:{phase}"]
            assert st.start and st.end
            bars.append(
                f'<div class="bar" style="'
                f'{_bar_style(st.start, st.end, schedule.range_start, team.color)}" '
                f'title="{_esc(t.id)} {_esc(phase)} '
                f'{st.start.isoformat()} → {st.end.isoformat()}">{_esc(t.id)}</div>'
            )
        team_rows.append(
            f'<div class="row team-row"><div class="label">'
            f'<span class="id">{_esc(team.label)}</span>'
            f'<span class="name">{_esc(phase)}</span>'
            f"</div><div class=\"track\">{track_cells()}"
            f"{''.join(bars)}{milestone_lines(all_ms)}</div></div>"
        )

    legend_teams = "".join(
        f'<li><span class="swatch" style="background:{_esc(cfg.teams[p].color)}"></span>'
        f"{_esc(cfg.teams[p].label)}</li>"
        for p in PHASES
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(cfg.title)}</title>
<style>{css}</style>
</head>
<body>
<header class="page">
  <h1>{_esc(cfg.title)}</h1>
  <p class="meta">{align_note} {mode_note}
  Range {schedule.range_start.isoformat()} → {schedule.range_end.isoformat()}.</p>
  <ul class="legend">
    {legend_teams}
    <li><span class="swatch weekend"></span>Weekend</li>
    <li><span class="swatch holiday"></span>Public holiday</li>
    <li><span class="swatch milestone"></span>Milestone</li>
  </ul>
</header>

<section class="view">
  <h2>By stored procedure / program</h2>
  <div class="chart-shell"><div class="chart">
    {"".join(sp_rows)}
  </div></div>
  <p class="footnote">Row order follows the CSV. Segments are Design → Implement → Test.</p>
</section>

<section class="view">
  <h2>By team</h2>
  <div class="chart-shell"><div class="chart">
    {"".join(team_rows)}
  </div></div>
  <p class="footnote">Overlapping bars on a team row indicate overload.</p>
</section>
</body>
</html>
"""


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Generate a standalone HTML Gantt chart from tasks.csv + config.toml."
    )
    p.add_argument(
        "--tasks",
        type=Path,
        default=DEFAULT_TASKS,
        help=f"tasks CSV (default: {DEFAULT_TASKS})",
    )
    p.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help=f"TOML config (default: {DEFAULT_CONFIG})",
    )
    p.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_OUT,
        help=f"output HTML path (default: {DEFAULT_OUT})",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    if sys.version_info < (3, 14):
        print(
            f"Python 3.14+ required (running {sys.version.split()[0]})",
            file=sys.stderr,
        )
        return 1
    args = parse_args(argv)
    config = load_config(args.config)
    tasks = load_tasks(args.tasks, config)
    schedule = build_schedule(tasks, config)
    html_text = render_html(schedule)
    args.out.write_text(html_text, encoding="utf-8")
    print(f"Wrote {args.out} ({len(schedule.subtasks)} subtasks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
