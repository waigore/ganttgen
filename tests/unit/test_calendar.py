"""Unit tests for calendar_util."""

from __future__ import annotations

from datetime import date

import pytest

from ganttgen.calendar_util import (
    add_working_days,
    is_working,
    iter_days,
    shift_working_days,
    snap_back_to_working,
    snap_forward_to_working,
    working_day_delta,
)
from ganttgen.models import Holiday
from tests.conftest import make_config


def test_is_working_skips_weekend_and_holiday() -> None:
    cfg = make_config(
        weekends={5, 6},
        holidays=[Holiday(date=date(2026, 9, 7), name="H")],  # Monday
    )
    assert is_working(date(2026, 9, 4), cfg)  # Friday
    assert not is_working(date(2026, 9, 5), cfg)  # Saturday
    assert not is_working(date(2026, 9, 7), cfg)  # holiday


def test_snap_forward_and_back() -> None:
    cfg = make_config(weekends={5, 6})
    assert snap_forward_to_working(date(2026, 9, 5), cfg) == date(2026, 9, 7)
    assert snap_back_to_working(date(2026, 9, 6), cfg) == date(2026, 9, 4)


def test_add_and_shift_working_days() -> None:
    cfg = make_config(weekends={5, 6})
    start = date(2026, 9, 4)  # Friday
    assert add_working_days(start, 0, cfg) == start
    assert add_working_days(start, 1, cfg) == date(2026, 9, 7)  # Monday
    assert shift_working_days(date(2026, 9, 7), -1, cfg) == start
    assert shift_working_days(start, 0, cfg) == start
    with pytest.raises(ValueError):
        add_working_days(start, -1, cfg)


def test_working_day_delta_symmetric() -> None:
    cfg = make_config(weekends={5, 6})
    a, b = date(2026, 9, 4), date(2026, 9, 8)
    assert working_day_delta(a, b, cfg) == 2
    assert working_day_delta(b, a, cfg) == -2
    assert working_day_delta(a, a, cfg) == 0


def test_iter_days_inclusive() -> None:
    days = list(iter_days(date(2026, 9, 1), date(2026, 9, 3)))
    assert days == [date(2026, 9, 1), date(2026, 9, 2), date(2026, 9, 3)]
