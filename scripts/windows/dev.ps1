<#
.SYNOPSIS
    Architecture Review Agent — Start both FastAPI backend and React frontend for local development.

.DESCRIPTION
    Runs the FastAPI backend on port 8000 and the Vite React dev server on port 5173.
    The Vite dev server proxies /api requests to the backend.

.EXAMPLE
    .\scripts\windows\dev.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Go up 2 levels: scripts/windows -> scripts -> project root
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)

Write-Host ""
Write-Host "=== Architecture Review Agent Dev Server ===" -ForegroundColor Cyan
Write-Host ""

# ── 1. Check prerequisites ──────────────────────────────────────────────────
$venvActivate = Join-Path $ProjectRoot ".venv\Scripts\Activate.ps1"
if (-not (Test-Path $venvActivate)) {
    Write-Host "[ERROR] .venv not found. Run .\scripts\windows\setup.ps1 first." -ForegroundColor Red
    exit 1
}

$frontendDir = Join-Path $ProjectRoot "frontend"
if (-not (Test-Path (Join-Path $frontendDir "node_modules"))) {
    Write-Host "[..] Installing frontend dependencies..." -ForegroundColor Yellow
    Push-Location $frontendDir
    npm install
    Pop-Location
}

# ── 2. Activate Python venv ─────────────────────────────────────────────────
Write-Host "[..] Activating Python virtual environment..." -ForegroundColor Yellow
& $venvActivate

# ── 3. Start FastAPI backend (background) ───────────────────────────────────
Write-Host "[..] Starting FastAPI backend on http://localhost:8000 ..." -ForegroundColor Yellow
$backendJob = Start-Job -ScriptBlock {
    param($root, $activate)
    Set-Location $root
    & $activate
    python -m uvicorn api:app --host 0.0.0.0 --port 8000 --reload
} -ArgumentList $ProjectRoot, $venvActivate

# ── 4. Start Vite frontend (foreground) ─────────────────────────────────────
Write-Host "[..] Starting React dev server on http://localhost:5173 ..." -ForegroundColor Yellow
Write-Host ""
Write-Host "  Frontend: http://localhost:5173" -ForegroundColor Green
Write-Host "  Backend:  http://localhost:8000/api/health" -ForegroundColor Green
Write-Host "  Press Ctrl+C to stop both servers." -ForegroundColor White
Write-Host ""

try {
    Push-Location $frontendDir
    npx vite --host
} finally {
    Write-Host ""
    Write-Host "[..] Shutting down backend..." -ForegroundColor Yellow
    Stop-Job $backendJob -ErrorAction SilentlyContinue
    Remove-Job $backendJob -Force -ErrorAction SilentlyContinue
    Pop-Location
    Write-Host "[OK] All servers stopped." -ForegroundColor Green
}
