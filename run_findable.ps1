# Findable Launcher for PowerShell
Write-Host "===================================================" -ForegroundColor Cyan
Write-Host "              STARTING FINDABLE" -ForegroundColor Cyan
Write-Host '    "Toffee isn''t a colour. Delta E 1.8 is."' -ForegroundColor Yellow
Write-Host "===================================================" -ForegroundColor Cyan

Set-Location -Path $PSScriptRoot

# 1. Check Python
try {
    $pythonVersion = python --version 2>&1
    Write-Host "[*] Found $pythonVersion" -ForegroundColor Green
} catch {
    Write-Host "[ERROR] Python is not found on PATH. Please install Python 3.11+." -ForegroundColor Red
    exit 1
}

# 2. Check Virtual Environment
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "[*] Creating virtual environment (.venv)..." -ForegroundColor Yellow
    python -m venv .venv
}

Write-Host "[*] Activating virtual environment..." -ForegroundColor Yellow
& ".venv\Scripts\Activate.ps1"

# 3. Check dependencies
try {
    python -c "import uvicorn, fastapi, sqlmodel" 2>$null
    if ($LASTEXITCODE -ne 0) { throw "Missing packages" }
} catch {
    Write-Host "[*] Installing required dependencies..." -ForegroundColor Yellow
    pip install -r requirements.txt
}

# 4. Launch FastAPI
Write-Host ""
Write-Host "===================================================" -ForegroundColor Green
Write-Host " Findable Web Service is launching!" -ForegroundColor Green
Write-Host " Open your browser to:"
Write-Host " - Judges Guide:      http://localhost:8000/judges" -ForegroundColor Cyan
Write-Host " - Seller Studio:     http://localhost:8000/studio" -ForegroundColor Cyan
Write-Host " - AI Shopping Agent: http://localhost:8000/agent" -ForegroundColor Cyan
Write-Host " - Dashboard:         http://localhost:8000/dashboard" -ForegroundColor Cyan
Write-Host "===================================================" -ForegroundColor Green
Write-Host ""

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

