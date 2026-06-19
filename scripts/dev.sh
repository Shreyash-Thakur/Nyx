#!/usr/bin/env bash
# Start backend (uvicorn) and frontend (next dev) in parallel.
# Assumes scripts/setup.sh has already been run.
#
# Usage:  ./scripts/dev.sh
# Ctrl-C stops both.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if [[ ! -d "$REPO_ROOT/backend/.venv" ]]; then
  echo "Backend venv not found. Run ./scripts/setup.sh first." >&2
  exit 1
fi
if [[ ! -d "$REPO_ROOT/frontend/node_modules" ]]; then
  echo "Frontend node_modules not found. Run ./scripts/setup.sh first." >&2
  exit 1
fi

cleanup() {
  echo ""
  echo "==> Stopping..."
  jobs -p | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "==> Starting backend on http://localhost:8000"
(
  cd "$REPO_ROOT/backend"
  # shellcheck disable=SC1091
  source .venv/bin/activate
  uvicorn app.main:app --reload --port 8000
) &

sleep 2

echo "==> Starting frontend on http://localhost:3000"
(
  cd "$REPO_ROOT/frontend"
  npm run dev
) &

echo ""
echo "Backend:  http://localhost:8000  (docs at /docs)"
echo "Frontend: http://localhost:3000"
echo ""
echo "Press Ctrl-C to stop both."
wait
