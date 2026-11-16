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

```bash
python3.14 ganttgen.py --tasks other.csv --config other.toml --out out.html
```

## Inputs

- **tasks.csv** — row order is schedule order within a milestone. Columns: `id`, `name`, `milestone`, `size` (`S`/`M`/`L`).
- **config.toml** — title, milestone dates, sizing matrix, weekends, holidays, team colours, `milestone_align` (`implement` \| `test`), `allow_team_overload`:
  - `false` — no same-team overlap *within* a milestone (CSV-order pipeline). Milestones are scheduled independently, so same-team work may overlap *across* milestones.
  - `true` — each SP is independent; same-team overlap is allowed within a milestone as well.

Scheduling works **backwards** (as late as possible) from each milestone date. With `milestone_align = "implement"`, Test may run after the milestone marker.
