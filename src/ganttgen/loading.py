"""Load and validate config.toml and tasks.csv."""

from __future__ import annotations

import csv
import tomllib
from datetime import date
from pathlib import Path

from .models import (
    DEFAULT_CAPACITIES,
    PHASES,
    Config,
    Holiday,
    TaskRow,
    TeamStyle,
)


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

    if "allow_team_overload" in raw:
        raise SystemExit(
            "allow_team_overload was removed; use teams.*.capacity and "
            'schedule_mode ("compress" | "align") instead'
        )
    if "capacity_scope" in raw:
        raise SystemExit(
            "capacity_scope was removed; use schedule_mode "
            '("compress" | "align") instead'
        )

    mode = str(raw.get("schedule_mode", "compress")).lower()
    if mode not in {"compress", "align"}:
        raise SystemExit('schedule_mode must be "compress" or "align"')

    project_start: date | None = None
    if "project_start" in raw and raw["project_start"] is not None:
        project_start = _parse_date(raw["project_start"], "project_start")
    if mode == "compress":
        if project_start is None:
            raise SystemExit(
                'project_start is required when schedule_mode = "compress"'
            )

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
        if not isinstance(t, dict):
            raise SystemExit(f"teams.{phase} must be a table")
        cap_raw = t.get("capacity", DEFAULT_CAPACITIES[phase])
        try:
            capacity = int(cap_raw)
        except (TypeError, ValueError):
            raise SystemExit(f"teams.{phase}.capacity must be an integer >= 1") from None
        if capacity < 1:
            raise SystemExit(f"teams.{phase}.capacity must be an integer >= 1")
        teams[phase] = TeamStyle(
            key=phase,
            label=str(t.get("label", phase.title())),
            color=str(t.get("color", "#666666")),
            capacity=capacity,
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

    abc_raw = raw.get("actuals_book_capacity", True)
    if not isinstance(abc_raw, bool):
        raise SystemExit("actuals_book_capacity must be true or false")

    return Config(
        title=str(raw.get("title", "Delivery Plan")),
        milestone_align=align,
        schedule_mode=mode,
        project_start=project_start,
        weekends=weekends,
        milestones=milestones,
        sizing=sizing,
        teams=teams,
        holidays=holidays,
        actuals_book_capacity=abc_raw,
    )


def _parse_actuals(norm: dict[str, str], row_num: int) -> dict[str, tuple[date, date | None]]:
    """Parse optional per-phase actual dates; enforce left-to-right prefix."""
    actuals: dict[str, tuple[date, date | None]] = {}
    for phase in PHASES:
        start_raw = norm.get(f"{phase}_start", "")
        end_raw = norm.get(f"{phase}_end", "")
        if end_raw and not start_raw:
            raise SystemExit(
                f"tasks CSV row {row_num}: {phase}_end without {phase}_start"
            )
        if not start_raw:
            continue
        try:
            start = date.fromisoformat(start_raw)
        except ValueError as exc:
            raise SystemExit(
                f"tasks CSV row {row_num}: invalid {phase}_start {start_raw!r}"
            ) from exc
        end: date | None = None
        if end_raw:
            try:
                end = date.fromisoformat(end_raw)
            except ValueError as exc:
                raise SystemExit(
                    f"tasks CSV row {row_num}: invalid {phase}_end {end_raw!r}"
                ) from exc
            if end < start:
                raise SystemExit(
                    f"tasks CSV row {row_num}: {phase}_end before {phase}_start"
                )
        actuals[phase] = (start, end)

    # Actuals must be a contiguous left-to-right prefix of PHASES.
    seen_gap = False
    for phase in PHASES:
        if phase in actuals:
            if seen_gap:
                raise SystemExit(
                    f"tasks CSV row {row_num}: actuals must be filled left-to-right "
                    f"(got {phase} without earlier phase)"
                )
        else:
            seen_gap = True
    return actuals


def load_tasks(path: Path, config: Config) -> list[TaskRow]:
    if not path.is_file():
        raise SystemExit(f"Tasks CSV not found: {path}")
    required = {"id", "name", "milestone", "size"}
    tasks: list[TaskRow] = []
    # utf-8-sig strips a leading BOM so Excel-exported CSVs still match headers.
    with path.open(newline="", encoding="utf-8-sig") as fh:
        reader = csv.DictReader(fh)
        if reader.fieldnames is None:
            raise SystemExit("tasks CSV is empty")
        fields = {f.strip().lower() for f in reader.fieldnames}
        missing = required - fields
        if missing:
            raise SystemExit(f"tasks CSV missing columns: {', '.join(sorted(missing))}")
        for i, row in enumerate(reader):
            norm = {
                k.strip().lower(): (v or "").strip()
                for k, v in row.items()
                if k is not None
            }
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
            actuals = _parse_actuals(norm, i + 2)
            tasks.append(
                TaskRow(
                    id=tid,
                    name=name,
                    milestone=milestone,
                    size=size,
                    index=i,
                    actuals=actuals,
                )
            )
    if not tasks:
        raise SystemExit("tasks CSV has no data rows")
    by_id: dict[str, list[int]] = {}
    for t in tasks:
        # CSV line number: header is line 1, first data row is line 2 → index + 2
        by_id.setdefault(t.id, []).append(t.index + 2)
    dups = {tid: lines for tid, lines in by_id.items() if len(lines) > 1}
    if dups:
        detail = "; ".join(
            f"{tid} on lines {', '.join(str(n) for n in lines)}"
            for tid, lines in sorted(dups.items())
        )
        raise SystemExit(f"tasks CSV contains duplicate id values: {detail}")
    return tasks
