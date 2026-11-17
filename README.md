# ganttgen

Pure-stdlib Python Gantt chart generator for stored-procedure / program delivery plans.

Requires **Python 3.14+**. No third-party packages (and no `uv` at runtime).

## Usage

```bash
python3.14 ganttgen.py
```

Defaults (override only if needed):

| flag | default |
|------|---------|
| `--tasks` | `tasks.csv` |
| `--config` | `config.toml` |
| `--out` | `gantt.html` |
| `--milestone` | all milestones |

```bash
python3.14 ganttgen.py --tasks other.csv --config other.toml --out out.html
python3.14 ganttgen.py --milestone M2 --out gantt-m2.html
python3.14 ganttgen.py --milestone M1 M3 --out gantt-m1-m3.html
```

With `--milestone`, only those milestones’ tasks are scheduled and the chart date range is cropped to that subset.

## Inputs

- **tasks.csv** — columns: `id`, `name`, `milestone`, `size` (`S`/`M`/`L`). UTF-8 with or without BOM. Duplicate `id` values are rejected (error lists line numbers). CSV order is the tie-break when several tasks are equally ready.
- **config.toml** — title, milestones, sizing, weekends, holidays, team colours/capacities, and:
  - `schedule_mode = "compress"` (default) — pack ASAP from `project_start` with a global ready queue across milestones (later-milestone work may run while earlier-milestone work is still open, up to capacity). Milestone dates are markers only.
  - `schedule_mode = "align"` — pack each milestone separately (per-milestone capacity), then shift so the last SP’s `milestone_align` phase ends on the milestone date.
  - `project_start` — **required** for `compress`.
  - `milestone_align` — `implement` \| `test` (used by `align`).
  - `teams.*.capacity` — max simultaneous tasks per team per day (defaults: design 1, implement 3, test 3).
