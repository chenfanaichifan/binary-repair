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
New-Item -ItemType Directory -Force (Join-Path $project "var") | Out-Null
Set-Content -Path (Join-Path $project "var\session.token") -Value $token -NoNewline
$url = "http://127.0.0.1:8123/?token=$token"

Write-Host ""
Write-Host " BinaryRepair MVP - GUI (local session)" -ForegroundColor Cyan
Write-Host " Open: $url" -ForegroundColor Green
Write-Host " Press Ctrl+C to stop" -ForegroundColor DarkGray
Write-Host ""

# Open the browser once the server has had a moment to start.
Start-Job -ScriptBlock {
    param($target)
    Start-Sleep -Seconds 2
    Start-Process $target
} -ArgumentList $url | Out-Null

& "$project\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8123
