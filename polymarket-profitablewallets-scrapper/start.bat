@echo off
echo ============================================================================
echo   Polymarket Profitable Wallets Scraper - Launcher
echo ============================================================================
echo.

node src/index.js watch
if %errorlevel% neq 0 (
    echo.
    echo [ERROR] Scraper crashed or failed to start.
    echo Make sure you have run setup.bat first and configured your .env file.
    pause
)
