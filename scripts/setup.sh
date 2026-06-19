#!/usr/bin/env bash
# One-time setup for Nyx on macOS / Linux / WSL.
# Creates a Python venv, installs backend + frontend deps, runs migrations.
# Idempotent: rerunning is safe.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

echo "==> Nyx setup"
echo "Repo: $REPO_ROOT"

# --- Backend ----------------------------------------------------------------
echo ""
echo "==> Backend: Python venv + deps"
cd "$REPO_ROOT/backend"

if [[ ! -d .venv ]]; then
  echo "Creating .venv ..."
  python3 -m venv .venv
fi

# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --upgrade pip wheel
python -m pip install -r requirements.txt

echo ""
echo "==> Backend: running migrations (SQLite by default)"
alembic upgrade head

# --- Frontend ---------------------------------------------------------------
echo ""
echo "==> Frontend: npm install"
cd "$REPO_ROOT/frontend"
npm install

# --- Done -------------------------------------------------------------------
cd "$REPO_ROOT"
echo ""
echo "==> Done."
echo "Run the dev servers with:  ./scripts/dev.sh"
