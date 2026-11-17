"""Unit tests for scheduling."""

from __future__ import annotations

from datetime import date

from ganttgen.scheduling import build_schedule
from tests.conftest import make_config, make_tasks


def test_compress_starts_at_project_start() -> None:
    cfg = make_config(schedule_mode="compress", project_start=date(2026, 9, 1))
    tasks = make_tasks(("SP1", "One", "M1", "S"))
    sch = build_schedule(tasks, cfg)
    design = sch.by_key["SP1:design"]
    assert design.start == date(2026, 9, 1)  # Tuesday
    assert design.end == date(2026, 9, 1)


def test_align_pins_implement_to_milestone() -> None:
    cfg = make_config(
        schedule_mode="align",
        project_start=None,
        milestones={"M1": date(2026, 10, 15)},  # Thursday
        milestone_align="implement",
    )
    tasks = make_tasks(("SP1", "One", "M1", "S"))
    sch = build_schedule(tasks, cfg)
    assert sch.by_key["SP1:implement"].end == date(2026, 10, 15)


def test_capacity_serializes_same_phase() -> None:
    cfg = make_config(
        schedule_mode="compress",
        project_start=date(2026, 9, 1),
        capacities={"design": 1, "implement": 1, "test": 1},
        milestones={"M1": date(2026, 12, 1)},
    )
    tasks = make_tasks(
        ("A", "A", "M1", "S"),
        ("B", "B", "M1", "S"),
        ("C", "C", "M1", "S"),
    )
    sch = build_schedule(tasks, cfg)
    design_starts = sorted(sch.by_key[f"{t.id}:design"].start for t in tasks)
    # capacity 1 => design starts must be distinct working days
    assert len(set(design_starts)) == 3


def test_phase_order_within_task() -> None:
    cfg = make_config()
    tasks = make_tasks(("SP1", "One", "M1", "M"))
    sch = build_schedule(tasks, cfg)
    d, i, t = (sch.by_key[f"SP1:{p}"] for p in ("design", "implement", "test"))
    assert d.end < i.start
    assert i.end < t.start
