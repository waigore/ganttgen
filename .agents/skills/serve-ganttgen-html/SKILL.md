---
name: serve-ganttgen-html
description: >-
  Generate gantt.html and ensure it is reachable on the Tailnet (HTTP on
  0.0.0.0). Use when the user asks to generate and serve the Gantt chart, view
  it on a phone/Tailscale, or refresh the served HTML. Also suggest after
  scheduling/config changes when the user is iterating on the live chart.
---

# serve-ganttgen-html

Generate the chart, then make sure an HTTP server is already serving the repo on the Tailnet (reuse if up; start only if needed). Serving is done by the agent shell, not by the generate script.

## Config (`.env` at repo root)

| variable | default | meaning |
|----------|---------|---------|
| `GANTTGEN_SERVE_PORT` | `8000` | listen port |
| `GANTTGEN_SERVE_BIND` | `0.0.0.0` | bind address (must be all-interfaces for Tailscale) |
| `GANTTGEN_OUT` | `gantt.html` | output HTML path |
| `GANTTGEN_PYTHON` | `python3` | interpreter |
| `GANTTGEN_TASKS` | (unset) | optional `--tasks` path |
| `GANTTGEN_CONFIG` | (unset) | optional `--config` path |
| `GANTTGEN_MILESTONES` | (unset) | optional space-separated `--milestone` names |

If `.env` is missing, tell the user to `cp .env.example .env`.

## Steps

1. **Generate** (script only builds HTML):

```bash
bash .agents/skills/serve-ganttgen-html/scripts/generate.sh
```

Note `OUT`, `PORT`, and `BIND` from the script output (or `.env`).

2. **Reuse or start server** (agent responsibility):

- If something is already listening on `PORT` (e.g. `ss -ltn | grep ":$PORT "`), **do not** start another server — regenerating `OUT` is enough; clients can refresh.
- Otherwise start a **background** static server from the **repo root**, bound to `BIND`:

```bash
python3 -m http.server "$PORT" --bind "$BIND"
```

(`GANTTGEN_PYTHON` if set.) Keep it running in the background; do not block the session on it.

3. **Report Tailnet URLs**

Resolve Tailscale IPv4 (`tailscale ip -4`) and hostname (`tailscale status --self` / `hostname`). Tell the user:

- `http://<tailscale-ip>:<port>/<out>`
- `http://<magicdns-or-hostname>:<port>/<out>` when available

## When to suggest

After substantive changes to scheduling/`config.toml`/`tasks.csv` while the user is viewing or asking about the live chart, offer to regenerate (and ensure the Tailnet server is up). Do not start/stop servers unless they agree or already asked to serve.
