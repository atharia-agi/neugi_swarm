@echo off
setlocal enabledelayedexpansion

echo =========================================
echo   NEUGI Swarm V2.1.3 - Windows Installer
echo =========================================

REM Check Python installation
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not installed or not in PATH
    echo.
    echo Please install Python 3.10+ from https://www.python.org/downloads/
    echo IMPORTANT: Check "Add Python to PATH" during installation!
    echo.
    start https://www.python.org/downloads/windows/
    pause
    exit /b 1
)

echo [OK] Python found
for /f "tokens=2" %%I in ('python --version 2^>^&1') do set PYTHON_VERSION=%%I
echo        Version: %PYTHON_VERSION%

REM Check Ollama installation
ollama --version >nul 2>&1
if %errorlevel% neq 0 (
    echo.
    echo [WARN] Ollama not found. NEUGI needs Ollama for local AI.
    echo.
    echo How would you like to install Ollama?
    echo   1. Auto-install via winget (recommended)
    echo   2. Open browser to download page
    echo   3. Skip (I'll use cloud API instead)
    echo.
    set /p OLLAMA_CHOICE="Choice (1/2/3): "
    
    if "!OLLAMA_CHOICE!"=="1" (
        winget --version >nul 2>&1
        if %errorlevel% equ 0 (
            echo Installing Ollama via winget...
            winget install Ollama.Ollama --accept-package-agreements --accept-source-agreements
            echo [OK] Ollama installed. Please restart your terminal after this install.
        ) else (
            echo [ERROR] winget not available. Opening browser instead...
            start https://ollama.com/download/windows
        )
    ) else if "!OLLAMA_CHOICE!"=="2" (
        start https://ollama.com/download/windows
        echo Please install Ollama, then press any key to continue...
        pause >nul
    ) else (
        echo [INFO] Skipping Ollama. You can configure cloud API later with: neugi wizard
    )
) else (
    echo [OK] Ollama found
)

REM Check Git (needed for clone)
git --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [WARN] Git not found. Installing via winget...
    winget install Git.Git --accept-package-agreements --accept-source-agreements 2>nul
)

REM Set installation directory
set "INSTALL_DIR=%USERPROFILE%\neugi_swarm"
if defined NEUGI_DIR set "INSTALL_DIR=%NEUGI_DIR%"

echo.
echo Installing NEUGI to: %INSTALL_DIR%

REM Clone or update repository
if not exist "%INSTALL_DIR%\.git" (
    echo Cloning repository...
    git clone https://github.com/atharia-agi/neugi_swarm.git "%INSTALL_DIR%"
    if %errorlevel% neq 0 (
        echo [ERROR] Failed to clone repository
        pause
        exit /b 1
    )
) else (
    echo Updating existing installation...
    cd /d "%INSTALL_DIR%"
    git pull
)

cd /d "%INSTALL_DIR%\neugi_swarm_v2"

REM Create virtual environment
if not exist "venv" (
    echo Creating virtual environment...
    python -m venv venv
)

REM Activate and install
call venv\Scripts\activate.bat
python -m pip install --upgrade pip -q
pip install -e ".[dev]" -q

REM Create neugi command shortcut
set "NEUGI_CMD=%USERPROFILE%\AppData\Local\Microsoft\WindowsApps\neugi.cmd"
(
    echo @echo off
    echo call "%INSTALL_DIR%\neugi_swarm_v2\venv\Scripts\activate.bat"
    echo python -m neugi_swarm_v2.cli.cli %%*
) > "%NEUGI_CMD%"

echo.
echo =========================================
echo   NEUGI v2.1.3 installed successfully!
echo =========================================
echo.
echo Quick start:
echo   neugi wizard      - Interactive setup (recommended)
echo   neugi rescue      - Fix issues automatically
echo   neugi chat        - Start chatting
echo   neugi status      - Check system health
echo.
echo Note: If Ollama was just installed, restart your terminal first.
echo.
pause
