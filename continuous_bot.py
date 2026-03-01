import os
import time
import json
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL

load_dotenv()

FUNDER_ADDRESS = os.getenv("FUNDER_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
SIGNATURE_TYPE = int(os.getenv("SIGNATURE_TYPE", 1))
BET_AMOUNT = float(os.getenv("BET_AMOUNT", 2.0))

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
        
        # Global stats
        self.stats = {
            "total_copied": 0,
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
        try:
            if os.path.exists(ACCOUNTS_FILE):
                with open(ACCOUNTS_FILE, 'r') as f:
                    data = json.load(f)
                    return data.get("accounts", [])
        except Exception as e:
            print(f"Error loading accounts: {e}")
        
        # Fallback: check if old TARGET_ADDRESS env exists
        old_target = os.getenv("TARGET_ADDRESS")
        if old_target:
            return [{
                "address": old_target,
                "name": "Default Target",
                "enabled": True,
                "bet_amount_override": None
            }]
        
        return []
    
    def save_target_accounts(self):
        """Save target accounts to accounts.json"""
        try:
            with open(ACCOUNTS_FILE, 'w') as f:
                json.dump({"accounts": self.target_accounts}, f, indent=2)
        except Exception as e:
            print(f"Error saving accounts: {e}")
    
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
            print(f"Error saving seen trades: {e}")
    
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
            print(f"Error updating status: {e}")
    
    def get_profile_name(self, wallet_address: str) -> str:
        """Fetch profile name from Polymarket"""
        try:
            response = requests.get(
                f"{PROFILE_API}/public-profile",
                params={"address": wallet_address},
                timeout=10
            )
            response.raise_for_status()
            profile = response.json()
            return profile.get("name") or profile.get("pseudonym") or wallet_address[:10] + "..."
        except:
            return wallet_address[:10] + "..."
    
    def get_positions(self, wallet_address: str) -> list:
        """Fetch positions for a wallet"""
        response = requests.get(
            f"{DATA_API}/positions",
            params={"user": wallet_address, "sizeThreshold": 0},
            timeout=10
        )
        response.raise_for_status()
        return response.json()
    
    def get_latest_bet(self, wallet_address: str) -> dict | None:
        """Get the latest BUY trade for a wallet"""
        response = requests.get(
            f"{DATA_API}/activity",
            params={"user": wallet_address, "limit": 50},
            timeout=10
        )
        response.raise_for_status()
        
        activities = response.json()
        
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
    
    def log_trade_to_database(self, trade_id: str, timestamp: int, market_title: str,
                              condition_id: str, outcome_index: int, outcome: str,
                              size: float, price: float, token_id: str,
                              is_dry_run: bool = True, copied_from: str = None):
        """Log trade to SQLite database for historical tracking"""
        try:
            import sqlite3
            from pathlib import Path
            
            db_path = Path("betting_history.db")
            
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
                    created_date TEXT,
                    is_dry_run INTEGER DEFAULT 1,
                    copied_from TEXT
                )
            """)
            
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
            print(f"Warning: Could not log to database: {e}")
    
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
        
        print(f"  Converting ${dollar_amount:.2f} at {price*100:.1f}¢ = {shares:.2f} shares")
        
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
            
            # This is a new trade to copy!
            log_msg = f"[{datetime.now().strftime('%H:%M:%S')}] 📋 New trade from {name}:"
            print(f"\n{log_msg}")
            print(f"  Market: {title}")
            print(f"  Outcome: {outcome}")
            print(f"  Price: {price*100:.1f}¢")
            print(f"  Amount: ${bet_amount:.2f}")
            
            # Calculate shares
            if price > 0:
                shares = bet_amount / price
                print(f"  Shares: {shares:.2f}")
            else:
                print(f"  ✗ Invalid price: {price}")
                return
            
            if self.dry_run:
                print(f"  ✓ DRY RUN - Would copy this trade")
                log_msg += f" ✓ DRY RUN - Would copy"
                
                # Log dry run trade to database
                try:
                    self.log_trade_to_database(
                        trade_id=trade_id,
                        timestamp=int(datetime.now(timezone.utc).timestamp()),
                        market_title=title,
                        condition_id=condition_id,
                        outcome_index=outcome_index,
                        outcome=outcome,
                        size=shares,
                        price=price,
                        token_id=asset_id,
                        is_dry_run=True,
                        copied_from=address
                    )
                except Exception as e:
                    print(f"  Warning: Could not log dry run trade to database: {e}")
                
                # Update stats for dry run
                self.stats["total_copied"] += 1
                self.stats["successful_copies"] += 1
                
                if address in self.stats["accounts"]:
                    self.stats["accounts"][address]["trades_copied"] += 1
                
            else:
                print(f"  ⚡ LIVE MODE - Executing trade...")
                try:
                    self.place_bet(asset_id, bet_amount, price)
                    log_msg += f" ✓ COPIED"
                    print(f"  ✓ Trade executed successfully!")
                    
                    # Update stats
                    self.stats["total_copied"] += 1
                    self.stats["successful_copies"] += 1
                    
                    if address in self.stats["accounts"]:
                        self.stats["accounts"][address]["trades_copied"] += 1
                    
                    # Log live trade to database
                    try:
                        self.log_trade_to_database(
                            trade_id=trade_id,
                            timestamp=int(datetime.now(timezone.utc).timestamp()),
                            market_title=title,
                            condition_id=condition_id,
                            outcome_index=outcome_index,
                            outcome=outcome,
                            size=shares,
                            price=price,
                            token_id=asset_id,
                            is_dry_run=False,
                            copied_from=address
                        )
                    except Exception as e:
                        print(f"  Warning: Could not log live trade to database: {e}")
                        
                except Exception as e:
                    log_msg += f" ✗ FAILED: {str(e)}"
                    print(log_msg)
                    self.stats["failed_copies"] += 1
            
            # Mark trade as seen (only if trade_id is valid)
            if trade_id:
                self.seen_trades.add(trade_id)
                self.save_seen_trades()
            
            # Update stats
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
            print(error_msg)
    
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
            print(error_msg)
            self.update_status(error_msg)
    
    def start(self, check_interval: int = 60):
        """Start the continuous monitoring bot"""
        if not FUNDER_ADDRESS:
            print("Error: Missing FUNDER_ADDRESS in .env")
            return
        
        if not PRIVATE_KEY and not self.dry_run:
            print("Error: Missing PRIVATE_KEY for live trading")
            return
        
        # Load accounts fresh at start
        self.target_accounts = self.load_target_accounts()
        
        if not self.target_accounts:
            print("Error: No target accounts configured in accounts.json")
            return
        
        self.running = True
        
        enabled_count = sum(1 for acc in self.target_accounts if acc.get("enabled", True))
        
        print("\n" + "="*80)
        print(f"  MULTI-ACCOUNT COPY TRADING BOT STARTED")
        print(f"  Tracking: {enabled_count} of {len(self.target_accounts)} accounts")
        for account in self.target_accounts:
            if account.get("enabled", True):
                name = account.get("name", "Unknown")
                addr = account.get("address", "")[:10]
                print(f"    • {name} ({addr}...)")
        print(f"  Your wallet: {FUNDER_ADDRESS[:10]}...{FUNDER_ADDRESS[-6:]}")
        print(f"  Mode: {'DRY RUN' if self.dry_run else 'LIVE TRADING'}")
        print(f"  Default Bet Amount: ${BET_AMOUNT}")
        print(f"  Check Interval: {check_interval} seconds")
        print(f"  Account Check Delay: {ACCOUNT_CHECK_DELAY} seconds")
        print("="*80 + "\n")
        
        self.update_status("Bot started and monitoring multiple accounts...")
        
        try:
            while self.running:
                print(f"\n[{datetime.now().strftime('%H:%M:%S')}] Check cycle starting...")
                self.check_and_copy()
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Check complete, sleeping {check_interval}s...")
                time.sleep(check_interval)
        
        except KeyboardInterrupt:
            print("\n\n⛔ Bot stopped by user")
            self.running = False
            self.update_status("Bot stopped by user")
        
        except Exception as e:
            print(f"\n\n❌ Bot error: {e}")
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
            print("PANIC SELL - DRY RUN MODE (not executing)")
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
                        
                        print(f"✓ Closed position: {title} ({size} shares)")
                
                except Exception as e:
                    print(f"✗ Failed to close {title}: {e}")
            
            return {
                "success": True,
                "message": f"Closed {len(closed_positions)} positions",
                "closed": closed_positions
            }
        
        except Exception as e:
            return {"success": False, "message": f"Panic sell failed: {str(e)}"}


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