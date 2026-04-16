@echo off
:: ============================================================
:: FiveCross TA Tag Refresher — Setup Script
:: Run this ONCE to create venv and install dependencies
:: ============================================================
cd /d "%~dp0"

echo [1/3] Creating virtual environment...
python -m venv venv

echo [2/3] Installing dependencies...
call venv\Scripts\activate.bat
pip install -r requirements.txt
playwright install chromium

echo [3/3] Setup complete!
echo.
echo To test the script, run:
echo   venv\Scripts\python.exe main.py --show
echo.
echo To force a fresh login (clears saved session):
echo   venv\Scripts\python.exe main.py --login --show
echo.
pause
