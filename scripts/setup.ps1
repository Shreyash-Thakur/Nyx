# One-time setup for Nyx on Windows (PowerShell).
# Creates a Python venv, installs backend + frontend deps, runs migrations.
# Idempotent: rerunning is safe.

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $RepoRoot

Write-Host "==> Nyx setup" -ForegroundColor Cyan
Write-Host "Repo: $RepoRoot"

# --- Backend ----------------------------------------------------------------
Write-Host "`n==> Backend: Python venv + deps" -ForegroundColor Cyan
Set-Location "$RepoRoot\backend"

if (-not (Test-Path ".venv")) {
    Write-Host "Creating .venv ..."
    python -m venv .venv
}

$Python = ".\.venv\Scripts\python.exe"
& $Python -m pip install --upgrade pip wheel
& $Python -m pip install -r requirements.txt

Write-Host "`n==> Backend: running migrations (SQLite by default)" -ForegroundColor Cyan
& ".\.venv\Scripts\alembic.exe" upgrade head

# --- Frontend ---------------------------------------------------------------
Write-Host "`n==> Frontend: npm install" -ForegroundColor Cyan
Set-Location "$RepoRoot\frontend"
npm install

# --- Done -------------------------------------------------------------------
Set-Location $RepoRoot
Write-Host "`n==> Done." -ForegroundColor Green
Write-Host "Run the dev servers with:  .\scripts\dev.ps1"
