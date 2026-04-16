@echo off
:: ============================================================
:: FiveCross TA Tag Refresher
:: Designed for Windows Task Scheduler
:: ============================================================

cd /d "%~dp0"

set PYTHON_EXE=python
if exist "venv\Scripts\python.exe" (
    set PYTHON_EXE=venv\Scripts\python.exe
)

%PYTHON_EXE% main.py

echo Exit code: %ERRORLEVEL%

:: Uncomment to pause when double-clicking (not needed in Task Scheduler)
pause
