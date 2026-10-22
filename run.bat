@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo.
echo   BinaryRepair MVP - GUI (demo data)
echo   Open http://127.0.0.1:8123
echo   Press Ctrl+C to stop
echo.
".venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8123
pause
