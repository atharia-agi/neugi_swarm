@echo off
:: NEUGI SOVEREIGN STARTUP SCRIPT
:: Refactored for Conflict Protection

set "NEUGI_DIR=%USERPROFILE%\neugi"
cd /d "%NEUGI_DIR%"

echo [SOVEREIGN] Initiating Neural Handshake...

:: 1. Check/Start Ollama
echo [SOVEREIGN] Pinging Ollama...
tasklist /FI "IMAGENAME eq ollama.exe" 2>NUL | find /I /N "ollama.exe">NUL
if "%ERRORLEVEL%"=="0" (
    echo [SOVEREIGN] Ollama is already active.
) else (
    echo [SOVEREIGN] Powering up Ollama...
    start /B ollama serve > nul 2>&1
)

:: 2. Check/Start NEUGI Engine (Using Port 19888 detection)
echo [SOVEREIGN] Awakening Swarm Engine...
netstat -ano | findstr :19888 >nul
if "%ERRORLEVEL%"=="0" (
    echo [SOVEREIGN] NEUGI engine already running on port 19888.
) else (
    echo [SOVEREIGN] Deploying engine...
    if not exist logs mkdir logs
    :: Leverage existing CLI wrapper for consistency
    if exist neugi.bat (
        call neugi.bat start
    ) else (
        start /B python neugi_swarm.py > logs\neugi.log 2>&1
    )
)

:: 3. Launch Dashboard
echo [SOVEREIGN] Linking to Dashboard...
timeout /t 2 /nobreak > nul
start http://localhost:19888

echo [SOVEREIGN] System is ONLINE.
exit
