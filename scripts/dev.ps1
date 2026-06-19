# Start the backend (uvicorn) and frontend (next dev) in parallel windows.
# Assumes scripts/setup.ps1 has already been run.
#
# Usage:  .\scripts\dev.ps1

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path -Parent $PSScriptRoot

if (-not (Test-Path "$RepoRoot\backend\.venv\Scripts\python.exe")) {
    Write-Host "Backend venv not found. Run .\scripts\setup.ps1 first." -ForegroundColor Red
    exit 1
}

if (-not (Test-Path "$RepoRoot\frontend\node_modules")) {
    Write-Host "Frontend node_modules not found. Run .\scripts\setup.ps1 first." -ForegroundColor Red
    exit 1
}

Write-Host "==> Starting backend on http://localhost:8000" -ForegroundColor Cyan
$backendArgs = "-NoExit -Command `"Set-Location '$RepoRoot\backend'; .\.venv\Scripts\Activate.ps1; uvicorn app.main:app --reload --port 8000`""
Start-Process powershell -ArgumentList $backendArgs -WindowStyle Normal

Start-Sleep -Seconds 2

Write-Host "==> Starting frontend on http://localhost:3000" -ForegroundColor Cyan
$frontendArgs = "-NoExit -Command `"Set-Location '$RepoRoot\frontend'; npm run dev`""
Start-Process powershell -ArgumentList $frontendArgs -WindowStyle Normal

Write-Host ""
Write-Host "Backend:  http://localhost:8000  (docs at /docs)" -ForegroundColor Green
Write-Host "Frontend: http://localhost:3000" -ForegroundColor Green
Write-Host ""
Write-Host "Both processes are running in separate windows. Close them to stop."
