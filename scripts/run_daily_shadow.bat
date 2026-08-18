@echo off
setlocal
cd /d "%~dp0.."

if not exist ".venv\Scripts\python.exe" (
  echo .venv Python executable was not found.
  exit /b 1
)

".venv\Scripts\python.exe" scripts\run_daily_shadow.py

exit /b %errorlevel%
