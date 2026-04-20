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

set RETURN_CODE=%ERRORLEVEL%
echo Task finished with exit code: %RETURN_CODE%

:: If you want to keep the window open for manual runs, you can use:
:: if "%1" neq "nopause" pause
:: But for scheduled tasks, we should just exit.

exit /b %RETURN_CODE%
