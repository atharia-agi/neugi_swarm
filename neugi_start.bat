@echo off
:: NEUGI SOVEREIGN STARTUP SCRIPT
:: Automatically launched by Windows Startup

set "NEUGI_DIR=%USERPROFILE%\neugi"
cd /d "%NEUGI_DIR%"

echo [SOVEREIGN] Initiating Neural Handshake...

:: 1. Start Ollama (Silent)
echo [SOVEREIGN] Pinging Ollama...
start /B ollama serve > nul 2>&1

:: 2. Start NEUGI Engine (Background)
echo [SOVEREIGN] Awakening Swarm Engine...
if not exist logs mkdir logs
start /B python neugi_swarm.py > logs\autoboot.log 2>&1

:: 3. Launch Dashboard
echo [SOVEREIGN] Linking to Dashboard...
timeout /t 3 /nobreak > nul
start http://localhost:19888

echo [SOVEREIGN] System is ONLINE.
exit
