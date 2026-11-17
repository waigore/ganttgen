"""Command-line interface for GanttGen."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .loading import load_config, load_tasks
from .models import DEFAULT_CONFIG, DEFAULT_OUT, DEFAULT_TASKS, Config, TaskRow
from .render import render_html
from .scheduling import build_schedule


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
    p.add_argument(
        "--milestone",
        nargs="+",
        metavar="NAME",
        help="only include these milestones (default: all)",
    )
    return p.parse_args(argv)


def filter_by_milestones(
    tasks: list[TaskRow], config: Config, names: list[str]
) -> tuple[list[TaskRow], Config]:
    """Keep only the named milestones; preserve config.toml milestone order."""
    unknown = [n for n in names if n not in config.milestones]
    if unknown:
        known = ", ".join(config.milestones)
        raise SystemExit(
            f"unknown milestone(s): {', '.join(unknown)} (known: {known})"
        )
    selected = set(names)
    # Preserve config.toml key order, not CLI argument order
    config.milestones = {
        k: v for k, v in config.milestones.items() if k in selected
    }
    filtered = [t for t in tasks if t.milestone in selected]
    if not filtered:
        raise SystemExit(
            f"no tasks for milestone(s): {', '.join(config.milestones)}"
        )
    return filtered, config


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
    if args.milestone:
        tasks, config = filter_by_milestones(tasks, config, args.milestone)
    schedule = build_schedule(tasks, config)
    html_text = render_html(schedule)
    args.out.write_text(html_text, encoding="utf-8")
    print(f"Wrote {args.out} ({len(schedule.subtasks)} subtasks)")
    return 0

