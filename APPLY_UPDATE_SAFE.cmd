@echo off
setlocal EnableExtensions
set "SOURCE=%~dp0"
set "TARGET=%~1"
if "%TARGET%"=="" set "TARGET=C:\dev\stock-analytics"

set "DB=%TARGET%\data\stock_analytics.db"
set "BACKUPDIR=%TARGET%\data\backup"

echo [V3.2.1 Phase 5.2 Safe Source Update]
echo Source: %SOURCE%
echo Target: %TARGET%
echo.
echo PRESERVED: data\  .env  results\  .venv*\  .git\
echo Distribution ZIP contains no data directory and no database.
echo.

if not exist "%TARGET%" (
  echo ERROR: target folder does not exist: %TARGET%
  exit /b 2
)

if exist "%DB%" (
  if not exist "%BACKUPDIR%" mkdir "%BACKUPDIR%"
  echo Creating verified pre-update SQLite backup...
  python -c "import sqlite3,datetime,pathlib; src=pathlib.Path(r'%DB%'); d=pathlib.Path(r'%BACKUPDIR%'); stamp=datetime.datetime.now().strftime('%%Y%%m%%d_%%H%%M%%S'); dst=d/f'stock_analytics_{stamp}_pre_update.db'; s=sqlite3.connect(src); t=sqlite3.connect(dst); s.backup(t); t.close(); s.close(); print('Backup:',dst)"
  if errorlevel 1 (
    echo ERROR: DB backup failed. Source update aborted.
    exit /b 3
  )
) else (
  echo WARNING: existing DB not found: %DB%
  echo Source update will continue, but no DB backup was created.
)

robocopy "%SOURCE%" "%TARGET%" /E /R:1 /W:1 ^
  /XD data results .venv .venv312 .git __pycache__ .pytest_cache ^
  /XF .env *.db *.sqlite *.sqlite3 *.zip

set "RC=%ERRORLEVEL%"
if %RC% GEQ 8 (
  echo ERROR: robocopy failed with code %RC%
  exit /b %RC%
)

echo.
echo Update completed. Existing DB/raw/checkpoints/features/labels/.env/results were preserved.
echo Recommended check:
echo   python -m src.main db-health-v321 --benchmark-code 069500
exit /b 0
