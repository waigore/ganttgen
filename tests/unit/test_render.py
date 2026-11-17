"""Unit tests for HTML rendering helpers."""

from __future__ import annotations

from datetime import date

from ganttgen.render import (
    _bar_style,
    _day_class,
    _esc,
    _holiday_name,
    _milestone_groups,
    render_html,
)
from ganttgen.models import Holiday, TaskRow
from ganttgen.scheduling import build_schedule
from tests.conftest import make_config, make_tasks


def test_esc_quotes() -> None:
    assert "&lt;" in _esc("<x>")
    assert "&quot;" in _esc('"hi"')


def test_day_class_weekend_holiday() -> None:
    cfg = make_config(
        weekends={5, 6},
        holidays=[Holiday(date=date(2026, 9, 7), name="H")],
    )
    assert "weekend" in _day_class(date(2026, 9, 5), cfg)
    assert "holiday" in _day_class(date(2026, 9, 7), cfg)
    assert _holiday_name(date(2026, 9, 7), cfg) == "H"
    assert _holiday_name(date(2026, 9, 8), cfg) == ""


def test_bar_style() -> None:
    s = _bar_style(date(2026, 9, 2), date(2026, 9, 3), date(2026, 9, 1), "#abc")
    assert "left:calc(1 * var(--day-w))" in s
    assert "width:calc(2 * var(--day-w))" in s
    assert "background:#abc" in s


def test_milestone_groups_preserves_order() -> None:
    tasks = [
        TaskRow("a", "A", "M1", "S", 0),
        TaskRow("b", "B", "M1", "S", 1),
        TaskRow("c", "C", "M2", "S", 2),
    ]
    groups = _milestone_groups(tasks)
    assert [g[0] for g in groups] == ["M1", "M2"]
    assert len(groups[0][1]) == 2


def test_render_html_contains_title_and_holiday() -> None:
    cfg = make_config(
        holidays=[Holiday(date=date(2026, 9, 7), name="Fixture Holiday")],
    )
    tasks = make_tasks(("SP1", "One", "M1", "S"))
    sch = build_schedule(tasks, cfg)
    html = render_html(sch)
    assert "Test Plan" in html
    assert "By stored procedure" in html
    assert "By team" in html
    assert "weekend" in html
