import os
import sys
import time
import subprocess
import urllib.request
import zipfile
import shutil
from dotenv import load_dotenv

load_dotenv()

# ============================================================================
# Polymarket Copy Trading Bot - Secure ZIP Auto-Updater
# ============================================================================
# No Git login required on the VPS! 
# Uses a GitHub Personal Access Token (PAT) from your .env to securely
# download the latest code as a ZIP file, extract it, and restart the bot.
# ============================================================================

GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
REPO_OWNER = "kawacoline"
REPO_NAME = "Polymarket-Copy-Kawa"
BRANCH = "main"

REPO_DIR = os.path.dirname(os.path.abspath(__file__))
CHECK_INTERVAL = 60  # seconds between checks
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

def setup_env():
    if not os.path.exists(VENV_DIR):
        log("Creating virtual environment...")
        subprocess.run([sys.executable, "-m", "venv", VENV_DIR], cwd=REPO_DIR)
    
    log("Installing/Updating dependencies...")
    subprocess.run([PIP_EXE, "install", "-r", "requirements.txt", "--upgrade", "-q"], cwd=REPO_DIR)

def get_latest_commit_sha():
    if not GITHUB_TOKEN:
        return None
        
    url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/commits/{BRANCH}"
    req = urllib.request.Request(url)
    req.add_header("Authorization", f"token {GITHUB_TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    
    try:
        with urllib.request.urlopen(req) as response:
            import json
            data = json.loads(response.read().decode())
            return data.get("sha")
    except Exception as e:
        log(f"Error checking GitHub API: {e}")
        return None

def download_and_extract_zip():
    if not GITHUB_TOKEN:
        log("ERROR: GITHUB_TOKEN not found in .env. Cannot download update.")
        return False
        
    zip_url = f"https://api.github.com/repos/{REPO_OWNER}/{REPO_NAME}/zipball/{BRANCH}"
    zip_path = os.path.join(REPO_DIR, "update.zip")
    extract_dir = os.path.join(REPO_DIR, "temp_update")
    
    req = urllib.request.Request(zip_url)
    req.add_header("Authorization", f"token {GITHUB_TOKEN}")
    req.add_header("Accept", "application/vnd.github.v3+json")
    
    try:
        log("Downloading latest code zip...")
        with urllib.request.urlopen(req) as response, open(zip_path, 'wb') as out_file:
            shutil.copyfileobj(response, out_file)
            
        log("Extracting code...")
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            zip_ref.extractall(extract_dir)
            
        # The API zip puts things in a subfolder like kawacoline-Polymarket-Copy-Kawa-commitSHA
        extracted_subdirs = os.listdir(extract_dir)
        if len(extracted_subdirs) == 1:
            source_dir = os.path.join(extract_dir, extracted_subdirs[0])
            
            log("Applying updates...")
            for item in os.listdir(source_dir):
                # IMPORTANT: DO NOT overwrite local sensitive files or state!
                if item in [VENV_DIR, ".env", "betting_history.db", "launcher.log", "bot_status.json", "accounts.json", "seen_trades.json", "withdrawals.json", ".env.example"]:
                    continue
                    
                s = os.path.join(source_dir, item)
                d = os.path.join(REPO_DIR, item)
                
                try:
                    if os.path.isdir(s):
                        if os.path.exists(d):
                            shutil.rmtree(d)
                        shutil.copytree(s, d)
                    else:
                        shutil.copy2(s, d)
                except Exception as e:
                    log(f"Warning: Could not copy {item}: {e}")
                    
        # Cleanup
        os.remove(zip_path)
        shutil.rmtree(extract_dir)
        return True
        
    except Exception as e:
        log(f"Error updating: {e}")
        # Cleanup on failure
        if os.path.exists(zip_path): os.remove(zip_path)
        if os.path.exists(extract_dir): shutil.rmtree(extract_dir)
        return False

def main():
    print("="*60)
    print("🚀 Auto-Deploy Launcher (PAT Token Edition)")
    print(f"   OS:         {'Windows' if os.name == 'nt' else 'Linux/Mac'}")
    print(f"   Repo:       {REPO_DIR}")
    print(f"   Interval:   {CHECK_INTERVAL}s")
    print("="*60)
    
    if not GITHUB_TOKEN:
        log("⚠️ WARNING: GITHUB_TOKEN missing from .env!")
        log("   The launcher will run the bot, but cannot fetch automatic updates.")
        log("   To fix: Create a GitHub Personal Access Token (classic, repo scope)")
        log("   and add 'GITHUB_TOKEN=ghp_yourtoken...' to your .env file.")
        log("   Waiting 10 seconds before starting anyway...")
        time.sleep(10)
    
    os.chdir(REPO_DIR)
    setup_env()
    
    bot_process = None
    current_sha = get_latest_commit_sha()
    
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
        log(f"Watching for updates every {CHECK_INTERVAL}s... (Press Ctrl+C to stop)")
        while True:
            time.sleep(CHECK_INTERVAL)
            
            # Restart if crashed
            if bot_process.poll() is not None:
                log("Bot process died! Restarting...")
                start_bot()
                continue
                
            # Check for updates if we have a token
            if GITHUB_TOKEN:
                latest_sha = get_latest_commit_sha()
                if latest_sha and current_sha != latest_sha:
                    log(f"New update found! {latest_sha[:7]}")
                    if download_and_extract_zip():
                        log("Update successful. Restarting bot...")
                        current_sha = latest_sha
                        
                        setup_env()  # Install new requirements if any
                        stop_bot()
                        start_bot()
                
    except KeyboardInterrupt:
        print("")
        log("Launcher stopped by user. Shutting down...")
        stop_bot()
        sys.exit(0)

if __name__ == "__main__":
    main()
