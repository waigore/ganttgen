---
name: update-ganttgen-gist
description: >-
  Update the ganttgen secret GitHub gist with essentials (ganttgen.py,
  config.toml, tasks.csv) using settings from the repo .env file. Use when the
  user asks to update/sync/publish the gist, or after changing ganttgen.py,
  config.toml, or tasks.csv when those changes should be reflected on the gist
  — suggest running this skill rather than editing the gist ad hoc.
---

# update-ganttgen-gist

Push the configured essential files to the project’s secret gist.

## Config (`.env` at repo root)

Required (see `.env.example`):

| variable | meaning |
|----------|---------|
| `GANTTGEN_GIST_ID` | Gist id (not the full URL) |
| `GANTTGEN_GIST_FILES` | Comma-separated repo-relative paths |

Optional:

| variable | meaning |
|----------|---------|
| `GANTTGEN_GIST_SHORT_URL` | Printed after update if set |

`.env` is gitignored. If missing, tell the user to `cp .env.example .env`.

## How to update

From the repo root:

```bash
bash .agents/skills/update-ganttgen-gist/scripts/update-gist.sh
```

Requires `gh` authenticated with permission to edit that gist.

## After success

Report both URLs when available:

- `https://gist.github.com/<GANTTGEN_GIST_ID>`
- `GANTTGEN_GIST_SHORT_URL` if set

## When to suggest

After substantive edits to any path listed in `GANTTGEN_GIST_FILES`, briefly offer to update the gist (do not run unless the user agrees, unless they already asked to update/sync the gist).
