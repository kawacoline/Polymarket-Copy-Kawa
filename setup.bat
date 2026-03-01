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
    echo [1/4] Cloning repository...
    git clone https://github.com/kawacoline/Polymarket-Copy-Kawa.git
    cd Polymarket-Copy-Kawa
) else (
    echo [1/4] Repository already present.
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
echo   python launcher.py
echo.
pause
