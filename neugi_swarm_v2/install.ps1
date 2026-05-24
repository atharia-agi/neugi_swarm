$ErrorActionPreference = "Stop"

function Show-InstallBanner {
    $ascii = @'
 _   _ _____ _   _  ____ ___
| \ | | ____| | | |/ ___|_ _|
|  \| |  _| | | | | |  _ | |
| |\  | |___| |_| | |_| || |
|_| \_|_____|\___/ \____|___|
'@
    Write-Host $ascii -ForegroundColor Cyan
    Write-Host "NEUGI Swarm v2.1.3 Installer" -ForegroundColor White
    Write-Host ""
}

function Confirm-InstallerRisk {
    Write-Host "Safety Notice (Beta / Experimental)" -ForegroundColor Yellow
    Write-Host "- NEUGI can run autonomous and tool-executing agent workflows." -ForegroundColor DarkYellow
    Write-Host "- Actions may affect files, systems, and connected provider resources." -ForegroundColor DarkYellow
    Write-Host "- Keep human approval controls enabled for high-impact operations." -ForegroundColor DarkYellow
    Write-Host "- Review terms and privacy: https://neugi.com/terms.html and https://neugi.com/privacy.html" -ForegroundColor DarkYellow
    Write-Host ""
    $answer = Read-Host "Do you want to continue installation? [y/N]"
    return $answer -match "^[Yy]$"
}

Show-InstallBanner
if (-not (Confirm-InstallerRisk)) {
    Write-Host "[NEUGI] Installation cancelled by user." -ForegroundColor Yellow
    exit 0
}

Write-Host "========================================="
Write-Host "  NEUGI Swarm V2.1.3 - Windows Installer"
Write-Host "========================================="

$repoUrl = "https://github.com/atharia-agi/neugi_swarm.git"
$installDir = if ($env:NEUGI_INSTALL_DIR) { $env:NEUGI_INSTALL_DIR } else { Join-Path $env:USERPROFILE "neugi_swarm" }
$packageDir = Join-Path $installDir "neugi_swarm_v2"

function Test-Command($name) {
    return [bool](Get-Command $name -ErrorAction SilentlyContinue)
}

Write-Host ""
Write-Host "[1/6] Checking Python..."
if (-not (Test-Command "python")) {
    Write-Host "[ERROR] Python 3.10+ is required."
    Write-Host "Install it from https://www.python.org/downloads/ and enable 'Add Python to PATH'."
    Start-Process "https://www.python.org/downloads/windows/"
    exit 1
}
python --version

Write-Host ""
Write-Host "[2/6] Checking Git..."
if (-not (Test-Command "git")) {
    if (Test-Command "winget") {
        Write-Host "[INFO] Installing Git with winget..."
        winget install Git.Git --accept-package-agreements --accept-source-agreements
    } else {
        Write-Host "[ERROR] Git is required. Install it from https://git-scm.com/download/win"
        Start-Process "https://git-scm.com/download/win"
        exit 1
    }
}

Write-Host ""
Write-Host "[3/6] Checking Ollama..."
if (-not (Test-Command "ollama")) {
    Write-Host "[WARN] Ollama not found. You can still use cloud providers via 'neugi wizard'."
    $choice = Read-Host "Install Ollama with winget now? [Y/n]"
    if ($choice -notmatch "^[Nn]$") {
        if (Test-Command "winget") {
            winget install Ollama.Ollama --accept-package-agreements --accept-source-agreements
            Write-Host "[OK] Ollama installed. Restart the terminal if the ollama command is not visible yet."
        } else {
            Start-Process "https://ollama.com/download/windows"
        }
    }
}

Write-Host ""
Write-Host "[4/6] Installing repository to $installDir"
if (Test-Path (Join-Path $installDir ".git")) {
    Push-Location $installDir
    git pull origin master
    Pop-Location
} else {
    if (-not (Test-Path $installDir)) {
        New-Item -ItemType Directory -Path $installDir | Out-Null
    }
    if ((Get-ChildItem -Path $installDir -Force | Select-Object -First 1)) {
        Write-Host "[ERROR] Install directory exists but is not a NEUGI git repo: $installDir"
        Write-Host "Set NEUGI_INSTALL_DIR to an empty directory or remove the directory first."
        exit 1
    }
    git clone $repoUrl $installDir
}

Write-Host ""
Write-Host "[5/6] Creating virtual environment and installing package..."
Push-Location $packageDir
if (-not (Test-Path "venv")) {
    python -m venv venv
}
& ".\venv\Scripts\python.exe" -m pip install --upgrade pip -q
& ".\venv\Scripts\python.exe" -m pip install -e ".[dev]" -q
Pop-Location

Write-Host ""
Write-Host "[6/6] Creating neugi command..."
$cmdDir = Join-Path $env:LOCALAPPDATA "Microsoft\WindowsApps"
if (-not (Test-Path $cmdDir)) {
    New-Item -ItemType Directory -Path $cmdDir | Out-Null
}
$cmdPath = Join-Path $cmdDir "neugi.cmd"
@"
@echo off
call "$packageDir\venv\Scripts\activate.bat"
python -m neugi_swarm_v2.cli.cli %*
"@ | Set-Content -Path $cmdPath -Encoding ASCII

Write-Host ""
Write-Host "========================================="
Write-Host "  NEUGI v2.1.3 installed successfully!"
Write-Host "========================================="
Write-Host ""
Write-Host "Quick start:"
Write-Host "  neugi quickstart  # Recommended: auto-fix, smoke test, and start"
Write-Host "  neugi wizard      # Pick provider, enter API key, choose model"
Write-Host "  neugi chat        # Start chatting"
Write-Host "  neugi status      # Check system health"
Write-Host ""
Write-Host "If 'neugi' is not found, open a new terminal or run:"
Write-Host "  $cmdPath wizard"
Write-Host ""

$runQuickstart = Read-Host "Run 'neugi quickstart' now? [Y/n]"
if ($runQuickstart -notmatch "^[Nn]$") {
    Write-Host "[INFO] Running quickstart..."
    $nonInteractive = Read-Host "Run non-interactive mode (best for CI/server)? [y/N]"
    if ($nonInteractive -match "^[Yy]$") {
        & $cmdPath quickstart --non-interactive --json
    } else {
        & $cmdPath quickstart
    }
}
