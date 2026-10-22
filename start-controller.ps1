# Start Member 1's final controller from a fixed worktree of origin/main.
# Usage: .\start-controller.ps1
# The GUI is separate: .\start.ps1 (http mode points here by default in docs).

$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $project
$env:GIT_TERMINAL_PROMPT = "0"

$gitCommand = Get-Command git -ErrorAction SilentlyContinue
$git = ""
if ($gitCommand) { $git = $gitCommand.Source }
if (-not $git) {
    $git = "C:\Users\linyz\AppData\Local\dshtools\PortableGit\cmd\git.exe"
}
if (-not (Test-Path $git)) {
    throw "git not found. Install Git or set the portable Git path in this script."
}

$worktree = Join-Path (Split-Path -Parent $project) "binaryrepair-controller"
$dataDir = Join-Path $project "var\controller"
New-Item -ItemType Directory -Force $dataDir | Out-Null

if (Test-Path (Join-Path $worktree ".git")) {
    Write-Host "Updating controller worktree ..." -ForegroundColor DarkGray
    & $git -C $worktree fetch origin main
    & $git -C $worktree -c advice.detachedHead=false checkout --detach origin/main
} else {
    Write-Host "Creating controller worktree at $worktree ..." -ForegroundColor DarkGray
    & $git fetch origin main
    & $git worktree add --detach $worktree origin/main
}

$env:BINARYREPAIR_DATA_DIR = $dataDir
Write-Host ""
Write-Host " BinaryRepair Controller (Member 1, origin/main)" -ForegroundColor Cyan
Write-Host " Health: http://127.0.0.1:8000/healthz" -ForegroundColor Green
Write-Host " Data:   $dataDir" -ForegroundColor DarkGray
Write-Host " Press Ctrl+C to stop" -ForegroundColor DarkGray
Write-Host ""

$python = Join-Path $project ".venv\Scripts\python.exe"
Push-Location $worktree
try {
    & $python -m uvicorn app.controller_api:app --host 127.0.0.1 --port 8000
} finally {
    Pop-Location
}
