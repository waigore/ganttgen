#!/usr/bin/env bash
# Generate gantt HTML using repo .env settings (does not start a server).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "missing .env — copy .env.example to .env and set GANTTGEN_*" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

OUT="${GANTTGEN_OUT:-gantt.html}"
PYTHON="${GANTTGEN_PYTHON:-python3}"

args=(ganttgen.py --out "$OUT")
if [[ -n "${GANTTGEN_TASKS:-}" ]]; then
  args+=(--tasks "$GANTTGEN_TASKS")
fi
if [[ -n "${GANTTGEN_CONFIG:-}" ]]; then
  args+=(--config "$GANTTGEN_CONFIG")
fi
# Space-separated milestone names, e.g. "M1 M3". Empty = all.
if [[ -n "${GANTTGEN_MILESTONES:-}" ]]; then
  # shellcheck disable=SC2206
  ms=($GANTTGEN_MILESTONES)
  args+=(--milestone "${ms[@]}")
fi

"$PYTHON" "${args[@]}"
echo "OUT=$OUT"
echo "PORT=${GANTTGEN_SERVE_PORT:-8000}"
echo "BIND=${GANTTGEN_SERVE_BIND:-0.0.0.0}"
