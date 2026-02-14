<#
.SYNOPSIS
    Architecture Review Agent — One-click setup script for Windows (PowerShell).

.DESCRIPTION
    Creates a .venv virtual environment, installs dependencies from
    requirements.txt, and copies .env.template to .env if it doesn't exist.

.EXAMPLE
    .\scripts\windows\setup.ps1
#>

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# Go up 2 levels: scripts/windows -> scripts -> project root
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Push-Location $ProjectRoot

Write-Host ""
Write-Host "=== Architecture Review Agent Setup ===" -ForegroundColor Cyan
Write-Host ""

# ── 1. Check Python ──────────────────────────────────────────────────────────
$python = $null
foreach ($candidate in @("python3", "python")) {
    try {
        $ver = & $candidate --version 2>&1
        if ($ver -match "Python\s+(\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 11) {
                $python = $candidate
                Write-Host "[OK] Found $ver" -ForegroundColor Green
                break
            } else {
                Write-Host "[WARN] $ver found but Python 3.11+ is required." -ForegroundColor Yellow
            }
        }
    } catch {
        # candidate not found — try next
    }
}

if (-not $python) {
    Write-Host "[ERROR] Python 3.11+ is required but was not found on PATH." -ForegroundColor Red
    Write-Host "        Install from https://www.python.org/downloads/" -ForegroundColor Red
    Pop-Location
    exit 1
}

# ── 2. Create .venv ──────────────────────────────────────────────────────────
$venvDir = Join-Path $ProjectRoot ".venv"
if (Test-Path $venvDir) {
    Write-Host "[OK] Virtual environment already exists at .venv/" -ForegroundColor Green
} else {
    Write-Host "[..] Creating virtual environment (.venv)..." -ForegroundColor Yellow
    & $python -m venv $venvDir
    Write-Host "[OK] Created .venv/" -ForegroundColor Green
}

# ── 3. Activate & install dependencies ────────────────────────────────────────
$activateScript = Join-Path $venvDir "Scripts\Activate.ps1"
if (-not (Test-Path $activateScript)) {
    Write-Host "[ERROR] Cannot find $activateScript" -ForegroundColor Red
    Pop-Location
    exit 1
}

Write-Host "[..] Activating virtual environment..." -ForegroundColor Yellow
& $activateScript

Write-Host "[..] Upgrading pip..." -ForegroundColor Yellow
& python -m pip install --upgrade pip --quiet

Write-Host "[..] Installing dependencies from requirements.txt..." -ForegroundColor Yellow
& python -m pip install -r (Join-Path $ProjectRoot "requirements.txt")
Write-Host "[OK] Dependencies installed." -ForegroundColor Green

# ── 4. Copy .env.template → .env (if needed) ─────────────────────────────────
$envFile = Join-Path $ProjectRoot ".env"
$envTemplate = Join-Path $ProjectRoot ".env.template"
if (-not (Test-Path $envFile)) {
    if (Test-Path $envTemplate) {
        Copy-Item $envTemplate $envFile
        Write-Host "[OK] Created .env from .env.template — edit it with your settings." -ForegroundColor Green
    } else {
        Write-Host "[WARN] No .env.template found. Create a .env file manually." -ForegroundColor Yellow
    }
} else {
    Write-Host "[OK] .env already exists." -ForegroundColor Green
}
# ── 5. Create output directory ─────────────────────────────────────────────────────────────
$outputDir = Join-Path $ProjectRoot "output"
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir | Out-Null
    Write-Host "[OK] Created output/ directory" -ForegroundColor Green
}
# ── Done ──────────────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "=== Setup Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "To activate the environment in future sessions:" -ForegroundColor White
Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host ""
Write-Host "Quick start (CLI):" -ForegroundColor White
Write-Host "  python run_local.py examples/ecommerce.yaml" -ForegroundColor White
Write-Host ""
Write-Host "Quick start (Web UI):" -ForegroundColor White
Write-Host "  .\scripts\windows\dev.ps1" -ForegroundColor White
Write-Host ""

Pop-Location
