@echo off
setlocal enabledelayedexpansion

echo ============================================================================
echo   Polymarket Copy Trading Bot - Initial Windows VPS Setup
echo ============================================================================
echo.

:: Check if Python is installed
python --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Python is not installed or not in PATH.
    echo Please install Python 3.9+ from python.org and ensure "Add to PATH" is checked.
    pause
    exit /b 1
)

:: Check if Node.js is installed (Required for Scraper)
node --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [WARNING] Node.js is not installed.
    echo The "Enrich Stats" and Scraper features will NOT work without Node.js.
    echo Please install Node.js from nodejs.org if you need these features.
) else (
    echo Node.js version:
    node --version
)

:: Check if Git is installed
git --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [ERROR] Git is not installed or not in PATH.
    echo Please install Git for Windows from git-scm.com.
    pause
    exit /b 1
)

:: Clone the repo if we aren't already in it
if not exist "continuous_bot.py" (
    echo [1/5] Cloning repository...
    git clone https://github.com/kawacoline/Polymarket-Copy-Kawa.git
    cd Polymarket-Copy-Kawa
) else (
    echo [1/5] Repository already present.
)

:: Create Virtual Environment
echo [2/5] Creating Python virtual environment...
if not exist "venv\" (
    python -m venv venv
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)

:: Install Python Dependencies
echo [3/5] Installing Python dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
echo Python dependencies installed successfully.

:: Install Scraper Dependencies (Node.js)
echo [4/5] Installing Scraper dependencies (Node.js)...
if exist "polymarket-profitablewallets-scrapper\package.json" (
    cd polymarket-profitablewallets-scrapper
    call npm install
    if !errorlevel! neq 0 (
        echo [WARNING] npm install failed. Check your internet connection or Node installation.
    ) else (
        echo Scraper dependencies installed successfully.
    )
    cd ..
) else (
    echo [ERROR] Scraper directory or package.json not found.
)

:: Setup .env
echo [5/5] Setting up environment variables...
if not exist ".env" (
    copy .env.example .env >nul
    echo Created .env file from .env.example.
) else (
    echo .env file already exists.
)

:: Setup Scraper .env
if exist "polymarket-profitablewallets-scrapper\" (
    if not exist "polymarket-profitablewallets-scrapper\.env" (
        copy "polymarket-profitablewallets-scrapper\.env.example" "polymarket-profitablewallets-scrapper\.env" >nul
        echo Created scraper .env file from example.
    )
)

echo.
echo ============================================================================
echo   SETUP COMPLETE!
echo ============================================================================
echo.
echo [!] IMPORTANT [!]
echo 1. Edit the .env folder in BOTH the root and scraper folder with your keys.
echo 2. To start the auto-deploy launcher, run: start.bat
echo.
pause
