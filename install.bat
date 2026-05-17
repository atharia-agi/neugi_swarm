@echo off
setlocal
REM NEUGI Swarm v2 - Root Install Wrapper
REM Delegates to neugi_swarm_v2\install.bat

echo NEUGI Swarm v2 Installer
echo ========================
echo.

set "REPO_URL=https://github.com/atharia-agi/neugi_swarm.git"
set "INSTALL_DIR=%USERPROFILE%\neugi_swarm"
if defined NEUGI_INSTALL_DIR set "INSTALL_DIR=%NEUGI_INSTALL_DIR%"

if exist "%INSTALL_DIR%\.git" (
    echo Updating existing installation...
    cd /d "%INSTALL_DIR%"
    git pull origin master
) else (
    echo Cloning repository...
    if exist "%INSTALL_DIR%" (
        dir /a /b "%INSTALL_DIR%" 2>nul | findstr . >nul
        if not errorlevel 1 (
            echo [ERROR] Install directory exists but is not a NEUGI git repo: %INSTALL_DIR%
            echo Set NEUGI_INSTALL_DIR to an empty directory or remove the directory first.
            exit /b 1
        )
    )
    git clone "%REPO_URL%" "%INSTALL_DIR%"
    cd /d "%INSTALL_DIR%"
)

echo Running v2 installer...
call neugi_swarm_v2\install.bat
