@echo off
setlocal enabledelayedexpansion
echo =======================================================
echo   Polymarket Bot ^& Scraper Auto-Launcher
echo =======================================================
echo.
echo 1) Start Copy-Trading Bot (Dashboard)
echo 2) Start Profitable Wallets Scraper
echo 3) Exit
echo.
set /p choice="Select an option (1-3): "

if "%choice%"=="1" (
    :: Check for virtual environment
    if not exist "venv\Scripts\activate.bat" (
        echo [ERROR] Virtual environment not found in "venv\" folder.
        echo Please run setup.bat first.
        pause
        exit /b 1
    )
    echo Starting the auto-updater and bot...
    venv\Scripts\python.exe launcher.py
)

if "%choice%"=="2" (
    if exist "polymarket-profitablewallets-scrapper\start.bat" (
        cd polymarket-profitablewallets-scrapper
        call start.bat
        cd ..
    ) else (
        echo [ERROR] Scraper start.bat not found.
        pause
    )
)

if "%choice%"=="3" exit /b 0

pause
