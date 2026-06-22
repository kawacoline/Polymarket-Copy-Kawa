import os
import time
import json
import requests
import logging
import threading
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from py_clob_client_v2 import ClobClient, OrderArgs, PartialCreateOrderOptions, OrderType
from py_clob_client_v2.order_builder.constants import BUY, SELL

from logging_utils import setup_logger, log_dynamic

load_dotenv()

# Logger Setup - Disabled internal console logging to use manual dynamic logging
logger = setup_logger("PolymarketBot", console=False)

FUNDER_ADDRESS = os.getenv("FUNDER_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
SIGNATURE_TYPE = int(os.getenv("SIGNATURE_TYPE", 1))
BET_AMOUNT = float(os.getenv("BET_AMOUNT", 2.0))
MAX_TRADES_PER_SESSION = int(os.getenv("MAX_TRADES_PER_SESSION", 3))
MAX_TRADES_PER_EVENT = int(os.getenv("MAX_TRADES_PER_EVENT", 1))

DATA_API = "https://data-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
PROFILE_API = "https://gamma-api.polymarket.com"

# Configuration files
STATUS_FILE = "bot_status.json"
SEEN_TRADES_FILE = "seen_trades.json"
ACCOUNTS_FILE = "accounts.json"

# Account check delay (to avoid rate limiting)
ACCOUNT_CHECK_DELAY = 2.0  # seconds

def bot_log(msg, category=None):
    """Unified bot logging that handles terminal dynamic output"""
    log_dynamic(logger, msg, category=category)

class CopyTradingBot:
    def __init__(self):
        self.running = False
        self.seen_trades = self.load_seen_trades()
        self.active_event_trades = set() # Memory guard for the current session
        self.last_check = None
        self.target_accounts = self.load_target_accounts()
        self.trades_this_session = 0  # Session management
        self.session_limit_alerted = False # Flag to log session limit only once
        
        # Global stats
        self.stats = {
            "total_copied": 0,
            "live_copies": 0,
            "successful_copies": 0,
            "failed_copies": 0,
            "last_trade_copied": None,
            "accounts": {}  # Per-account stats
        }
        
        # Initialize per-account stats
        self.sync_account_stats()
    
    def sync_account_stats(self):
        """Sync stats dictionary with current account list"""
        # Reload accounts from file to catch any changes made through GUI
        current_accounts = self.load_target_accounts()
        
        # Add stats for new accounts
        for account in current_accounts:
            addr = account.get("address", "")
            if addr and addr not in self.stats["accounts"]:
                self.stats["accounts"][addr] = {
                    "name": account.get("name", addr[:10]),
                    "trades_copied": 0,
                    "last_check": None,
                    "last_trade": None,
                    "enabled": account.get("enabled", True)
                }
            elif addr:
                # Update enabled status from accounts.json
                self.stats["accounts"][addr]["enabled"] = account.get("enabled", True)
                self.stats["accounts"][addr]["name"] = account.get("name", addr[:10])
        
        # Remove stats for accounts that no longer exist
        current_addresses = set(acc.get("address") for acc in current_accounts if acc.get("address"))
        removed_addresses = [addr for addr in self.stats["accounts"].keys() if addr not in current_addresses]
        for addr in removed_addresses:
            del self.stats["accounts"][addr]
    
    def load_target_accounts(self):
        """Load target accounts from accounts.json"""
        accounts = []
        try:
            if os.path.exists(ACCOUNTS_FILE):
                with open(ACCOUNTS_FILE, 'r') as f:
                    content = f.read().strip()
                    if content:
                        data = json.loads(content)
                        accounts = data.get("accounts", [])
        except Exception as e:
            print(f"Error loading accounts: {e}")
        
        # Fallback: check if old TARGET_ADDRESS env exists and add it if not already in list
        old_target = os.getenv("TARGET_ADDRESS")
        if old_target and not any(acc.get("address", "").lower() == old_target.lower() for acc in accounts):
            accounts.append({
                "address": old_target,
                "name": "Default Target",
                "enabled": True,
                "bet_amount_override": None
            })
            
        return accounts
    
    def save_target_accounts(self):
        """Save target accounts to accounts.json"""
        try:
            with open(ACCOUNTS_FILE, 'w') as f:
                json.dump({"accounts": self.target_accounts}, f, indent=2)
        except Exception as e:
            logger.exception(f"Error saving accounts: {e}")
    
    def load_seen_trades(self):
        """Load previously seen trades to avoid duplicates"""
        try:
            if os.path.exists(SEEN_TRADES_FILE):
                with open(SEEN_TRADES_FILE, 'r') as f:
                    data = json.load(f)
                    return set(item for item in data if item is not None)
        except:
            pass
        return set()
    
    def save_seen_trades(self):
        """Save seen trades to file"""
        try:
            with open(SEEN_TRADES_FILE, 'w') as f:
                valid_trades = [t for t in self.seen_trades if t is not None]
                json.dump(valid_trades, f)
        except Exception as e:
            logger.exception(f"Error saving seen trades: {e}")
    
    def update_status(self, message: str = None):
        """Update status file for GUI"""
        self.sync_account_stats()
        current_accounts = self.load_target_accounts()
        
        status = {
            "running": self.running,
            "last_check": self.last_check,
            "stats": self.stats,
            "message": message,
            "tracked_accounts": len(current_accounts),
            "enabled_accounts": sum(1 for acc in current_accounts if acc.get("enabled", True))
        }
        
        try:
            with open(STATUS_FILE, 'w') as f:
                json.dump(status, f, indent=2)
        except Exception as e:
            logger.exception(f"Error updating status: {e}")
    
    def api_request(self, method, url, **kwargs):
        """Robust API request wrapper with retries"""
        max_retries = 3
        for i in range(max_retries):
            try:
                response = requests.request(method, url, **kwargs)
                response.raise_for_status()
                return response
            except (requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if i < max_retries - 1:
                    bot_log(f"⚠️ API Connection issue ({i+1}/{max_retries}): {str(e)[:100]}...", category="API_ERROR")
                    time.sleep(2 * (i + 1))
                else:
                    raise e
            except Exception as e:
                raise e

    def get_positions(self, wallet_address: str) -> list:
        """Fetch positions for a wallet"""
        try:
            response = self.api_request(
                "GET",
                f"{DATA_API}/positions",
                params={"user": wallet_address, "sizeThreshold": 0},
                timeout=10
            )
            return response.json()
        except Exception as e:
            bot_log(f"Error fetching positions for {wallet_address}: {e}", category="API_ERROR")
            return []

    def get_latest_bet(self, wallet_address: str) -> dict | None:
        """Get the latest BUY trade for a wallet"""
        try:
            response = self.api_request(
                "GET",
                f"{DATA_API}/activity",
                params={"user": wallet_address, "limit": 50},
                timeout=10
            )
            activities = response.json()
        except Exception as e:
            bot_log(f"Error fetching latest bet for {wallet_address}: {e}", category="API_ERROR")
            return None
        
        buy_trades = [a for a in activities if a.get("type") == "TRADE" and a.get("side") == "BUY"]
        if not buy_trades: return None
        
        latest = buy_trades[0]
        if not latest.get("id"):
            latest["id"] = f"synthetic_{latest.get('conditionId','')}_{latest.get('outcomeIndex','')}_{latest.get('timestamp','')}_{latest.get('size','')}"
        
        return latest
    
    def already_has_position(self, positions: list, condition_id: str, outcome_index: int) -> bool:
        """Check if we already have a position for this market/outcome"""
        for pos in positions:
            if (pos.get("conditionId") == condition_id and pos.get("outcomeIndex") == int(outcome_index)):
                return True
        return False
    
    def get_clob_client(self):
        """Get authenticated CLOB client (V2)"""
        client = ClobClient(
            host=CLOB_API,
            key=PRIVATE_KEY,
            chain_id=137,
            signature_type=SIGNATURE_TYPE,
            funder=FUNDER_ADDRESS,
        )
        creds = client.create_or_derive_api_key()
        client.set_api_creds(creds)
        return client

    def log_trade_to_database(self, trade_id, timestamp, market_title, condition_id, outcome_index, 
                           outcome, size, price, token_id, copied_from=""):
        """Log a trade to the SQLite database for tracking and P&L"""
        try:
            db_path = Path("betting_history.db")
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS trades (
                    id TEXT PRIMARY KEY,
                    timestamp INTEGER,
                    market_title TEXT,
                    condition_id TEXT,
                    outcome_index INTEGER,
                    outcome TEXT,
                    side TEXT,
                    size REAL,
                    price REAL,
                    token_id TEXT,
                    status TEXT DEFAULT 'OPEN',
                    created_date TEXT,
                    copied_from TEXT
                )
            """)
            
            # Migration/Maintenance
            for col in ["copied_from TEXT"]:
                try: cursor.execute(f"ALTER TABLE trades ADD COLUMN {col}")
                except: pass
            
            created_date = datetime.fromtimestamp(timestamp, timezone.utc).strftime('%Y-%m-%d')
            cursor.execute("""
                INSERT OR REPLACE INTO trades 
                (id, timestamp, market_title, condition_id, outcome_index, outcome, 
                 side, size, price, token_id, created_date, copied_from)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (trade_id, timestamp, market_title, condition_id, outcome_index, outcome, 
                 "BUY", size, price, token_id, created_date, copied_from))
            
            conn.commit()
            conn.close()
            
            # Update memory guard
            self.active_event_trades.add(f"{condition_id}_{outcome_index}")
            
        except Exception as e:
            bot_log(f"Warning: Could not log to database: {e}", category="ERROR")

    def place_bet(self, token_id: str, dollar_amount: float, price: float):
        """Place a bet on Polymarket (V2 API)"""
        if price <= 0: raise ValueError(f"Invalid price: {price}")
        shares = dollar_amount / price
        bot_log(f"  Converting ${dollar_amount:.2f} at {price*100:.1f}¢ = {shares:.2f} shares")
        
        client = self.get_clob_client()
        # V2: Use create_and_post_order with FOK for immediate execution
        response = client.create_and_post_order(
            OrderArgs(
                token_id=token_id,
                price=price,
                size=shares,
                side=BUY,
            ),
            options=PartialCreateOrderOptions(
                tick_size="0.01",
                neg_risk=False,
            ),
            order_type=OrderType.FOK,
        )
        bot_log(f"  Order response: {response}")

    def check_account_for_trades(self, account: dict):
        """Check a single account for new trades"""
        address = account.get("address")
        name = account.get("name", address[:10])
        bet_amount = account.get("bet_amount_override") or BET_AMOUNT
        
        if not account.get("enabled", True): return
        
        try:
            if address in self.stats["accounts"]:
                self.stats["accounts"][address]["last_check"] = datetime.now(timezone.utc).isoformat()
                self.update_status()
            
            latest = self.get_latest_bet(address)
            if not latest: return
            
            trade_id = latest.get("id")
            title = latest.get("title", "Unknown Market")[:50]
            outcome = latest.get("outcome", "Unknown Outcome")
            price = float(latest.get("price", 0))
            asset_id = latest.get("asset")
            condition_id = latest.get("conditionId")
            outcome_index = latest.get("outcomeIndex")
            
            if trade_id in self.seen_trades: return

            # MEMORY GUARD CHECK
            if f"{condition_id}_{outcome_index}" in self.active_event_trades:
                # Mark as seen to avoid repeated logging attempts
                self.seen_trades.add(trade_id)
                self.save_seen_trades()
                return

            # POSITION CHECK
            my_positions = self.get_positions(FUNDER_ADDRESS)
            if self.already_has_position(my_positions, condition_id, outcome_index):
                if trade_id:
                    self.seen_trades.add(trade_id)
                    self.save_seen_trades()
                return

            # SESSION LIMIT CHECK
            if self.trades_this_session >= MAX_TRADES_PER_SESSION:
                bot_log(f"  [SESSION LIMIT] Max trades reached. Skipping {name}'s trade.", category="SESSION_LIMIT")
                if trade_id: self.seen_trades.add(trade_id); self.save_seen_trades()
                return
            
            # EVENT LIMIT CHECK (DB)
            try:
                db_path = Path("betting_history.db")
                if db_path.exists():
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT COUNT(*) FROM trades WHERE condition_id = ? AND outcome_index = ? AND side = 'BUY'", (condition_id, outcome_index))
                    event_trade_count = cursor.fetchone()[0]
                    conn.close()
                    
                    if event_trade_count >= MAX_TRADES_PER_EVENT:
                        bot_log(f"  [EVENT LIMIT] Reached max trades for event ({MAX_TRADES_PER_EVENT}). Skipping.", category="EVENT_LIMIT")
                        if trade_id: self.seen_trades.add(trade_id); self.save_seen_trades()
                        return
            except Exception as e:
                bot_log(f"  Warning: Event limit check failed: {e}", category="ERROR")

            # EXECUTION
            shares = bet_amount / price if price > 0 else 0
            if shares <= 0:
                bot_log(f"  [X] Invalid trade data (shares: {shares})", category="ERROR")
                return

            trade_summary = f"[{datetime.now().strftime('%H:%M:%S')}] [NEW] {name} -> {title} ({outcome}) @ {price*100:.1f}¢"
            
            bot_log(trade_summary + " [EXECUTING]", category=f"TRADE_START_{trade_id}")
            try:
                self.place_bet(asset_id, bet_amount, price)
                self.log_trade_to_database(trade_id, int(time.time()), title, condition_id, outcome_index, outcome, shares, price, asset_id, name)
                self.stats["live_copies"] += 1
                self.trades_this_session += 1
                bot_log(f"  [OK] Success! Session: {self.trades_this_session}/{MAX_TRADES_PER_SESSION}", category="SESSION_STATS")
            except Exception as e:
                bot_log(f"Execution Error: {e}", category="ERROR")
                self.stats["failed_copies"] += 1

            self.stats["total_copied"] += 1
            self.stats["successful_copies"] += 1
            if address in self.stats["accounts"]: self.stats["accounts"][address]["trades_copied"] += 1
            
            if trade_id: self.seen_trades.add(trade_id); self.save_seen_trades()
            self.update_status(f"Copied {name}: {title}")
            
        except Exception as e:
            bot_log(f"Error checking {name}: {e}", category="ERROR")

    def check_and_copy(self):
        """Check all target accounts"""
        try:
            self.last_check = datetime.now(timezone.utc).isoformat()
            self.target_accounts = self.load_target_accounts()
            self.sync_account_stats()
            
            if not self.target_accounts: return
            
            if self.trades_this_session >= MAX_TRADES_PER_SESSION:
                if not self.session_limit_alerted:
                    bot_log(f"⚠️ SESSION LIMIT REACHED ({MAX_TRADES_PER_SESSION}). idling.", category="SESSION_LIMIT")
                    self.session_limit_alerted = True
                return
            
            self.session_limit_alerted = False
            enabled_accounts = [acc for acc in self.target_accounts if acc.get("enabled", True)]
            self.update_status(f"Checking {len(enabled_accounts)} accounts...")
            
            for i, account in enumerate(enabled_accounts):
                self.check_account_for_trades(account)
                if i < len(enabled_accounts) - 1: time.sleep(ACCOUNT_CHECK_DELAY)
            
            self.update_status(f"Checked {len(enabled_accounts)} accounts")
        except Exception as e:
            bot_log(f"Cycle Error: {e}", category="ERROR")

    def start(self, check_interval: float = 0.01):
        """Main Loop"""
        if self.running: return
        self.running = True
        
        # Periodic stats refresh in BG
        threading.Thread(target=self._stats_refresh_loop, daemon=True).start()
        
        bot_log("="*50, category="BOT_START")
        bot_log("  Polymarket Copy Bot Started", category="BOT_START")
        bot_log(f"  Funder: {FUNDER_ADDRESS}", category="BOT_START")
        bot_log("="*50, category="BOT_START")
        
        try:
            while self.running:
                self.check_and_copy()
                time.sleep(check_interval)
        except KeyboardInterrupt:
            self.running = False

    def _stats_refresh_loop(self):
        """24-hour enrichment refresh"""
        while self.running:
            try:
                bot_log("🕒 BG Refresh starting...", category="BG_REFRESH")
                accounts = self.load_target_accounts()
                scrapper_dir = os.path.join(os.getcwd(), "polymarket-profitablewallets-scrapper")
                script_path = os.path.join(scrapper_dir, "src", "analyze_single.js")
                
                for acc in accounts:
                    if not self.running: break
                    addr = acc.get('address')
                    if not addr or not acc.get('enabled', True): continue
                    
                    try:
                        result = subprocess.run(["node", script_path, addr], capture_output=True, text=True, cwd=scrapper_dir, timeout=60)
                        if result.returncode == 0:
                            data = json.loads(result.stdout)
                            acc.update({
                                'pnl': data.get('pnl', acc.get('pnl', 0)),
                                'winRate': data.get('winRate', acc.get('winRate', 0)),
                                'rank': data.get('rank', acc.get('rank', 9999)),
                                'enrichment': {**data, "lastUpdate": datetime.now(timezone.utc).isoformat()}
                            })
                    except: pass
                    time.sleep(10)
                
                with open(ACCOUNTS_FILE, 'w') as f: json.dump({"accounts": accounts}, f, indent=2)
                self.target_accounts = accounts
                bot_log("✅ BG Refresh complete.", category="BG_REFRESH")
            except Exception as e:
                bot_log(f"BG Refresh Error: {e}", category="ERROR")
            
            for _ in range(1440):
                if not self.running: break
                time.sleep(60)

def main():
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--interval', type=int, default=60)
    parser.add_argument('--once', action='store_true')
    args = parser.parse_args()
    bot = CopyTradingBot()
    if args.once: bot.check_and_copy()
    else: bot.start(args.interval)

if __name__ == "__main__":
    main()