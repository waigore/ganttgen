"""Unit tests for models."""

from __future__ import annotations

from datetime import date

from ganttgen.models import Holiday, SubTask
from tests.conftest import make_config


def test_config_holiday_dates_derived() -> None:
    cfg = make_config(holidays=[Holiday(date=date(2026, 1, 1), name="NY")])
    assert date(2026, 1, 1) in cfg.holiday_dates


def test_subtask_key() -> None:
    st = SubTask(
        sp_id="SP1",
        sp_name="One",
        milestone="M1",
        phase="design",
        size="S",
        duration=1,
    )
    assert st.key == "SP1:design"
