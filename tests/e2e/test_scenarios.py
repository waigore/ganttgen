"""End-to-end tests against the built ganttgen.py."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

PYTHON = sys.executable


def _run_built(
    built_script: Path,
    *,
    cwd: Path,
    args: list[str],
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [PYTHON, str(built_script), *args],
        cwd=cwd,
        check=check,
        capture_output=True,
        text=True,
    )


def _run_modular(
    repo_root: Path,
    *,
    cwd: Path,
    args: list[str],
) -> subprocess.CompletedProcess[str]:
    """Run package CLI from a temp cwd so root ganttgen.py does not shadow."""
    env = os.environ.copy()
    env["PYTHONPATH"] = str(repo_root / "src")
    return subprocess.run(
        [PYTHON, "-m", "ganttgen", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def test_e2e_compress_default(
    built_script: Path, fixtures_dir: Path, tmp_path: Path
) -> None:
    out = tmp_path / "compress.html"
    proc = _run_built(
        built_script,
        cwd=tmp_path,
        args=[
            "--config",
            str(fixtures_dir / "compress.toml"),
            "--tasks",
            str(fixtures_dir / "compress_tasks.csv"),
            "--out",
            str(out),
        ],
    )
    assert proc.returncode == 0
    text = out.read_text(encoding="utf-8")
    assert "Compress Fixture" in text
    assert "Compress mode" in text
    assert "SP_A" in text


def test_e2e_align_mode(
    built_script: Path, fixtures_dir: Path, tmp_path: Path
) -> None:
    out = tmp_path / "align.html"
    _run_built(
        built_script,
        cwd=tmp_path,
        args=[
            "--config",
            str(fixtures_dir / "align.toml"),
            "--tasks",
            str(fixtures_dir / "align_tasks.csv"),
            "--out",
            str(out),
        ],
    )
    text = out.read_text(encoding="utf-8")
    assert "Align mode" in text
    assert "SP_A1" in text


def test_e2e_milestone_filters(
    built_script: Path, fixtures_dir: Path, tmp_path: Path
) -> None:
    out_one = tmp_path / "m1.html"
    _run_built(
        built_script,
        cwd=tmp_path,
        args=[
            "--config",
            str(fixtures_dir / "compress.toml"),
            "--tasks",
            str(fixtures_dir / "compress_tasks.csv"),
            "--milestone",
            "M1",
            "--out",
            str(out_one),
        ],
    )
    one = out_one.read_text(encoding="utf-8")
    assert "SP_A" in one and "SP_B" in one
    assert "SP_C" not in one

    out_multi = tmp_path / "m1m2.html"
    _run_built(
        built_script,
        cwd=tmp_path,
        args=[
            "--config",
            str(fixtures_dir / "compress.toml"),
            "--tasks",
            str(fixtures_dir / "compress_tasks.csv"),
            "--milestone",
            "M1",
            "M2",
            "--out",
            str(out_multi),
        ],
    )
    multi = out_multi.read_text(encoding="utf-8")
    assert "SP_A" in multi and "SP_C" in multi


def test_e2e_holidays_and_weekends_in_html(
    built_script: Path, fixtures_dir: Path, tmp_path: Path
) -> None:
    out = tmp_path / "hol.html"
    _run_built(
        built_script,
        cwd=tmp_path,
        args=[
            "--config",
            str(fixtures_dir / "compress.toml"),
            "--tasks",
            str(fixtures_dir / "compress_tasks.csv"),
            "--out",
            str(out),
        ],
    )
    text = out.read_text(encoding="utf-8")
    assert 'class="day weekend"' in text or "weekend" in text
    assert "holiday" in text
    assert "Fixture Holiday" in text


def test_e2e_capacity_contention(
    built_script: Path, fixtures_dir: Path, tmp_path: Path
) -> None:
    out = tmp_path / "cap.html"
    proc = _run_built(
        built_script,
        cwd=tmp_path,
        args=[
            "--config",
            str(fixtures_dir / "capacity.toml"),
            "--tasks",
            str(fixtures_dir / "capacity_tasks.csv"),
            "--out",
            str(out),
        ],
    )
    assert "12 subtasks" in proc.stdout
    text = out.read_text(encoding="utf-8")
    assert "SP_1" in text and "SP_4" in text


@pytest.mark.parametrize(
    ("config_name", "tasks_name", "match"),
    [
        ("missing_project_start.toml", "compress_tasks.csv", "project_start"),
        ("compress.toml", "dup_tasks.csv", "duplicate id"),
        ("compress.toml", "bad_size_tasks.csv", "unknown size"),
    ],
)
def test_e2e_invalid_inputs(
    built_script: Path,
    fixtures_dir: Path,
    tmp_path: Path,
    config_name: str,
    tasks_name: str,
    match: str,
) -> None:
    proc = _run_built(
        built_script,
        cwd=tmp_path,
        args=[
            "--config",
            str(fixtures_dir / config_name),
            "--tasks",
            str(fixtures_dir / tasks_name),
            "--out",
            str(tmp_path / "out.html"),
        ],
        check=False,
    )
    assert proc.returncode != 0
    err = proc.stderr + proc.stdout
    assert match in err


def test_e2e_bom_csv(
    built_script: Path, fixtures_dir: Path, tmp_path: Path
) -> None:
    out = tmp_path / "bom.html"
    _run_built(
        built_script,
        cwd=tmp_path,
        args=[
            "--config",
            str(fixtures_dir / "compress.toml"),
            "--tasks",
            str(fixtures_dir / "bom_tasks.csv"),
            "--out",
            str(out),
        ],
    )
    assert "SP_BOM" in out.read_text(encoding="utf-8")


def test_e2e_modular_vs_merged_parity(
    built_script: Path,
    fixtures_dir: Path,
    repo_root: Path,
    tmp_path: Path,
) -> None:
    args = [
        "--config",
        str(fixtures_dir / "compress.toml"),
        "--tasks",
        str(fixtures_dir / "compress_tasks.csv"),
    ]
    built_out = tmp_path / "built.html"
    mod_out = tmp_path / "modular.html"
    _run_built(
        built_script,
        cwd=tmp_path,
        args=[*args, "--out", str(built_out)],
    )
    _run_modular(
        repo_root,
        cwd=tmp_path,
        args=[*args, "--out", str(mod_out)],
    )
    assert built_out.read_text(encoding="utf-8") == mod_out.read_text(
        encoding="utf-8"
    )


def test_e2e_repo_sample_inputs(
    built_script: Path, repo_root: Path, tmp_path: Path
) -> None:
    out = tmp_path / "sample.html"
    proc = _run_built(
        built_script,
        cwd=repo_root,
        args=["--out", str(out)],
    )
    assert proc.returncode == 0
    assert out.stat().st_size > 1000
