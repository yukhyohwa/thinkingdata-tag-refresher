@echo off
:: ============================================================
:: FiveCross TA Tag Refresher
:: Designed for Windows Task Scheduler
:: ============================================================

:: Change to the project directory (using the directory this .bat lives in)
cd /d "%~dp0"

:: Activate the virtual environment (if it exists)
if exist "venv\Scripts\activate.bat" (
    call venv\Scripts\activate.bat
)

:: Run the refresh script (headless mode — no visible browser window)
python refresh_tag.py

:: Log the exit code
echo Exit code: %ERRORLEVEL%

:: Optional: pause only when run interactively (not in Task Scheduler)
:: Uncomment the next line if you want to see output when double-clicking the .bat
:: pause
