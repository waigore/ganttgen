"""Data types and constants for GanttGen."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

PHASES = ("design", "implement", "test")
DEFAULT_TASKS = Path("tasks.csv")
DEFAULT_CONFIG = Path("config.toml")
DEFAULT_OUT = Path("gantt.html")
DEFAULT_CAPACITIES = {"design": 1, "implement": 3, "test": 3}


@dataclass(frozen=True)
class Holiday:
    date: date
    name: str


@dataclass(frozen=True)
class TeamStyle:
    key: str
    label: str
    color: str
    capacity: int


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
    schedule_mode: str  # "compress" | "align"
    project_start: date | None  # required for compress
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
