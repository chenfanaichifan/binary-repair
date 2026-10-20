@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo   BinaryRepair MVP - GUI 骨架（演示数据）
echo   打开浏览器访问：http://127.0.0.1:8123
echo   按 Ctrl+C 停止
echo.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8123
pause
