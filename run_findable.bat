@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo               STARTING FINDABLE
echo     "Toffee isn't a colour. Delta E 1.8 is."
echo ===================================================

cd /d "%~dp0"

:: 1. Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python is not found on your PATH.
    echo Please install Python 3.11+ from https://www.python.org/
    pause
    exit /b 1
)

:: 2. Check Virtual Environment
if not exist ".venv\Scripts\activate.bat" (
    echo [*] Creating virtual environment (.venv)...
    python -m venv .venv
    if errorlevel 1 (
        echo [ERROR] Failed to create virtual environment.
        pause
        exit /b 1
    )
)

echo [*] Activating virtual environment...
call .venv\Scripts\activate.bat

:: 3. Install requirements if uvicorn is missing
python -c "import uvicorn, fastapi, sqlmodel" >nul 2>&1
if errorlevel 1 (
    echo [*] Installing dependencies from requirements.txt...
    pip install -r requirements.txt
    if errorlevel 1 (
        echo [ERROR] Failed to install requirements.
        pause
        exit /b 1
    )
)

:: 4. Launch FastAPI Application
echo.
echo ===================================================
echo  Findable Web Service is launching!
echo  Open your browser to:
echo  - Judges Guide:      http://localhost:8000/judges
echo  - Seller Studio:     http://localhost:8000/studio
echo  - AI Shopping Agent: http://localhost:8000/agent
echo  - Dashboard:         http://localhost:8000/dashboard
echo ===================================================
echo.

uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

pause

