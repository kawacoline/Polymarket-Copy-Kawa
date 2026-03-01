import os
import sys
import time
import subprocess

# ============================================================================
# Polymarket Copy Trading Bot - Cross-Platform Auto-Deploy Launcher
# ============================================================================
# This script runs on your Windows (or Linux/Mac) VPS and:
#   1. Pulls latest code from GitHub automatically every 30s
#   2. Installs/updates dependencies
#   3. Launches the bot + web GUI
#   4. Auto-restarts on crashes
#   5. Watches for new pushes and hot-reloads
#
# SETUP (run once on your VPS):
#   1. Install Git and Python on your VPS
#   2. git clone https://github.com/kawacoline/Polymarket-Copy-Kawa.git
#   3. cd Polymarket-Copy-Kawa
#   4. copy .env.example .env  (and edit .env with your real keys)
#   5. python launcher.py
# ============================================================================

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
BRANCH = "main"
CHECK_INTERVAL = 30  # seconds between git pull checks
BOT_SCRIPT = "web_gui.py"
VENV_DIR = "venv"

# Determine python executable based on OS
if os.name == 'nt':  # Windows
    PYTHON_EXE = os.path.join(REPO_DIR, VENV_DIR, "Scripts", "python.exe")
    PIP_EXE = os.path.join(REPO_DIR, VENV_DIR, "Scripts", "pip.exe")
else:  # Linux/Mac
    PYTHON_EXE = os.path.join(REPO_DIR, VENV_DIR, "bin", "python")
    PIP_EXE = os.path.join(REPO_DIR, VENV_DIR, "bin", "pip")

def log(msg):
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

def run_cmd(cmd, quiet=False):
    if quiet:
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, cwd=REPO_DIR)
    else:
        subprocess.run(cmd, cwd=REPO_DIR)

def get_cmd_output(cmd):
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_DIR, check=True)
        return result.stdout.strip()
    except Exception as e:
        return ""

def setup_env():
    if not os.path.exists(VENV_DIR):
        log("Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", VENV_DIR], cwd=REPO_DIR)
    
    log("Installing/Updating dependencies...")
    run_cmd([PYTHON_EXE, "-m", "pip", "install", "-r", "requirements.txt", "--upgrade", "-q"])

def main():
    print("="*60)
    print("🚀 Auto-Deploy Launcher Started")
    print(f"   OS:         {'Windows' if os.name == 'nt' else 'Linux/Mac'}")
    print(f"   Repo:       {REPO_DIR}")
    print(f"   Branch:     {BRANCH}")
    print(f"   Interval:   {CHECK_INTERVAL}s")
    print("="*60)
    
    os.chdir(REPO_DIR)
    setup_env()
    
    log("Performing initial git pull...")
    run_cmd(["git", "pull", "origin", BRANCH], quiet=True)
    
    bot_process = None
    
    def start_bot():
        nonlocal bot_process
        log(f"Starting {BOT_SCRIPT}...")
        bot_process = subprocess.Popen([PYTHON_EXE, BOT_SCRIPT], cwd=REPO_DIR)
        
    def stop_bot():
        nonlocal bot_process
        if bot_process and bot_process.poll() is None:
            log("Stopping bot...")
            bot_process.terminate()
            try:
                bot_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                bot_process.kill()
                
    start_bot()
    
    try:
        log(f"Watching for git pushes every {CHECK_INTERVAL}s... (Press Ctrl+C to stop)")
        while True:
            time.sleep(CHECK_INTERVAL)
            
            # Check if crashed
            if bot_process.poll() is not None:
                log("Bot process died! Restarting...")
                start_bot()
                continue
                
            # Check git for new code
            run_cmd(["git", "fetch", "origin", BRANCH], quiet=True)
            local_rev = get_cmd_output(["git", "rev-parse", "HEAD"])
            remote_rev = get_cmd_output(["git", "rev-parse", f"origin/{BRANCH}"])
            
            if local_rev and remote_rev and local_rev != remote_rev:
                log("New code detected! Pulling latest...")
                run_cmd(["git", "pull", "origin", BRANCH], quiet=True)
                
                log("Updating dependencies...")
                run_cmd([PYTHON_EXE, "-m", "pip", "install", "-r", "requirements.txt", "--upgrade", "-q"])
                
                stop_bot()
                start_bot()
                
    except KeyboardInterrupt:
        print("")
        log("Launcher stopped by user. Shutting down...")
        stop_bot()
        sys.exit(0)

if __name__ == "__main__":
    main()
