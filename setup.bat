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

:: Check if Git is installed (Optional but recommended for the very first clone)
git --version >nul 2>&1
if !errorlevel! neq 0 (
    echo [WARNING] Git is not installed. 
    echo If you downloaded this as a ZIP instead of cloning, that's completely fine!
    echo The new updater.py handles updates without Git.
)

:: Note: setup.bat assumes you already downloaded/cloned the repo and are inside it.
if not exist "continuous_bot.py" (
    echo [ERROR] continuous_bot.py not found.
    echo Please run this script from inside the Polymarket-Copy-Kawa folder!
    pause
    exit /b 1
)

:: Create Virtual Environment
echo [2/4] Creating Python virtual environment...
if not exist "venv\" (
    python -m venv venv
    echo Virtual environment created.
) else (
    echo Virtual environment already exists.
)

:: Install Dependencies
echo [3/4] Installing dependencies...
call venv\Scripts\activate.bat
python -m pip install --upgrade pip
pip install -r requirements.txt
echo Dependencies installed successfully.

:: Setup .env
echo [4/4] Setting up environment variables...
if not exist ".env" (
    copy .env.example .env >nul
    echo Created .env file from .env.example.
    echo.
    echo [!] IMPORTANT [!]
    echo Please edit the .env file with your real FUNDER_ADDRESS and PRIVATE_KEY.
    echo You can use Notepad to edit it: notepad .env
) else (
    echo .env file already exists.
)

echo.
echo ============================================================================
echo   SETUP COMPLETE!
echo ============================================================================
echo.
echo To start the auto-deploy launcher, run:
echo   start.bat
echo.
pause
