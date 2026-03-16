@echo off
setlocal enabledelayedexpansion

echo ============================================================================
echo   Polymarket Profitable Wallets Scraper - Initialization Setup
echo ============================================================================
echo.

:: Check if Node.js is installed
node --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Node.js is not installed or not in PATH.
    echo Please install Node.js from nodejs.org (LTS version recommended).
    pause
    exit /b 1
)

:: Install Dependencies
echo [1/2] Installing dependencies...
npm install
if !errorlevel! neq 0 (
    echo [ERROR] npm install failed.
    pause
    exit /b 1
)
echo Dependencies installed successfully.

:: Setup .env
echo [2/2] Setting up environment variables...
if not exist ".env" (
    copy .env.example .env >nul
    echo Created .env file from .env.example.
    echo.
    echo [!] IMPORTANT [!]
    echo Please edit the .env file with your Polymarket API credentials.
    echo You can use Notepad to edit it: notepad .env
) else (
    echo .env file already exists.
)

echo.
echo ============================================================================
echo   SCRAPER SETUP COMPLETE!
echo ============================================================================
echo.
echo To start the scraper, run:
echo   start.bat
echo.
pause
