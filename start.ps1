# One-click launcher (PowerShell).
# Usage: open a terminal in this folder and run  .\start.ps1

$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $project

# Random one-time local session token; the printed URL carries it once.
$rng = New-Object System.Security.Cryptography.RNGCryptoServiceProvider
$bytes = New-Object byte[] 24
$rng.GetBytes($bytes)
$token = [Convert]::ToBase64String($bytes).Replace("+", "-").Replace("/", "_").TrimEnd("=")
$env:BINARYREPAIR_SESSION_TOKEN = $token

Write-Host ""
Write-Host " BinaryRepair MVP - GUI (local session)" -ForegroundColor Cyan
Write-Host " Open: http://127.0.0.1:8123/?token=$token" -ForegroundColor Green
Write-Host " Press Ctrl+C to stop" -ForegroundColor DarkGray
Write-Host ""

& "$project\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8123
