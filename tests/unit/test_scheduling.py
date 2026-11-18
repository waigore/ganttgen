"""Unit tests for scheduling."""

from __future__ import annotations

from datetime import date

from ganttgen.models import TaskRow
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


def test_actual_start_only_derives_end() -> None:
    cfg = make_config(
        schedule_mode="compress",
        project_start=date(2026, 9, 1),
        milestones={"M1": date(2026, 12, 1)},
    )
    # M design duration = 2 working days; Mon 2026-08-03 → Tue 2026-08-04
    tasks = [
        TaskRow(
            id="SP1",
            name="One",
            milestone="M1",
            size="M",
            index=0,
            actuals={"design": (date(2026, 8, 3), None)},
        )
    ]
    sch = build_schedule(tasks, cfg)
    assert sch.by_key["SP1:design"].start == date(2026, 8, 3)
    assert sch.by_key["SP1:design"].end == date(2026, 8, 4)
    assert sch.by_key["SP1:implement"].start == date(2026, 8, 5)


def test_actual_start_end_overrides_duration() -> None:
    cfg = make_config(
        schedule_mode="compress",
        project_start=date(2026, 9, 1),
        milestones={"M1": date(2026, 12, 1)},
    )
    # S design is 1d, but pin a 3-calendar-day span Mon–Wed
    tasks = [
        TaskRow(
            id="SP1",
            name="One",
            milestone="M1",
            size="S",
            index=0,
            actuals={"design": (date(2026, 8, 3), date(2026, 8, 5))},
        )
    ]
    sch = build_schedule(tasks, cfg)
    assert sch.by_key["SP1:design"].start == date(2026, 8, 3)
    assert sch.by_key["SP1:design"].end == date(2026, 8, 5)
    assert sch.by_key["SP1:implement"].start == date(2026, 8, 6)


def test_actuals_book_capacity_default_blocks_overlap() -> None:
    cfg = make_config(
        schedule_mode="compress",
        project_start=date(2026, 9, 1),
        capacities={"design": 1, "implement": 1, "test": 1},
        milestones={"M1": date(2026, 12, 1), "M2": date(2026, 12, 16)},
    )
    tasks = [
        TaskRow(
            id="M1A",
            name="M1",
            milestone="M1",
            size="S",
            index=0,
            actuals={"design": (date(2026, 9, 1), date(2026, 9, 1))},
        ),
        TaskRow(id="M2A", name="M2", milestone="M2", size="S", index=1),
    ]
    sch = build_schedule(tasks, cfg)
    # design capacity 1 + actuals_book_capacity default true → M2 waits
    assert sch.by_key["M2A:design"].start > date(2026, 9, 1)


def test_actuals_book_capacity_false_allows_overlap() -> None:
    cfg = make_config(
        schedule_mode="compress",
        project_start=date(2026, 9, 1),
        capacities={"design": 1, "implement": 1, "test": 1},
        milestones={"M1": date(2026, 12, 1)},
        actuals_book_capacity=False,
    )
    tasks = [
        TaskRow(
            id="DONE",
            name="Done",
            milestone="M1",
            size="S",
            index=0,
            actuals={
                "design": (date(2026, 9, 1), date(2026, 9, 1)),
                "implement": (date(2026, 9, 2), date(2026, 9, 2)),
                "test": (date(2026, 9, 3), date(2026, 9, 3)),
            },
        ),
        TaskRow(id="NEW", name="New", milestone="M1", size="S", index=1),
    ]
    sch = build_schedule(tasks, cfg)
    assert sch.by_key["NEW:design"].start == date(2026, 9, 1)


def test_align_with_partial_actuals() -> None:
    cfg = make_config(
        schedule_mode="align",
        project_start=None,
        milestones={"M1": date(2026, 10, 15)},
        milestone_align="implement",
    )
    tasks = [
        TaskRow(
            id="SP1",
            name="One",
            milestone="M1",
            size="S",
            index=0,
            actuals={"design": (date(2026, 8, 3), date(2026, 8, 3))},
        )
    ]
    sch = build_schedule(tasks, cfg)
    assert sch.by_key["SP1:design"].start == date(2026, 8, 3)
    assert sch.by_key["SP1:implement"].end == date(2026, 10, 15)
    assert sch.by_key["SP1:design"].end < sch.by_key["SP1:implement"].start
