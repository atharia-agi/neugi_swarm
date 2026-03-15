@echo off
:: NEUGI CLI Wrapper for Windows
set "NEUGI_DIR=%USERPROFILE%\neugi"

if "%1"=="start" (
    netstat -ano | findstr :19888 >nul
    if "%ERRORLEVEL%"=="0" (
        echo [WARN] NEUGI is already running on port 19888.
        exit /b
    )
    echo [INFO] Starting NEUGI Swarm...
    cd /d "%NEUGI_DIR%"
    start /B python neugi_swarm.py > logs\neugi.log 2>&1
    echo NEUGI started.
    exit /b
)

if "%1"=="stop" (
    echo [INFO] Stopping NEUGI Swarm...
    taskkill /F /IM python.exe /FI "WINDOWTITLE eq neugi_swarm*" >nul 2>&1
    echo NEUGI stopped.
    exit /b
)

if "%1"=="logs" (
    type "%NEUGI_DIR%\logs\neugi.log"
    exit /b
)

if "%1"=="dashboard" (
    start http://localhost:19888
    exit /b
)

if "%1"=="help" (
    cd /d "%NEUGI_DIR%"
    python neugi_assistant.py %*
    exit /b
)

echo NEUGI CLI
echo Commands: start, stop, logs, dashboard, help
