# Start the canonical controller API (app/controller_api.py) on loopback:8000.
# Usage: .\start-controller.ps1
# The GUI is a separate process: .\start.ps1 (its http mode points here by default).
#
# The controller lives in this checkout (main @4107836 added it), so no second
# worktree of origin/main is needed any more. This script used to create one; it
# now serves the same canonical API from the merged tree, which keeps the GUI and
# the controller on one commit.
#
# One canonical data directory: the controller and start-worker.ps1 must use the
# same store, otherwise the worker looks at an empty database. Both default to
# <repo>\var and both honour an explicit BINARYREPAIR_DATA_DIR.

$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $project

$dataDir = if ($env:BINARYREPAIR_DATA_DIR) {
    $env:BINARYREPAIR_DATA_DIR
} else {
    Join-Path $project "var"
}
New-Item -ItemType Directory -Force $dataDir | Out-Null
$env:BINARYREPAIR_DATA_DIR = (Resolve-Path $dataDir).Path

$python = Join-Path $project ".venv\Scripts\python.exe"
if (-not (Test-Path $python)) {
    $python = "python"
}

Write-Host ""
Write-Host " BinaryRepair Controller (app.controller_api:app, canonical)" -ForegroundColor Cyan
Write-Host " Health: http://127.0.0.1:8000/healthz" -ForegroundColor Green
Write-Host " Data:   $dataDir" -ForegroundColor DarkGray
Write-Host " Press Ctrl+C to stop" -ForegroundColor DarkGray
Write-Host ""

& $python -m uvicorn app.controller_api:app --host 127.0.0.1 --port 8000
