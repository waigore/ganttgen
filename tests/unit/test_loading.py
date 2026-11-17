"""Unit tests for loading config and tasks."""

from __future__ import annotations

from pathlib import Path

import pytest

from ganttgen.loading import load_config, load_tasks


def test_load_compress_config(fixtures_dir: Path) -> None:
    cfg = load_config(fixtures_dir / "compress.toml")
    assert cfg.schedule_mode == "compress"
    assert cfg.project_start is not None
    assert "M1" in cfg.milestones
    named = [h for h in cfg.holidays if h.name == "Fixture Holiday"]
    assert named[0].date.isoformat() == "2026-09-07"


def test_load_align_config(fixtures_dir: Path) -> None:
    cfg = load_config(fixtures_dir / "align.toml")
    assert cfg.schedule_mode == "align"
    assert cfg.project_start is None


def test_compress_requires_project_start(fixtures_dir: Path) -> None:
    with pytest.raises(SystemExit, match="project_start"):
        load_config(fixtures_dir / "missing_project_start.toml")


def test_load_tasks_ok(fixtures_dir: Path) -> None:
    cfg = load_config(fixtures_dir / "compress.toml")
    tasks = load_tasks(fixtures_dir / "compress_tasks.csv", cfg)
    assert [t.id for t in tasks] == ["SP_A", "SP_B", "SP_C"]


def test_duplicate_ids(fixtures_dir: Path) -> None:
    cfg = load_config(fixtures_dir / "compress.toml")
    with pytest.raises(SystemExit, match="duplicate id"):
        load_tasks(fixtures_dir / "dup_tasks.csv", cfg)


def test_bad_size(fixtures_dir: Path) -> None:
    cfg = load_config(fixtures_dir / "compress.toml")
    with pytest.raises(SystemExit, match="unknown size"):
        load_tasks(fixtures_dir / "bad_size_tasks.csv", cfg)


def test_bom_csv(fixtures_dir: Path) -> None:
    cfg = load_config(fixtures_dir / "compress.toml")
    tasks = load_tasks(fixtures_dir / "bom_tasks.csv", cfg)
    assert tasks[0].id == "SP_BOM"


def test_missing_config(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="Config not found"):
        load_config(tmp_path / "nope.toml")


def test_missing_tasks(fixtures_dir: Path, tmp_path: Path) -> None:
    cfg = load_config(fixtures_dir / "compress.toml")
    with pytest.raises(SystemExit, match="Tasks CSV not found"):
        load_tasks(tmp_path / "nope.csv", cfg)


def test_removed_keys_rejected(tmp_path: Path) -> None:
    path = tmp_path / "bad.toml"
    path.write_text(
        'title="x"\nschedule_mode="align"\nallow_team_overload=true\n'
        "[milestones]\nM1=2026-10-01\n"
        "[sizing.S]\ndesign=1\nimplement=1\ntest=1\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="allow_team_overload"):
        load_config(path)


def test_invalid_align_and_mode(tmp_path: Path) -> None:
    bad_align = tmp_path / "align.toml"
    bad_align.write_text(
        'milestone_align="nope"\nschedule_mode="align"\n'
        "[milestones]\nM1=2026-10-01\n"
        "[sizing.S]\ndesign=1\nimplement=1\ntest=1\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="milestone_align"):
        load_config(bad_align)

    bad_mode = tmp_path / "mode.toml"
    bad_mode.write_text(
        'schedule_mode="warp"\n'
        "[milestones]\nM1=2026-10-01\n"
        "[sizing.S]\ndesign=1\nimplement=1\ntest=1\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="schedule_mode"):
        load_config(bad_mode)


def test_capacity_scope_removed(tmp_path: Path) -> None:
    path = tmp_path / "scope.toml"
    path.write_text(
        'schedule_mode="align"\ncapacity_scope="global"\n'
        "[milestones]\nM1=2026-10-01\n"
        "[sizing.S]\ndesign=1\nimplement=1\ntest=1\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="capacity_scope"):
        load_config(path)


def test_bad_weekends_and_empty_tasks(tmp_path: Path, fixtures_dir: Path) -> None:
    path = tmp_path / "weekends.toml"
    path.write_text(
        'schedule_mode="align"\nweekends=[9]\n'
        "[milestones]\nM1=2026-10-01\n"
        "[sizing.S]\ndesign=1\nimplement=1\ntest=1\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="weekends"):
        load_config(path)

    cfg = load_config(fixtures_dir / "compress.toml")
    empty = tmp_path / "empty.csv"
    empty.write_text("id,name,milestone,size\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="no data rows"):
        load_tasks(empty, cfg)


def test_unknown_milestone_in_tasks(tmp_path: Path, fixtures_dir: Path) -> None:
    cfg = load_config(fixtures_dir / "compress.toml")
    path = tmp_path / "tasks.csv"
    path.write_text(
        "id,name,milestone,size\nSP1,One,MX,S\n", encoding="utf-8"
    )
    with pytest.raises(SystemExit, match="unknown milestone"):
        load_tasks(path, cfg)


def test_bad_team_capacity(tmp_path: Path) -> None:
    path = tmp_path / "cap.toml"
    path.write_text(
        'schedule_mode="align"\n'
        "[milestones]\nM1=2026-10-01\n"
        "[sizing.S]\ndesign=1\nimplement=1\ntest=1\n"
        "[teams.design]\ncapacity=0\n",
        encoding="utf-8",
    )
    with pytest.raises(SystemExit, match="capacity"):
        load_config(path)
