# 一键启动（PowerShell）
# 用法：在项目文件夹里右键“在终端中打开”，执行  .\start.ps1

$ErrorActionPreference = "Stop"
$project = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $project

Write-Host ""
Write-Host " BinaryRepair MVP - GUI 骨架（演示数据）" -ForegroundColor Cyan
Write-Host " 浏览器打开：http://127.0.0.1:8123" -ForegroundColor Green
Write-Host " 按 Ctrl+C 停止" -ForegroundColor DarkGray
Write-Host ""

& "$project\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8123
