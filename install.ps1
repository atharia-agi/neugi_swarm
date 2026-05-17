$ErrorActionPreference = "Stop"

Write-Host "NEUGI Swarm v2 Installer"
Write-Host "========================"
Write-Host ""

$repoUrl = "https://github.com/atharia-agi/neugi_swarm.git"
$installDir = if ($env:NEUGI_INSTALL_DIR) { $env:NEUGI_INSTALL_DIR } else { Join-Path $env:USERPROFILE "neugi_swarm" }

if (Test-Path (Join-Path $installDir ".git")) {
    Write-Host "Updating existing installation..."
    Push-Location $installDir
    git pull origin master
    Pop-Location
} else {
    Write-Host "Cloning repository..."
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

Write-Host "Running v2 installer..."
& (Join-Path $installDir "neugi_swarm_v2\install.ps1")
