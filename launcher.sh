#!/bin/bash
# ============================================================================
# Polymarket Copy Trading Bot - VPS Auto-Deploy Launcher
# ============================================================================
# This script runs on your VPS and:
#   1. Pulls latest code from GitHub automatically
#   2. Installs/updates dependencies
#   3. Launches the bot + web GUI
#   4. Auto-restarts on crashes
#   5. Watches for new pushes and hot-reloads
#
# SETUP (run once on your VPS):
#   chmod +x launcher.sh
#   git clone https://github.com/kawacoline/Polymarket-Copy-Kawa.git
#   cd Polymarket-Copy-Kawa
#   cp .env.example .env
#   nano .env  # Add your real keys
#   ./launcher.sh
#
# To run in background:
#   nohup ./launcher.sh > launcher.log 2>&1 &
# ============================================================================

set -e

# ─── Configuration ──────────────────────────────────────────────────────
REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
BRANCH="main"
CHECK_INTERVAL=30        # seconds between git pull checks
BOT_SCRIPT="web_gui.py"  # launches both web GUI and bot
VENV_DIR="venv"
LOG_FILE="launcher.log"
PID_FILE=".bot.pid"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# ─── Functions ──────────────────────────────────────────────────────────

log() {
    echo -e "${CYAN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')] ✓${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[$(date '+%Y-%m-%d %H:%M:%S')] ⚠${NC} $1"
}

log_error() {
    echo -e "${RED}[$(date '+%Y-%m-%d %H:%M:%S')] ✗${NC} $1"
}

setup_venv() {
    if [ ! -d "$VENV_DIR" ]; then
        log "Creating Python virtual environment..."
        python3 -m venv "$VENV_DIR"
        log_success "Virtual environment created"
    fi
    source "$VENV_DIR/bin/activate"
}

install_deps() {
    log "Installing/updating dependencies..."
    pip install -r requirements.txt -q --upgrade
    log_success "Dependencies installed"
}

pull_latest() {
    cd "$REPO_DIR"
    
    # Fetch latest from remote
    git fetch origin "$BRANCH" --quiet 2>/dev/null
    
    # Check if there are new commits
    LOCAL=$(git rev-parse HEAD 2>/dev/null)
    REMOTE=$(git rev-parse "origin/$BRANCH" 2>/dev/null)
    
    if [ "$LOCAL" != "$REMOTE" ]; then
        log "New code detected! Pulling latest..."
        git pull origin "$BRANCH" --quiet
        log_success "Code updated to $(git rev-parse --short HEAD)"
        return 0  # true - code changed
    fi
    
    return 1  # false - no changes
}

start_bot() {
    cd "$REPO_DIR"
    setup_venv
    install_deps
    
    log "Starting bot (${BOT_SCRIPT})..."
    python "$BOT_SCRIPT" &
    BOT_PID=$!
    echo "$BOT_PID" > "$PID_FILE"
    log_success "Bot started (PID: $BOT_PID)"
}

stop_bot() {
    if [ -f "$PID_FILE" ]; then
        BOT_PID=$(cat "$PID_FILE")
        if kill -0 "$BOT_PID" 2>/dev/null; then
            log "Stopping bot (PID: $BOT_PID)..."
            kill "$BOT_PID" 2>/dev/null || true
            wait "$BOT_PID" 2>/dev/null || true
            log_success "Bot stopped"
        fi
        rm -f "$PID_FILE"
    fi
}

is_bot_running() {
    if [ -f "$PID_FILE" ]; then
        BOT_PID=$(cat "$PID_FILE")
        if kill -0 "$BOT_PID" 2>/dev/null; then
            return 0  # running
        fi
    fi
    return 1  # not running
}

cleanup() {
    log_warn "Shutting down launcher..."
    stop_bot
    log "Launcher stopped. Goodbye!"
    exit 0
}

# ─── Main ───────────────────────────────────────────────────────────────

# Trap Ctrl+C and other signals
trap cleanup SIGINT SIGTERM

cd "$REPO_DIR"

echo ""
echo "============================================================================"
echo "  🚀 Polymarket Copy Trading Bot - VPS Launcher"
echo "============================================================================"
echo "  Repo:     $REPO_DIR"
echo "  Branch:   $BRANCH"
echo "  Script:   $BOT_SCRIPT"
echo "  Interval: ${CHECK_INTERVAL}s between pull checks"
echo "============================================================================"
echo ""

# Initial setup
log "Performing initial git pull..."
git pull origin "$BRANCH" --quiet 2>/dev/null || true

# Start the bot
start_bot

# ─── Main Loop: Watch for Changes ──────────────────────────────────────
log "Watching for git pushes every ${CHECK_INTERVAL}s..."
log "Press Ctrl+C to stop"
echo ""

while true; do
    sleep "$CHECK_INTERVAL"
    
    # Check if bot is still running
    if ! is_bot_running; then
        log_warn "Bot crashed! Restarting..."
        start_bot
    fi
    
    # Check for new code
    if pull_latest; then
        log_warn "Code changed - restarting bot with new code..."
        stop_bot
        start_bot
        log_success "Bot restarted with latest code"
    fi
done
