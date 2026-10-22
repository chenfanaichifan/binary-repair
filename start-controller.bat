# Start the controller from a fixed worktree (cmd wrapper).

@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-controller.ps1"
pause
