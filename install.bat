@echo off
REM NEUGI Swarm v2 — Root Install Wrapper
REM Delegates to neugi_swarm_v2\install.bat

echo 🦞 NEUGI Swarm v2 Installer
echo ============================
echo.

set REPO_URL=https://github.com/atharia-agi/neugi_swarm.git
set INSTALL_DIR=%USERPROFILE%\neugi_swarm

if exist "%INSTALL_DIR%" (
    echo 📁 Updating existing installation...
    cd /d "%INSTALL_DIR%"
    git pull origin master
) else (
    echo 📥 Cloning repository...
    git clone "%REPO_URL%" "%INSTALL_DIR%"
    cd /d "%INSTALL_DIR%"
)

echo 🚀 Running v2 installer...
call neugi_swarm_v2\install.bat
