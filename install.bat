@echo off
setlocal enabledelayedexpansion

echo.
echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
echo   DANGER: UNRESTRICTED SYSTEM ACCESS 
echo !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!
echo.
echo NEUGI is an autonomous AI system. By installing, you 
echo give the AI permission to execute system-level 
echo commands on this machine.
echo.
set /p confirm="Do you wish to proceed? (y/n): "
if /i "%confirm%" neq "y" (
    echo [ERROR] Installation aborted.
    pause
    exit /b
)
echo.

:: 1. Check Ollama
where ollama >nul 2>nul
if %ERRORLEVEL% neq 0 (
    echo [ERROR] Ollama not found.
    echo Please install Ollama from https://ollama.com/download/windows
    echo and ensure it is in your system PATH.
    pause
    exit /b
)

:: 2. Pull Model
echo [INFO] Pulling model qwen3.5:cloud...
ollama pull qwen3.5:cloud

:: 3. Setup Directory
set "NEUGI_DIR=%USERPROFILE%\neugi"
if not exist "%NEUGI_DIR%" mkdir "%NEUGI_DIR%"
cd /d "%NEUGI_DIR%"

:: 4. Download files
echo [INFO] Downloading NEUGI repository...
if exist "%NEUGI_DIR%\.git" (
    cd /d "%NEUGI_DIR%"
    git pull origin master
) else (
    git clone https://github.com/atharia-agi/neugi_swarm.git "%NEUGI_DIR%"
    cd /d "%NEUGI_DIR%"
)

echo [INFO] Installing python dependencies...
pip install -r requirements.txt

:: 5. Create config.py
echo # NEUGI SWARM CONFIG > config.py
echo USE_OLLAMA=True >> config.py
echo OLLAMA_URL="http://localhost:11434" >> config.py
echo OLLAMA_MODEL="qwen3.5:cloud" >> config.py
echo MODEL="auto" >> config.py
echo CONTEXT_WINDOW=2048 >> config.py
echo MASTER_KEY="neugi123" >> config.py

if not exist data mkdir data
if not exist models mkdir models
if not exist logs mkdir logs
if not exist workspace\nul mkdir workspace

echo [SUCCESS] NEUGI installed to %NEUGI_DIR%
echo.

:: 6. Run Wizard
echo [INFO] Running Setup Wizard...
python neugi_swarm\neugi_wizard.py

:: 7. Start NEUGI
echo.
echo [INFO] Starting NEUGI Swarm...
start /B python neugi_swarm\neugi_swarm.py > logs\neugi.log 2>&1

echo.
echo ===================================================
echo         NEUGI IS RUNNING!
echo Dashboard: http://localhost:19888
echo ===================================================
echo.
echo You can check the logs in %NEUGI_DIR%\logs\neugi.log
pause
