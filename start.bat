@echo off
setlocal enabledelayedexpansion
echo =======================================================
echo   Polymarket Bot ^& Scraper Auto-Launcher
echo =======================================================
echo.

:: Check for virtual environment
if not exist "venv\Scripts\activate.bat" (
    echo [ERROR] Virtual environment not found in "venv\" folder.
    echo Please run setup.bat first.
    pause
    exit /b 1
)

echo Starting Copy-Trading Bot ^& Profitable Wallets Scraper...
venv\Scripts\python.exe launcher.py
pause
