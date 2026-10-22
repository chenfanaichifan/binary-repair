# Start the GUI on the loopback interface.
# Usage: right-click the project folder -> "Open in Terminal" -> .\start.ps1

$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $project

Write-Host ""
Write-Host " BinaryRepair MVP - GUI (demo data)" -ForegroundColor Cyan
Write-Host " Open http://127.0.0.1:8123" -ForegroundColor Green
Write-Host " Press Ctrl+C to stop" -ForegroundColor DarkGray
Write-Host ""

& "$project\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8123
