"""GanttGen: pure-stdlib Gantt chart generator."""

from .cli import main
from .loading import load_config, load_tasks
from .render import render_html
from .scheduling import build_schedule

__all__ = [
    "build_schedule",
    "load_config",
    "load_tasks",
    "main",
    "render_html",
]

__version__ = "1.0.0"
