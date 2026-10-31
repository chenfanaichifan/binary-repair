@echo off
setlocal
set PY=D:\BinRepair\.tmp\venv-int\Scripts\python.exe
set BASE=D:\BinRepair\.tmp\p2-real-2026-10-30
if /I "%BINARYREPAIR_ROUTE%"=="route_a" (
  "%PY%" -m app.services.attempt_writer --input "%BASE%\route-a-input.json" --route route_a --data-dir "%BINARYREPAIR_DATA_DIR%" --job-id "%BINARYREPAIR_JOB_ID%" --run-id "%BINARYREPAIR_RUN_ID%" --attempt-id "%BINARYREPAIR_ATTEMPT_ID%" --out "%BINARYREPAIR_RESULT_PATH%"
) else if /I "%BINARYREPAIR_ROUTE%"=="route_b" (
  "%PY%" -m app.services.attempt_writer --input "%BASE%\route-b-input.json" --route route_b --data-dir "%BINARYREPAIR_DATA_DIR%" --job-id "%BINARYREPAIR_JOB_ID%" --run-id "%BINARYREPAIR_RUN_ID%" --attempt-id "%BINARYREPAIR_ATTEMPT_ID%" --out "%BINARYREPAIR_RESULT_PATH%"
) else (
  echo unknown route "%BINARYREPAIR_ROUTE%" 1>&2
  exit /b 2
)
exit /b %ERRORLEVEL%
