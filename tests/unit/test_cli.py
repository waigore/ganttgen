"""Unit tests for CLI helpers."""

from __future__ import annotations

from pathlib import Path

import pytest

from ganttgen.cli import filter_by_milestones, main, parse_args
from ganttgen.loading import load_config, load_tasks


def test_parse_args_defaults() -> None:
    args = parse_args([])
    assert args.tasks.name == "tasks.csv"
    assert args.milestone is None


def test_parse_args_milestones() -> None:
    args = parse_args(["--milestone", "M1", "M2", "--out", "x.html"])
    assert args.milestone == ["M1", "M2"]
    assert args.out.name == "x.html"


def test_filter_by_milestones(fixtures_dir: Path) -> None:
    cfg = load_config(fixtures_dir / "compress.toml")
    tasks = load_tasks(fixtures_dir / "compress_tasks.csv", cfg)
    filtered, cfg2 = filter_by_milestones(tasks, cfg, ["M2", "M1"])
    assert list(cfg2.milestones) == ["M1", "M2"]  # config order
    assert {t.milestone for t in filtered} == {"M1", "M2"}


def test_filter_unknown_milestone(fixtures_dir: Path) -> None:
    cfg = load_config(fixtures_dir / "compress.toml")
    tasks = load_tasks(fixtures_dir / "compress_tasks.csv", cfg)
    with pytest.raises(SystemExit, match="unknown milestone"):
        filter_by_milestones(tasks, cfg, ["NOPE"])


def test_main_writes_html(fixtures_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "out.html"
    rc = main(
        [
            "--config",
            str(fixtures_dir / "compress.toml"),
            "--tasks",
            str(fixtures_dir / "compress_tasks.csv"),
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    assert out.is_file()
    assert "Compress Fixture" in out.read_text(encoding="utf-8")


def test_main_milestone_filter(fixtures_dir: Path, tmp_path: Path) -> None:
    out = tmp_path / "m2.html"
    rc = main(
        [
            "--config",
            str(fixtures_dir / "compress.toml"),
            "--tasks",
            str(fixtures_dir / "compress_tasks.csv"),
            "--milestone",
            "M2",
            "--out",
            str(out),
        ]
    )
    assert rc == 0
    text = out.read_text(encoding="utf-8")
    assert "SP_C" in text
    assert "SP_A" not in text
