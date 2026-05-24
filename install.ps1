$ErrorActionPreference = "Stop"

$ascii = @'
 _   _ _____ _   _  ____ ___
| \ | | ____| | | |/ ___|_ _|
|  \| |  _| | | | | |  _ | |
| |\  | |___| |_| | |_| || |
|_| \_|_____|\___/ \____|___|
'@

Write-Host $ascii -ForegroundColor Cyan
Write-Host "NEUGI Installer Safety Notice" -ForegroundColor Yellow
Write-Host "- This framework can execute autonomous and tool-driven actions." -ForegroundColor DarkYellow
Write-Host "- Outputs can be wrong; keep human oversight and staged rollout." -ForegroundColor DarkYellow
Write-Host "- Use implies acceptance of Terms/Privacy at https://neugi.com." -ForegroundColor DarkYellow
Write-Host ""
$consent = Read-Host "Continue installer bootstrap? [y/N]"
if ($consent -notmatch "^[Yy]$") {
    Write-Host "[NEUGI] Installation cancelled by user." -ForegroundColor Yellow
    exit 0
}

$scriptUrl = "https://neugi.com/install.ps1"
$tempScript = Join-Path $env:TEMP "neugi_install_latest.ps1"

Write-Host "[NEUGI] Fetching installer from $scriptUrl ..."
Invoke-WebRequest -Uri $scriptUrl -OutFile $tempScript -UseBasicParsing

Write-Host "[NEUGI] Running latest installer..."
& powershell -ExecutionPolicy Bypass -File $tempScript
