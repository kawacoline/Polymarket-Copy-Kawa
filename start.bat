@echo off
echo =======================================================
echo   Polymarket Bot Auto-Launcher (with Auto-Update)
echo =======================================================

:: Check for virtual environment
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found in "venv\" folder.
    echo Please run these commands first:
    echo   python -m venv venv
    echo   venv\Scripts\activate
    echo   pip install -r requirements.txt
    pause
    exit /b 1
)

:: Activate venv and run launcher
echo Activating virtual environment...
call venv\Scripts\activate.bat

echo Starting the auto-updater and bot...
python updater.py

pause
