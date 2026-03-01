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

:: Run the launcher using the virtual environment's python directly
:: This avoids activate.bat which hardcodes absolute paths and breaks if the folder moves
echo Starting the auto-updater and bot...
venv\Scripts\python.exe launcher.py

pause
