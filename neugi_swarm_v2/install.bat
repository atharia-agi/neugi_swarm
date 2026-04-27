@echo off
setlocal enabledelayedexpansion

echo =========================================
echo   NEUGI Swarm V2 - Windows Installer
echo =========================================

REM Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Error: Python is not installed or not in PATH
    echo Please install Python 3.10 or higher from https://www.python.org/downloads/
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo Checking Python version...
for /f "tokens=2" %%I in ('python --version 2^>^&1') do set PYTHON_VERSION=%%I
echo Found Python %PYTHON_VERSION%

REM Set installation directory
set "NEUGI_INSTALL_DIR=%USERPROFILE%\.neugi"
if not "%NEUGI_INSTALL_DIR%"=="" set "NEUGI_INSTALL_DIR=%NEUGI_INSTALL_DIR%"

echo Installing to: %NEUGI_INSTALL_DIR%

REM Create installation directory
if not exist "%NEUGI_INSTALL_DIR%" mkdir "%NEUGI_INSTALL_DIR%"
cd /d "%NEUGI_INSTALL_DIR%"

REM Create virtual environment
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

echo.
echo =========================================
echo   NEUGI Swarm V2 installed successfully!
echo =========================================
echo.
echo Quick start:
echo   neugi init        - Initialize configuration
echo   neugi start       - Start the gateway
echo   neugi status      - Check status
echo.
echo Documentation: https://docs.neugi.ai
echo.
pause
