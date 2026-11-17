#!/usr/bin/env bash
# Push ganttgen essentials to the configured secret gist.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
cd "$ROOT"

if [[ ! -f .env ]]; then
  echo "missing .env — copy .env.example to .env and set GANTTGEN_GIST_*" >&2
  exit 1
fi

set -a
# shellcheck disable=SC1091
source .env
set +a

: "${GANTTGEN_GIST_ID:?GANTTGEN_GIST_ID is required in .env}"
: "${GANTTGEN_GIST_FILES:?GANTTGEN_GIST_FILES is required in .env}"

IFS=',' read -r -a FILES <<< "$GANTTGEN_GIST_FILES"
for f in "${FILES[@]}"; do
  f="${f#"${f%%[![:space:]]*}"}"
  f="${f%"${f##*[![:space:]]}"}"
  if [[ ! -f "$f" ]]; then
    echo "missing file: $f" >&2
    exit 1
  fi
  echo "Updating gist file: $f"
  gh gist edit "$GANTTGEN_GIST_ID" -a "$f"
done

echo "https://gist.github.com/${GANTTGEN_GIST_ID}"
if [[ -n "${GANTTGEN_GIST_SHORT_URL:-}" ]]; then
  echo "$GANTTGEN_GIST_SHORT_URL"
fi
