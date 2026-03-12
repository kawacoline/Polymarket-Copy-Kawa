import os
import time
import json
import requests
import logging
import threading
from datetime import datetime, timezone
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL

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


class CopyTradingBot:
    def __init__(self):
        self.running = False
        self.dry_run = os.getenv("DRY_RUN", "True").lower() == "true"
        self.seen_trades = self.load_seen_trades()
        self.last_check = None
        self.target_accounts = self.load_target_accounts()
        self.trades_this_session = 0  # Session management
        self.session_limit_alerted = False # Flag to log session limit only once
        
        # Global stats
        self.stats = {
            "total_copied": 0,
            "live_copies": 0,
            "dry_run_copies": 0,
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
    
    def add_target_account(self, address: str, name: str = None, bet_amount: float = None):
        """Add a new target account to track"""
        # Reload accounts to ensure we have latest
        self.target_accounts = self.load_target_accounts()
        
        # Check if already exists
        for account in self.target_accounts:
            if account.get("address") == address:
                return False, "Account already exists"
        
        # Get profile name if not provided
        if not name:
            name = self.get_profile_name(address)
        
        new_account = {
            "address": address,
            "name": name,
            "rank": 9999,
            "score": 0,
            "winRate": 0,
            "pnl": 0,
            "tags": ["MANUAL"],
            "enabled": True,
            "bet_amount_override": bet_amount,
            "added_date": datetime.now(timezone.utc).isoformat()
        }
        
        self.target_accounts.append(new_account)
        self.save_target_accounts()
        
        # Sync stats to pick up the new account
        self.sync_account_stats()
        
        return True, "Account added successfully"
    
    def remove_target_account(self, address: str):
        """Remove a target account"""
        self.target_accounts = self.load_target_accounts()
        self.target_accounts = [
            acc for acc in self.target_accounts 
            if acc.get("address") != address
        ]
        self.save_target_accounts()
        
        # Remove from stats
        if address in self.stats["accounts"]:
            del self.stats["accounts"][address]
    
    def toggle_account(self, address: str, enabled: bool):
        """Enable/disable tracking for an account"""
        # Reload accounts to ensure we have latest
        self.target_accounts = self.load_target_accounts()
        
        for account in self.target_accounts:
            if account.get("address") == address:
                account["enabled"] = enabled
                self.save_target_accounts()
                
                # Update stats immediately
                if address in self.stats["accounts"]:
                    self.stats["accounts"][address]["enabled"] = enabled
                
                return True
        return False
    
    def load_seen_trades(self):
        """Load previously seen trades to avoid duplicates"""
        try:
            if os.path.exists(SEEN_TRADES_FILE):
                with open(SEEN_TRADES_FILE, 'r') as f:
                    data = json.load(f)
                    # Filter out None/null values to prevent corruption
                    return set(item for item in data if item is not None)
        except:
            pass
        return set()
    
    def save_seen_trades(self):
        """Save seen trades to file"""
        try:
            with open(SEEN_TRADES_FILE, 'w') as f:
                # Filter out None values before saving
                valid_trades = [t for t in self.seen_trades if t is not None]
                json.dump(valid_trades, f)
        except Exception as e:
            logger.exception(f"Error saving seen trades: {e}")
    
    def update_status(self, message: str = None):
        """Update status file for GUI"""
        # Sync account stats before updating status
        self.sync_account_stats()
        
        # Get current accounts for accurate counts
        current_accounts = self.load_target_accounts()
        
        status = {
            "running": self.running,
            "dry_run": self.dry_run,
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
        """Robust API request wrapper that handles SSL/Network errors dynamically"""
        max_retries = 3
        for i in range(max_retries):
            try:
                response = requests.request(method, url, **kwargs)
                response.raise_for_status()
                # If success, clear any previous API error logic
                return response
            except (requests.exceptions.SSLError, requests.exceptions.ConnectionError, requests.exceptions.Timeout) as e:
                if i < max_retries - 1:
                    bot_log(f"⚠️ API Connection issue ({i+1}/{max_retries}): {str(e)[:100]}...", category="API_ERROR")
                    time.sleep(2 * (i + 1))
                else:
                    raise e
            except Exception as e:
                raise e

    def get_profile_name(self, wallet_address: str) -> str:
        """Fetch profile name from Polymarket"""
        try:
            response = self.api_request(
                "GET",
                f"{PROFILE_API}/public-profile",
                params={"address": wallet_address},
                timeout=10
            )
            profile = response.json()
            return profile.get("name") or profile.get("pseudonym") or wallet_address[:10] + "..."
        except:
            return wallet_address[:10] + "..."
    
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
        
        # Filter for BUY trades only
        buy_trades = [
            a for a in activities 
            if a.get("type") == "TRADE" and a.get("side") == "BUY"
        ]
        
        if not buy_trades:
            return None
        
        # Return most recent BUY trade
        latest = buy_trades[0]
        
        # Generate synthetic ID if none exists
        if not latest.get("id"):
            condition_id = latest.get("conditionId", "")
            outcome_index = latest.get("outcomeIndex", "")
            timestamp = latest.get("timestamp", "")
            size = latest.get("size", "")
            latest["id"] = f"synthetic_{condition_id}_{outcome_index}_{timestamp}_{size}"
        
        return latest
    
    def already_has_position(self, positions: list, condition_id: str, outcome_index: int) -> bool:
        """Check if we already have a position for this market/outcome"""
        for pos in positions:
            if (pos.get("conditionId") == condition_id and 
                pos.get("outcomeIndex") == outcome_index):
                return True
        return False
    
    def get_clob_client(self):
        """Get authenticated CLOB client"""
        client = ClobClient(
            CLOB_API,
            key=PRIVATE_KEY,
            chain_id=137,
            signature_type=SIGNATURE_TYPE,
            funder=FUNDER_ADDRESS
        )
        creds = client.derive_api_key()
        client.set_api_creds(creds)
        return client
    
def bot_log(msg, category=None):
    """Unified bot logging that handles terminal dynamic output"""
    log_dynamic(logger, msg, category=category)

class CopyTradingBot:
    # ... previous code ...
    
    def log_trade_to_database(self, trade_id, timestamp, market_title, condition_id, outcome_index, 
                           outcome, size, price, token_id, is_dry_run=True, copied_from=""):
        """Log a trade to the SQLite database for tracking and P&L"""
        try:
            import sqlite3
            from pathlib import Path
            
            db_path = Path("simulated_history.db") if is_dry_run else Path("betting_history.db")
            
            # Create database and table if they don't exist
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
                    is_dry_run INTEGER DEFAULT 1,
                    copied_from TEXT
                )
            """)
            
            # Add new columns if they don't exist
            try:
                cursor.execute("ALTER TABLE trades ADD COLUMN is_dry_run INTEGER DEFAULT 1")
            except sqlite3.OperationalError:
                pass
                
            try:
                cursor.execute("ALTER TABLE trades ADD COLUMN copied_from TEXT")
            except sqlite3.OperationalError:
                pass
            
            created_date = datetime.fromtimestamp(timestamp, timezone.utc).strftime('%Y-%m-%d')
            
            cursor.execute("""
                INSERT OR REPLACE INTO trades 
                (id, timestamp, market_title, condition_id, outcome_index, outcome, 
                 side, size, price, token_id, created_date, is_dry_run, copied_from)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id,
                timestamp,
                market_title,
                condition_id,
                outcome_index,
                outcome,
                "BUY",
                size,
                price,
                token_id,
                created_date,
                1 if is_dry_run else 0,
                copied_from
            ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            bot_log(f"Warning: Could not log to database: {e}", category="ERROR")
    
    def place_bet(self, token_id: str, dollar_amount: float, price: float):
        """
        Place a bet on Polymarket
        
        Args:
            token_id: The token ID to buy
            dollar_amount: Amount in dollars to spend (e.g., 2.0 for $2)
            price: Current price per share (e.g., 0.65 for 65¢)
        """
        # Convert dollar amount to shares
        # If price is 0.65 and we want to spend $2, we buy 2/0.65 = 3.077 shares
        if price <= 0:
            raise ValueError(f"Invalid price: {price}. Cannot calculate shares.")
        
        shares = dollar_amount / price
        
        bot_log(f"  Converting ${dollar_amount:.2f} at {price*100:.1f}¢ = {shares:.2f} shares")
        
        client = self.get_clob_client()
        order = MarketOrderArgs(
            token_id=token_id,
            amount=shares,  # Now correctly passing SHARES, not dollars
            side=BUY,
            order_type=OrderType.FOK
        )
        signed_order = client.create_market_order(order)
        client.post_order(signed_order, OrderType.FOK)
    
    def check_account_for_trades(self, account: dict):
        """Check a single account for new trades"""
        address = account.get("address")
        name = account.get("name", address[:10])
        bet_amount = account.get("bet_amount_override") or BET_AMOUNT
        
        if not account.get("enabled", True):
            return
        
        try:
            # Update last check time for this account
            if address in self.stats["accounts"]:
                self.stats["accounts"][address]["last_check"] = datetime.now(timezone.utc).isoformat()
                # Save status immediately after updating last_check
                self.update_status()
            
            # Get latest bet
            latest = self.get_latest_bet(address)
            
            if not latest:
                return
            
            trade_id = latest.get("id")
            title = latest.get("title", "Unknown Market")[:50]
            outcome = latest.get("outcome", "Unknown Outcome")
            target_size = float(latest.get("size", 0))
            price = float(latest.get("price", 0))
            asset_id = latest.get("asset")
            condition_id = latest.get("conditionId")
            outcome_index = latest.get("outcomeIndex")
            
            # Check if we already have this position
            my_positions = self.get_positions(FUNDER_ADDRESS)
            
            if self.already_has_position(my_positions, condition_id, outcome_index):
                # Mark as seen but don't copy (only if trade_id is valid)
                if trade_id and trade_id not in self.seen_trades:
                    self.seen_trades.add(trade_id)
                    self.save_seen_trades()
                return
            
            # Check if we've already copied this trade
            if trade_id in self.seen_trades:
                return
            # SESSION LIMIT CHECK
            if not self.dry_run and self.trades_this_session >= MAX_TRADES_PER_SESSION:
                logger.info(f"  [SESSION LIMIT] Reached max trades ({MAX_TRADES_PER_SESSION}). Skipping {name}'s trade on {title}.")
                if trade_id: # Only add if trade_id is valid
                    self.seen_trades.add(trade_id)
                    self.save_seen_trades()
                return
            
            # EVENT LIMIT CHECK
            try:
                import sqlite3
                from pathlib import Path
                db_path = Path("betting_history.db")
                if not self.dry_run and db_path.exists():
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute(
                        "SELECT COUNT(*) FROM trades WHERE condition_id = ? AND outcome_index = ? AND side = 'BUY'",
                        (condition_id, outcome_index)
                    )
                    row = cursor.fetchone()
                    event_trade_count = row[0] if row else 0
                    conn.close()
                    
                    if event_trade_count >= MAX_TRADES_PER_EVENT:
                        logger.info(f"  [EVENT LIMIT] Reached max trades for this event ({MAX_TRADES_PER_EVENT}). Skipping.")
                        if trade_id: # Only add if trade_id is valid
                            self.seen_trades.add(trade_id)
                            self.save_seen_trades()
                        return
            except Exception as e:
                print(f"  Warning: Could not check event limit: {e}")
            
            # This is a new trade to copy!
            log_msg = f"[{datetime.now().strftime('%H:%M:%S')}] [NEW] New trade from {name}:"
            print(f"\n{log_msg}")
            print(f"  Market: {title}")
            print(f"  Outcome: {outcome}")
            print(f"  Price: {price*100:.1f}¢")
            print(f"  Amount: ${bet_amount:.2f}")
            
            # Calculate shares
            if price > 0:
                shares = bet_amount / price
            # Calculate shares
            if price > 0:
                shares = bet_amount / price
                trade_summary = (
                    f"[{datetime.now().strftime('%H:%M:%S')}] [NEW] New trade from {name}:\n"
                    f"  Market: {title}\n"
                    f"  Outcome: {outcome}\n"
                    f"  Price: {price*100:.1f}¢\n"
                    f"  Amount: ${bet_amount:.2f}\n"
                    f"  Shares: {shares:.2f}"
                )
            else:
                bot_log(f"  [X] Invalid price for {title}: {price}", category="ERROR")
                return
            
            if self.dry_run:
                trade_summary += f"\n  [OK] DRY RUN - Would copy this trade\n  [SESSION] Dry run trade logged."
                bot_log(trade_summary, category=f"TRADE_{trade_id}")
                
                # Update stats for dry run
                self.stats["total_copied"] += 1
                self.stats["dry_run_copies"] += 1
                self.stats["successful_copies"] += 1
                
                if address in self.stats["accounts"]:
                    self.stats["accounts"][address]["trades_copied"] += 1
                
            else:
                trade_summary += f"\n  ⚡ LIVE MODE - Executing trade..."
                bot_log(trade_summary, category=f"TRADE_START_{trade_id}")
                
                try:
                    self.place_bet(asset_id, bet_amount, price)
                    log_msg += f" [OK] COPIED"
                    bot_log(f"  [OK] Trade executed successfully!", category=f"TRADE_DONE_{trade_id}")
                    
                    # Update stats
                    self.stats["total_copied"] += 1
                    self.stats["live_copies"] += 1
                    self.stats["successful_copies"] += 1
                    
                    if address in self.stats["accounts"]:
                        self.stats["accounts"][address]["trades_copied"] += 1
                    
                    self.trades_this_session += 1  # Increment session counter
                    bot_log(f"  [SESSION] Trades this session: {self.trades_this_session}/{MAX_TRADES_PER_SESSION}", category="SESSION_STATS")
                    
                    # Log live trade to database
                    # ... (rest of DB logging) ...
                except Exception as e:
                    bot_log(f"Error executing trade: {e}", category="ERROR")
                    log_msg += f" [X] FAILED: {str(e)}"
                    bot_log(log_msg, category="ERROR")
                    self.stats["failed_copies"] += 1
            
            # Mark trade as seen (only if trade_id is valid)
            if trade_id:
                self.seen_trades.add(trade_id)
                self.save_seen_trades()
            
            # Update last trade info
            trade_info = {
                "title": title,
                "outcome": outcome,
                "price": price,
                "amount": bet_amount,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "from_account": name,
                "from_address": address
            }
            self.stats["last_trade_copied"] = trade_info
            
            if address in self.stats["accounts"]:
                self.stats["accounts"][address]["last_trade"] = trade_info
            
            self.update_status(log_msg)
            
        except Exception as e:
            error_msg = f"Error checking {name}: {str(e)}"
            bot_log(error_msg, category="ERROR")
    
    def check_and_copy(self):
        """Check all target accounts for new trades"""
        try:
            self.last_check = datetime.now(timezone.utc).isoformat()
            
            # CRITICAL: Reload accounts from file to pick up any changes made through GUI
            self.target_accounts = self.load_target_accounts()
            
            # Sync stats to ensure new accounts are tracked
            self.sync_account_stats()
            
            if not self.target_accounts:
                self.update_status("No target accounts configured")
                return

            # SESSION LIMIT EARLY EXIT
            if not self.dry_run and self.trades_this_session >= MAX_TRADES_PER_SESSION:
                if not self.session_limit_alerted:
                    bot_log(f"⚠️ SESSION LIMIT REACHED ({MAX_TRADES_PER_SESSION}/{MAX_TRADES_PER_SESSION}). Bot is now idling.", category="SESSION_LIMIT")
                    self.update_status(f"Session limit reached ({MAX_TRADES_PER_SESSION}). Bot idling.")
                    self.session_limit_alerted = True
                else:
                    bot_log(f"Idling - Session limit reached ({MAX_TRADES_PER_SESSION}).", category="SESSION_LIMIT")
                return
            
            # Reset alert flag if we are under the limit (e.g. if MAX_TRADES_PER_SESSION was increased via .env or GUI)
            if self.trades_this_session < MAX_TRADES_PER_SESSION:
                self.session_limit_alerted = False
            
            enabled_accounts = [acc for acc in self.target_accounts if acc.get("enabled", True)]
            
            if not enabled_accounts:
                self.update_status("No enabled accounts to monitor")
                return
            
            # Update status immediately to show we're checking
            self.update_status(f"Checking {len(enabled_accounts)} accounts...")
            
            # Check each account with delay between checks
            for i, account in enumerate(enabled_accounts):
                self.check_account_for_trades(account)
                
                # Add delay between accounts (except after last one)
                if i < len(enabled_accounts) - 1:
                    time.sleep(ACCOUNT_CHECK_DELAY)
            
            self.update_status(f"Checked {len(enabled_accounts)} accounts")
            
        except Exception as e:
            error_msg = f"Error in check cycle: {str(e)}"
            bot_log(error_msg, category="ERROR")
            self.update_status(error_msg)
    
    def start(self, check_interval: float = 0.01):
        """Start the continuous monitoring bot"""
        if self.running:
            bot_log("Bot is already running.", category="INFO")
            return

        if not FUNDER_ADDRESS:
            bot_log("Error: Missing FUNDER_ADDRESS in .env", category="ERROR")
            return
        
        if not PRIVATE_KEY and not self.dry_run:
            bot_log("Error: Missing PRIVATE_KEY for live trading", category="ERROR")
            return
        
        if not self.target_accounts:
            print("Error: No target accounts configured in accounts.json")
            return
        
        # Start periodic stats refresh thread
        import threading
        refresh_thread = threading.Thread(target=self._stats_refresh_loop)
        refresh_thread.daemon = True
        refresh_thread.start()
        
        self.running = True
        
        enabled_count = sum(1 for acc in self.target_accounts if acc.get("enabled", True))
        
        bot_log("="*50, category="BOT_START")
        bot_log("  --> Polymarket Copy Trading Bot Started", category="BOT_START")
        bot_log(f"  Funder: {FUNDER_ADDRESS}", category="BOT_START")
        bot_log(f"  Dry Run: {self.dry_run}", category="BOT_START")
        bot_log(f"  Interval: {check_interval}s", category="BOT_START")
        bot_log("="*50, category="BOT_START")
        
        self.update_status("Bot started and monitoring multiple accounts...")
        
        try:
            while self.running:
                try:
                    status_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Checking {enabled_count} accounts... (Press Ctrl+C to stop)"
                    bot_log(status_msg, category="MAIN_LOOP")
                    self.check_and_copy()
                    sleep_msg = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] Finished check. Sleeping {check_interval}s..."
                    bot_log(sleep_msg, category="MAIN_LOOP")
                    time.sleep(check_interval)
                except Exception as e:
                    bot_log(f"CRITICAL ERROR in main loop: {e}", category="ERROR")
                    time.sleep(10) # Wait before retry
        
        except KeyboardInterrupt:
            bot_log("⛔ Bot stopped by user", category="BOT_STOP")
            self.running = False
            self.update_status("Bot stopped by user")
        
        except Exception as e:
            bot_log(f"❌ Bot error: {e}", category="ERROR")
            self.running = False
            self.update_status(f"Bot stopped due to error: {str(e)}")
    
    def stop(self):
        """Stop the bot"""
        self.running = False
        self.update_status("Bot stopped")
    
    def set_dry_run(self, dry_run: bool):
        """Toggle dry run mode"""
        self.dry_run = dry_run
        self.update_status(f"Dry run mode: {'enabled' if dry_run else 'disabled'}")
    
    def panic_sell_all(self):
        """Close all open positions immediately"""
        if self.dry_run:
            bot_log("PANIC SELL - DRY RUN MODE (not executing)", category="PANIC")
            return {"success": True, "message": "Dry run mode - no positions closed", "closed": []}
        
        try:
            positions = self.get_positions(FUNDER_ADDRESS)
            
            if not positions:
                return {"success": True, "message": "No open positions to close", "closed": []}
            
            client = self.get_clob_client()
            closed_positions = []
            
            for position in positions:
                try:
                    token_id = position.get("asset")
                    size = float(position.get("size", 0))
                    title = position.get("title", "Unknown")
                    
                    if size > 0:
                        # Create sell order for full position
                        order = MarketOrderArgs(
                            token_id=token_id,
                            amount=size,
                            side=SELL,
                            order_type=OrderType.FOK
                        )
                        signed_order = client.create_market_order(order)
                        client.post_order(signed_order, OrderType.FOK)
                        
                        closed_positions.append({
                            "title": title,
                            "size": size
                        })
                        
                        bot_log(f"[OK] Closed position: {title} ({size} shares)", category="PANIC")
                
                except Exception as e:
                    bot_log(f"[X] Failed to close {title}: {e}", category="ERROR")
            
            return {
                "success": True,
                "message": f"Closed {len(closed_positions)} positions",
                "closed": closed_positions
            }
        
        except Exception as e:
            return {"success": False, "message": f"Panic sell failed: {str(e)}"}

    def _stats_refresh_loop(self):
        """Background thread to refresh all account stats every 24 hours"""
        import subprocess
        import os
        import json
        
        # Initial delay to let the bot stabilize
        time.sleep(60)
        
        while self.running:
            try:
                bot_log("🕒 Starting periodic account stats refresh...", category="BG_REFRESH")
                accounts = self.load_target_accounts()
                
                scrapper_dir = os.path.join(os.getcwd(), "polymarket-profitablewallets-scrapper")
                script_path = os.path.join(scrapper_dir, "src", "analyze_single.js")
                
                for acc in accounts:
                    if not self.running: break
                    if not acc.get('enabled', True): continue
                    
                    addr = acc.get('address')
                    if not addr: continue
                    
                    bot_log(f"  Enriching stats for {addr}...", category="BG_ENRICH")
                    try:
                        result = subprocess.run(
                            ["node", script_path, addr],
                            capture_output=True,
                            text=True,
                            cwd=scrapper_dir,
                            timeout=60
                        )
                        
                        if result.returncode == 0:
                            data = json.loads(result.stdout)
                            acc['pnl'] = data.get('pnl', acc.get('pnl', 0))
                            acc['winRate'] = data.get('winRate', acc.get('winRate', 0))
                            acc['rank'] = data.get('rank', acc.get('rank', 9999))
                            acc['tags'] = list(set(acc.get('tags', []) + data.get('tags', [])))
                            
                            acc['enrichment'] = {
                                "totalTrades": data.get('totalTrades', 0),
                                "activePositions": data.get('activePositions', 0),
                                "avgTradeSize": data.get('avgTradeSize', 0),
                                "tradesPerDay": data.get('tradesPerDay', 0),
                                "lastTradeAt": data.get('lastTradeAt'),
                                "lastUpdate": datetime.now(timezone.utc).isoformat()
                            }
                    except Exception:
                        pass # Silently continue
                    
                    time.sleep(10)
                
                # Save updated stats
                with open(ACCOUNTS_FILE, 'w') as f:
                    json.dump({"accounts": accounts}, f, indent=2)
                
                self.target_accounts = accounts
                self.sync_account_stats()
                bot_log("✅ Periodic refresh complete.", category="BG_REFRESH")
                
            except Exception as e:
                bot_log(f"Error in stats refresh loop: {e}", category="ERROR")
            
            # Wait 24 hours
            for _ in range(1440):
                if not self.running: break
                time.sleep(60)


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Multi-Account Copy Trading Bot')
    parser.add_argument('--interval', type=int, default=60, help='Check interval in seconds')
    parser.add_argument('--once', action='store_true', help='Run once and exit')
    
    args = parser.parse_args()
    
    bot = CopyTradingBot()
    
    if args.once:
        bot.check_and_copy()
    else:
        bot.start(check_interval=args.interval)


if __name__ == "__main__":
    main()