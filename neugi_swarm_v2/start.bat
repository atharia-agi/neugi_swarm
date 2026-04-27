@echo off
setlocal enabledelayedexpansion

echo =========================================
echo   NEUGI Swarm V2 - Starting Gateway
echo =========================================

REM Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.10 or higher from https://www.python.org/downloads/
    pause
    exit /b 1
)

REM Create virtual environment if it doesn't exist
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate virtual environment
call venv\Scripts\activate.bat

REM Install dependencies
echo Installing dependencies...
python -m pip install --upgrade pip
pip install -e .

REM Start the gateway
echo.
echo Starting NEUGI Swarm V2 Gateway...
echo =========================================
neugi start

pause
