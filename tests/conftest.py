"""Shared pytest fixtures."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

import pytest

# Root ganttgen.py shadows the package on sys.path; prefer src/ganttgen/.
ROOT = Path(__file__).resolve().parents[1]
_SRC = str(ROOT / "src")
while _SRC in sys.path:
    sys.path.remove(_SRC)
sys.path.insert(0, _SRC)
for _name in list(sys.modules):
    if _name == "ganttgen" or _name.startswith("ganttgen."):
        del sys.modules[_name]

from ganttgen.models import PHASES, Config, Holiday, TaskRow, TeamStyle  # noqa: E402

FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def repo_root() -> Path:
    return ROOT


@pytest.fixture
def built_script(repo_root: Path) -> Path:
    path = repo_root / "ganttgen.py"
    assert path.is_file(), "ganttgen.py missing — run python build.py"
    return path


def make_config(
    *,
    schedule_mode: str = "compress",
    project_start: date | None = date(2026, 9, 1),
    weekends: set[int] | None = None,
    milestones: dict[str, date] | None = None,
    holidays: list[Holiday] | None = None,
    capacities: dict[str, int] | None = None,
    milestone_align: str = "implement",
    actuals_book_capacity: bool = True,
) -> Config:
    caps = capacities or {"design": 1, "implement": 3, "test": 3}
    teams = {
        p: TeamStyle(key=p, label=p.title(), color="#000000", capacity=caps[p])
        for p in PHASES
    }
    return Config(
        title="Test Plan",
        milestone_align=milestone_align,
        schedule_mode=schedule_mode,
        project_start=project_start,
        weekends=weekends if weekends is not None else {5, 6},
        milestones=milestones
        or {
            "M1": date(2026, 11, 30),
            "M2": date(2026, 12, 16),
        },
        sizing={
            "S": {"design": 1, "implement": 1, "test": 1},
            "M": {"design": 2, "implement": 2, "test": 2},
            "L": {"design": 3, "implement": 3, "test": 3},
        },
        teams=teams,
        holidays=holidays or [],
        actuals_book_capacity=actuals_book_capacity,
    )


def make_tasks(*rows: tuple[str, str, str, str]) -> list[TaskRow]:
    """rows: (id, name, milestone, size)."""
    return [
        TaskRow(id=r[0], name=r[1], milestone=r[2], size=r[3], index=i)
        for i, r in enumerate(rows)
    ]


@pytest.fixture
def basic_config() -> Config:
    return make_config()
