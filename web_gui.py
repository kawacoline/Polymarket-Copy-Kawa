#!/usr/bin/env python3
"""
Flask Web GUI for Polymarket Copy Trading Bot
Enhanced with multi-account tracking and Excel export
"""

import os
import json
import sqlite3
import threading
import time
from datetime import datetime, timezone
from flask import Flask, render_template, jsonify, request, send_file
from dotenv import load_dotenv
import requests
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import SELL
import pandas as pd
from io import BytesIO

from logging_utils import setup_logger, log_dynamic

load_dotenv()
logger = setup_logger("WebGUI", console=False) # We'll handle terminal manually

FUNDER_ADDRESS = os.getenv("FUNDER_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
SIGNATURE_TYPE = int(os.getenv("SIGNATURE_TYPE", 1))

DATA_API = "https://data-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
PROFILE_API = "https://gamma-api.polymarket.com"
STATUS_FILE = "bot_status.json"
DB_PATH = "betting_history.db"
WITHDRAWALS_FILE = "withdrawals.json"
ACCOUNTS_FILE = "accounts.json"

app = Flask(__name__)

# Configure Werkzeug for dynamic logs
import logging

class DynamicAccessHandler(logging.Handler):
    """Custom handler for Werkzeug to make access logs dynamic."""
    def emit(self, record):
        try:
            msg = self.format(record)
            
            # Trim the message: Extract "GET /path HTTP/1.1" 200
            # Example: 127.0.0.1 - - [12/Mar/2026 15:15:49] "GET /api/portfolio HTTP/1.1" 200 -
            import re
            match = re.search(r'"(.*?)"\s+(\d+)', msg)
            if match:
                request_line = match.group(1) # e.g. "GET /api/portfolio HTTP/1.1"
                status_code = match.group(2)  # e.g. "200"
                # Strip HTTP version to save more space
                request_line = request_line.replace(" HTTP/1.1", "").replace(" HTTP/1.0", "")
                display_msg = f"{request_line} {status_code}"
            else:
                display_msg = msg
                
            # Group all /api/ requests into a single dynamic line
            if "/api/" in display_msg:
                log_dynamic(logger, display_msg, category="HTTP_POLLING")
            else:
                log_dynamic(logger, display_msg, category="HTTP_ACCESS")
        except Exception:
            self.handleError(record)

log = logging.getLogger('werkzeug')
log.setLevel(logging.INFO)
log.propagate = False 
for h in log.handlers[:]:
    log.removeHandler(h)
log.addHandler(DynamicAccessHandler())
# Suppress noisy library loggers (py_clob_client prints "Make sure you have USDC" every call)
# These only affect the library's own loggers, not our app
for _lib_name in ['py_clob_client', 'polymarket', 'clob_client']:
    logging.getLogger(_lib_name).setLevel(logging.CRITICAL)

# ---- USDC Balance: RPC Fallback Chain + Cache ----
# Ordered list of reliable free Polygon RPCs; bot cycles to next on failure
POLYGON_RPCS = [
    'https://polygon-rpc.com',                      # 1 - Official Polygon RPC
    'https://rpc-mainnet.matic.quiknode.pro',        # 2 - QuickNode public
    'https://rpc.ankr.com/polygon',                 # 3 - Ankr (very reliable)
    'https://polygon.drpc.org',                     # 4 - dRPC
    'https://polygon-mainnet.public.blastapi.io',   # 5 - Blast API
    'https://1rpc.io/matic',                        # 6 - 1RPC
]

_rpc_index = 0          # current RPC in use
_balance_cache = None   # last successfully fetched balance (float)
_balance_ts = 0.0       # unix timestamp of last successful fetch
_portfolio_cache = None # cached portfolio stats dict
_portfolio_ts = 0.0     # last successful portfolio calculation


# Bot instance (will be imported)
bot_instance = None
bot_thread = None


def get_clob_client():
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


def get_positions():
    """Calculate current positions locally from betting_history.db"""
    try:
        import sqlite3
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Group trades by token to find net position
        cursor.execute("""
            SELECT 
                market_title as title,
                outcome,
                token_id as asset,
                SUM(CASE WHEN side = 'BUY' THEN size ELSE -size END) as net_size,
                SUM(CASE WHEN side = 'BUY' THEN size * price ELSE 0 END) as total_spent,
                SUM(CASE WHEN side = 'BUY' THEN size ELSE 0 END) as total_bought,
                GROUP_CONCAT(DISTINCT copied_from) as copied_from
            FROM trades
            GROUP BY token_id, market_title, outcome
            HAVING net_size > 0.01
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        enhanced = []
        for row in rows:
            size = float(row['net_size'])
            # Calculate average entry price
            total_bought = float(row['total_bought'])
            entry_price = float(row['total_spent']) / total_bought if total_bought > 0 else 0
            
            # Since we can't fetch live price easily without SDK, mock currentPrice as entry 
            # (or use 0% unrealized PNL temporarily)
            current_price = entry_price
            
            enhanced.append({
                "title": row['title'],
                "outcome": row['outcome'],
                "asset": row['asset'],
                "size": round(size, 2),
                "price": round(entry_price, 4),
                "currentPrice": round(current_price, 4),
                "pnl": 0.0,
                "pnl_percent": 0.0,
                "current_value": round(size * current_price, 2),
                "cost_basis": round(size * entry_price, 2),
                "copied_from": row["copied_from"]
            })
            
        return enhanced
        
    except Exception as e:
        logger.error(f"Error calculating positions from DB: {e}")
        return []

def get_simulated_positions():
    try:
        import sqlite3
        import os
        sim_db_path = "simulated_history.db"
        
        if not os.path.exists(sim_db_path):
            return []
            
        conn = sqlite3.connect(sim_db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
            
        # Group trades by token to find net position for dry run trades
        cursor.execute("""
            SELECT 
                market_title as title,
                outcome,
                token_id as asset,
                SUM(CASE WHEN side = 'BUY' THEN size ELSE -size END) as net_size,
                SUM(CASE WHEN side = 'BUY' THEN size * price ELSE 0 END) as total_spent,
                SUM(CASE WHEN side = 'BUY' THEN size ELSE 0 END) as total_bought,
                GROUP_CONCAT(DISTINCT copied_from) as copied_from
            FROM trades
            GROUP BY token_id, market_title, outcome
            HAVING net_size > 0.01
        """)
        
        rows = cursor.fetchall()
        conn.close()
        
        enhanced = []
        for row in rows:
            size = float(row['net_size'])
            # Calculate average entry price
            total_bought = float(row['total_bought'])
            entry_price = float(row['total_spent']) / total_bought if total_bought > 0 else 0
            
            # Since we can't fetch live price easily without SDK, mock currentPrice as entry 
            current_price = entry_price
            
            enhanced.append({
                "title": row['title'],
                "outcome": row['outcome'],
                "asset": row['asset'],
                "size": round(size, 2),
                "price": round(entry_price, 4),
                "currentPrice": round(current_price, 4),
                "pnl": 0.0,
                "pnl_percent": 0.0,
                "current_value": round(size * current_price, 2),
                "cost_basis": round(size * entry_price, 2),
                "copied_from": row["copied_from"]
            })
            
        return enhanced
        
    except Exception as e:
        logger.error(f"Error calculating simulated positions from DB: {e}")
        return []



def _fetch_usdc_balance_with_fallback():
    """Try each RPC in POLYGON_RPCS in order, rotating to the next on failure.
    Returns the float USDC balance, or None if all RPCs fail."""
    global _rpc_index
    from web3 import Web3

    usdc_address = Web3.to_checksum_address('0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174')
    erc20_abi = [{
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "balance", "type": "uint256"}],
        "type": "function"
    }]
    user_address = Web3.to_checksum_address(FUNDER_ADDRESS)

    # Try every RPC starting from the current index
    total = len(POLYGON_RPCS)
    
    # 15 second cache check for balance (to save RPC calls)
    now = time.time()
    if _balance_cache is not None and (now - _balance_ts < 15):
        return _balance_cache

    for attempt in range(total):
        rpc = POLYGON_RPCS[_rpc_index % total]
        try:
            w3 = Web3(Web3.HTTPProvider(rpc, request_kwargs={'timeout': 5}))
            contract = w3.eth.contract(address=usdc_address, abi=erc20_abi)
            raw = contract.functions.balanceOf(user_address).call()
            balance = raw / 1_000_000
            logger.debug(f"[RPC {_rpc_index % total + 1}/{total}] Fetched balance {balance:.2f} USDC via {rpc}")
            return balance          # success – keep current RPC index
        except Exception as e:
            logger.debug(f"[RPC {_rpc_index % total + 1}/{total}] {rpc} failed: {e}")
            _rpc_index += 1         # rotate to next RPC for this and future attempts

    return None  # all RPCs failed


def get_portfolio_stats():
    """Calculate overall portfolio statistics and fetch USDC balance"""
    global _balance_cache, _balance_ts, _portfolio_cache, _portfolio_ts

    try:
        now = time.time()
        
        # 5 second cache for the full stats grid
        if _portfolio_cache and (now - _portfolio_ts < 5):
            return _portfolio_cache

        balance = 0

        # Method 1: Try using authenticated CLOB client (kept for compatibility)
        try:
            client = get_clob_client()
            try:
                bal_data = client.get_balance_allowance()
                if isinstance(bal_data, dict):
                    for key in ['balance', 'available_balance', 'total_balance']:
                        if key in bal_data:
                            balance = float(bal_data[key]) / 10**6
                            break
                elif hasattr(bal_data, 'balance'):
                    balance = float(bal_data.balance) / 10**6
            except Exception:
                try:
                    bal_data = client.get_balance()
                    if isinstance(bal_data, (int, float)):
                        balance = float(bal_data) / 10**6
                    elif isinstance(bal_data, dict) and 'balance' in bal_data:
                        balance = float(bal_data['balance']) / 10**6
                    elif hasattr(bal_data, 'balance'):
                        balance = float(bal_data.balance) / 10**6
                except Exception:
                    pass
        except Exception:
            pass

        # Method 2: Blockchain with RPC fallback chain
        if balance == 0:
            try:
                fetched = _fetch_usdc_balance_with_fallback()
                if fetched is not None:
                    balance = fetched
                    _balance_cache = balance        # update cache with fresh value
                    _balance_ts = time.time()
                elif _balance_cache is not None:
                    # All RPCs failed – use cached value silently
                    balance = _balance_cache
                    logger.debug(f"[Balance] All RPCs failed, using cached {balance:.2f} USDC")
                else:
                    log_dynamic(logger, "[WARNING] Could not fetch balance from any source", category="BALANCE_ERROR")
            except ImportError:
                logger.debug("[DEBUG] web3 not installed – skipping blockchain balance check")
        else:
            # CLOB succeeded – also update cache
            _balance_cache = balance
            _balance_ts = time.time()

        positions = get_positions()
        
        total_cost = sum(p.get("cost_basis", 0) for p in positions)
        total_value = sum(p.get("current_value", 0) for p in positions)
        total_pnl = total_value - total_cost
        
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
            SELECT SUM(pnl) as closed_pnl, COUNT(*) as closed_count
            FROM trades 
            WHERE status = 'CLOSED' AND pnl IS NOT NULL
        """)
        row = cursor.fetchone()
        closed_pnl = row[0] if row[0] else 0
        closed_count = row[1] if row[1] else 0
        conn.close()
        
        withdrawals = load_withdrawals()
        total_withdrawn = sum(w.get("amount", 0) for w in withdrawals)
        
        result = {
            "account_balance": round(balance, 2), 
            "open_positions": len(positions),
            "total_cost_basis": round(total_cost, 2),
            "total_current_value": round(total_value, 2),
            "unrealized_pnl": round(total_pnl, 2),
            "realized_pnl": round(closed_pnl, 2),
            "total_pnl": round(total_pnl + closed_pnl, 2),
            "total_withdrawn": round(total_withdrawn, 2),
            "closed_positions": closed_count
        }
        
        # Update cache
        _portfolio_cache = result
        _portfolio_ts = now
        
        return result
    except Exception as e:
        print(f"Error calculating portfolio stats: {e}")
        return {
            "open_positions": 0,
            "total_cost_basis": 0,
            "total_current_value": 0,
            "unrealized_pnl": 0,
            "realized_pnl": 0,
            "total_pnl": 0,
            "total_withdrawn": 0,
            "closed_positions": 0
        }


def load_withdrawals():
    """Load withdrawal history"""
    try:
        if os.path.exists(WITHDRAWALS_FILE):
            with open(WITHDRAWALS_FILE, 'r') as f:
                return json.load(f)
    except:
        pass
    return []


def save_withdrawals(withdrawals):
    """Save withdrawal history"""
    try:
        with open(WITHDRAWALS_FILE, 'w') as f:
            json.dump(withdrawals, f, indent=2)
    except Exception as e:
        print(f"Error saving withdrawals: {e}")


def load_accounts():
    """Load target accounts configuration"""
    try:
        if os.path.exists(ACCOUNTS_FILE):
            with open(ACCOUNTS_FILE, 'r') as f:
                data = json.load(f)
                return data.get("accounts", [])
    except:
        pass
    return []


# ============================================================================
# API ROUTES
# ============================================================================

@app.route('/')
def index():
    """Serve the main GUI"""
    return render_template('index.html')


@app.route('/api/status', methods=['GET'])
def get_status():
    """Get bot status"""
    try:
        if os.path.exists(STATUS_FILE):
            with open(STATUS_FILE, 'r') as f:
                content = f.read().strip()
                if content:
                    status = json.loads(content)
                else:
                    # File is empty (race condition with writer) — use defaults
                    status = None
        else:
            status = None

        if status is None:
            status = {
                "running": False,
                "dry_run": True,
                "last_check": None,
                "stats": {},
                "message": "Bot not started",
                "tracked_accounts": 0,
                "enabled_accounts": 0
            }
            
        # Add dynamic header stats
        try:
            accounts = load_accounts()
            wallets_found = len(accounts)
        except:
            wallets_found = 0
            
        db_records = 0
        last_trade_time = None
        try:
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT COUNT(*) FROM trades")
            row = cursor.fetchone()
            if row:
                db_records = row[0]
                
            cursor.execute("SELECT timestamp FROM trades ORDER BY timestamp DESC LIMIT 1")
            row = cursor.fetchone()
            if row:
                last_trade_time = row[0]
            conn.close()
        except:
            pass
            
        events_session = status.get("stats", {}).get("total_copied", 0)
        live_events = status.get("stats", {}).get("live_copies", 0)
        dry_events = status.get("stats", {}).get("dry_run_copies", 0)
        
        status["wallets_found"] = wallets_found
        status["db_records"] = db_records
        status["last_trade_time"] = last_trade_time
        status["events_session"] = events_session
        status["live_events_session"] = live_events
        status["dry_events_session"] = dry_events
        
        # Override running status based on actual thread state if running within the GUI
        status["header_stats"] = {
            "wallets_found": wallets_found,
            "events_session": events_session,
            "db_records": db_records,
            "last_trade_time": last_trade_time
        }
        
        status["funder_address"] = FUNDER_ADDRESS
        
        global bot_thread
        if bot_thread is None or not bot_thread.is_alive():
            status["running"] = False
            status["message"] = "Bot stopped"
        
        return jsonify(status)
    
    except Exception as e:
        logger.exception(f"API Error in /api/status: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/bot/start', methods=['POST'])
def start_bot():
    """Start the copy trading bot"""
    global bot_instance, bot_thread
    
    try:
        from continuous_bot import CopyTradingBot
        
        if bot_thread and bot_thread.is_alive():
            return jsonify({"error": "Bot already running"}), 400
        
        bot_instance = CopyTradingBot()
        
        # Start bot in separate thread
        bot_thread = threading.Thread(target=bot_instance.start, kwargs={"check_interval": 0.01})
        bot_thread.daemon = True
        bot_thread.start()
        
        return jsonify({"success": True, "message": "Bot started"})
    
    except Exception as e:
        logger.exception(f"API Error in /api/bot/start: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/bot/stop', methods=['POST'])
def stop_bot():
    """Stop the copy trading bot"""
    global bot_instance
    
    try:
        if bot_instance:
            bot_instance.stop()
            return jsonify({"success": True, "message": "Bot stopped"})
        else:
            return jsonify({"error": "Bot not running"}), 400
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/bot/dry-run', methods=['POST'])
def toggle_dry_run():
    """Toggle dry run mode"""
    global bot_instance
    
    try:
        data = request.json
        dry_run = data.get('dry_run', True)
        
        if bot_instance:
            bot_instance.set_dry_run(dry_run)
        
        return jsonify({"success": True, "dry_run": dry_run})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/positions', methods=['GET'])
def api_get_positions():
    """Get current positions"""
    try:
        positions = get_positions()
        return jsonify(positions)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/simulated_positions', methods=['GET'])
def api_get_simulated_positions():
    """Get simulated dry run positions"""
    try:
        positions = get_simulated_positions()
        return jsonify(positions)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/simulated_positions/clear', methods=['POST'])
def api_clear_simulated_positions():
    """Wipe all simulated trades"""
    try:
        import sqlite3
        import os
        sim_db_path = "simulated_history.db"
        if os.path.exists(sim_db_path):
            conn = sqlite3.connect(sim_db_path)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM trades")
            conn.commit()
            conn.close()
            return jsonify({"success": True, "message": "Simulated trades cleared."})
        else:
            return jsonify({"success": True, "message": "No simulated db found."})
    except Exception as e:
        logger.exception(f"Error clearing simulated DB: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/portfolio', methods=['GET'])
def api_portfolio_stats():
    """Get portfolio statistics"""
    try:
        stats = get_portfolio_stats()
        return jsonify(stats)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/position/close', methods=['POST'])
def close_position():
    """Close a specific position (full or partial)"""
    try:
        data = request.json
        token_id = data.get('token_id')
        amount = float(data.get('amount'))  # Amount to sell
        dry_run = data.get('dry_run', False)
        
        if not token_id or amount <= 0:
            return jsonify({"error": "Invalid token_id or amount"}), 400
        
        if dry_run:
            return jsonify({
                "success": True,
                "message": f"DRY RUN: Would sell {amount} shares",
                "dry_run": True
            })
        
        # Execute sell order
        client = get_clob_client()
        order = MarketOrderArgs(
            token_id=token_id,
            amount=amount,
            side=SELL,
            order_type=OrderType.FOK
        )
        signed_order = client.create_market_order(order)
        client.post_order(signed_order, OrderType.FOK)
        
        return jsonify({
            "success": True,
            "message": f"Successfully sold {amount} shares"
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/panic-sell', methods=['POST'])
def api_panic_sell():
    """Close all positions immediately"""
    try:
        data = request.json
        dry_run = data.get('dry_run', False)
        
        positions = get_positions()
        
        if not positions:
            return jsonify({"success": True, "message": "No positions to close", "closed": []})
        
        if dry_run:
            return jsonify({
                "success": True,
                "message": f"DRY RUN: Would close {len(positions)} positions",
                "dry_run": True,
                "positions": positions
            })
        
        # Close all positions
        client = get_clob_client()
        closed = []
        errors = []
        
        for pos in positions:
            try:
                token_id = pos.get("asset")
                size = float(pos.get("size", 0))
                title = pos.get("title", "Unknown")
                
                if size > 0:
                    order = MarketOrderArgs(
                        token_id=token_id,
                        amount=size,
                        side=SELL,
                        order_type=OrderType.FOK
                    )
                    signed_order = client.create_market_order(order)
                    client.post_order(signed_order, OrderType.FOK)
                    
                    closed.append({
                        "title": title,
                        "size": size,
                        "pnl": pos.get("pnl", 0)
                    })
            
            except Exception as e:
                errors.append({
                    "title": pos.get("title", "Unknown"),
                    "error": str(e)
                })
        
        return jsonify({
            "success": True,
            "message": f"Closed {len(closed)} positions",
            "closed": closed,
            "errors": errors
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/withdrawals', methods=['GET'])
def api_get_withdrawals():
    """Get withdrawal history"""
    try:
        withdrawals = load_withdrawals()
        return jsonify(withdrawals)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/withdrawals', methods=['POST'])
def api_add_withdrawal():
    """Record a new withdrawal"""
    try:
        data = request.json
        amount = float(data.get('amount', 0))
        note = data.get('note', '')
        
        if amount <= 0:
            return jsonify({"error": "Invalid amount"}), 400
        
        withdrawals = load_withdrawals()
        
        withdrawal = {
            "id": len(withdrawals) + 1,
            "amount": amount,
            "note": note,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "date": datetime.now(timezone.utc).strftime('%Y-%m-%d')
        }
        
        withdrawals.append(withdrawal)
        save_withdrawals(withdrawals)
        
        return jsonify({"success": True, "withdrawal": withdrawal})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/withdrawals/search', methods=['GET'])
def api_search_withdrawals():
    """Search withdrawals by date range"""
    try:
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        withdrawals = load_withdrawals()
        
        if start_date and end_date:
            filtered = [
                w for w in withdrawals
                if start_date <= w.get('date', '') <= end_date
            ]
            
            total = sum(w.get('amount', 0) for w in filtered)
            
            return jsonify({
                "withdrawals": filtered,
                "total": round(total, 2),
                "count": len(filtered)
            })
        
        return jsonify({
            "withdrawals": withdrawals,
            "total": sum(w.get('amount', 0) for w in withdrawals),
            "count": len(withdrawals)
        })
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# MULTI-ACCOUNT MANAGEMENT ROUTES
# ============================================================================

@app.route('/api/accounts', methods=['GET'])
def api_get_accounts():
    """Get all target accounts"""
    try:
        accounts = load_accounts()
        return jsonify(accounts)
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def analyze_wallet_external(address):
    """
    Call the Node.js scraper analyzer for a single wallet.
    Returns a dict with processed stats and tags.
    """
    import subprocess
    import json
    
    scrapper_dir = os.path.join(os.getcwd(), "polymarket-profitablewallets-scrapper")
    script_path = os.path.join(scrapper_dir, "src", "analyze_single.js")
    
    try:
        # Run node script
        result = subprocess.run(
            ["node", script_path, address],
            capture_output=True,
            text=True,
            cwd=scrapper_dir,
            timeout=30
        )
        
        if result.returncode != 0:
            logger.error(f"Analysis script failed for {address}: {result.stderr}")
            return None, result.stderr
            
        data = json.loads(result.stdout)
        return data, None
        
    except Exception as e:
        logger.exception(f"Exception during external analysis of {address}: {e}")
        return None, str(e)


@app.route('/api/accounts/analyze/<address>', methods=['POST'])
def api_analyze_account(address):
    """Enrich an existing account with fresh stats and tags"""
    try:
        address = address.strip().lower()
        logger.info(f"Triggering deep analysis for {address}...")
        
        data, error = analyze_wallet_external(address)
        if error:
            return jsonify({"error": f"Analysis failed: {error}"}), 500
            
        # Update accounts.json
        accounts = load_accounts()
        updated = False
        
        for acc in accounts:
            if acc.get('address', '').lower() == address:
                # Merge stats
                acc['pnl'] = data.get('pnl', acc.get('pnl', 0))
                acc['winRate'] = data.get('winRate', acc.get('winRate', 0))
                acc['rank'] = data.get('rank', acc.get('rank', 9999))
                
                # Merge tags (unique)
                new_tags = data.get('tags', [])
                existing_tags = acc.get('tags', [])
                acc['tags'] = list(set(existing_tags + new_tags))
                
                # Full stats enrichment
                acc['enrichment'] = {
                    "totalTrades": data.get('totalTrades', 0),
                    "activePositions": data.get('activePositions', 0),
                    "avgTradeSize": data.get('avgTradeSize', 0),
                    "tradesPerDay": data.get('tradesPerDay', 0),
                    "lastTradeAt": data.get('lastTradeAt'),
                    "lastUpdate": datetime.now(timezone.utc).isoformat()
                }
                updated = True
                break
        
        if updated:
            with open(ACCOUNTS_FILE, 'w') as f:
                json.dump({"accounts": accounts}, f, indent=2)
            
            # If bot is running, force it to reload accounts
            global bot_instance
            if bot_instance:
                bot_instance.sync_account_stats()
                
            return jsonify({"success": True, "data": data})
        else:
            return jsonify({"error": "Account not found in tracking list"}), 404
            
    except Exception as e:
        logger.exception(f"Error in api_analyze_account: {e}")
        return jsonify({"error": str(e)}), 500


@app.route('/api/accounts', methods=['POST'])
def api_add_account():
    """Add a new target account"""
    global bot_instance
    
    try:
        data = request.json
        address = data.get('address', '').strip()
        name = data.get('name', '').strip()
        bet_amount = data.get('bet_amount')
        auto_analyze = data.get('auto_analyze', False)
        
        if not address:
            return jsonify({"error": "Address is required"}), 400
        
        address = address.lower()
        
        # 1. Basic properties
        new_account = {
            "address": address,
            "name": name or address[:10] + "...",
            "rank": 9999,
            "score": 0,
            "winRate": 0,
            "pnl": 0,
            "tags": ["MANUAL"],
            "enabled": True,
            "bet_amount_override": bet_amount,
            "added_date": datetime.now(timezone.utc).isoformat()
        }
        
        # 2. Optional deep analysis
        if auto_analyze:
            logger.info(f"Auto-enriching new wallet {address}...")
            enriched_data, error = analyze_wallet_external(address)
            if enriched_data:
                new_account['pnl'] = enriched_data.get('pnl', 0)
                new_account['winRate'] = enriched_data.get('winRate', 0)
                new_account['rank'] = enriched_data.get('rank', 9999)
                new_account['tags'] = list(set(new_account['tags'] + enriched_data.get('tags', [])))
                new_account['enrichment'] = {
                    "totalTrades": enriched_data.get('totalTrades', 0),
                    "activePositions": enriched_data.get('activePositions', 0),
                    "avgTradeSize": enriched_data.get('avgTradeSize', 0),
                    "tradesPerDay": enriched_data.get('tradesPerDay', 0),
                    "lastTradeAt": enriched_data.get('lastTradeAt'),
                    "lastUpdate": datetime.now(timezone.utc).isoformat()
                }

        if bot_instance:
            # We bypass the bot's simplified add_target_account and do it manually here 
            # to support the new enrichment data structure.
            accounts = load_accounts()
            if any(acc.get('address', '').lower() == address for acc in accounts):
                return jsonify({"error": "Account already exists"}), 400
            
            accounts.append(new_account)
            with open(ACCOUNTS_FILE, 'w') as f:
                json.dump({"accounts": accounts}, f, indent=2)
            
            bot_instance.sync_account_stats()
        else:
            # Bot not running, manually add to file
            accounts = load_accounts()
            
            if any(acc.get('address', '').lower() == address for acc in accounts):
                return jsonify({"error": "Account already exists"}), 400
            
            accounts.append(new_account)
            
            with open(ACCOUNTS_FILE, 'w') as f:
                json.dump({"accounts": accounts}, f, indent=2)
        
        return jsonify({"success": True, "message": "Account added successfully", "account": new_account})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/accounts/<address>', methods=['DELETE'])
def api_remove_account(address):
    """Remove a target account"""
    global bot_instance
    
    try:
        if bot_instance:
            bot_instance.remove_target_account(address)
        else:
            accounts = load_accounts()
            accounts = [acc for acc in accounts if acc.get('address') != address]
            
            with open(ACCOUNTS_FILE, 'w') as f:
                json.dump({"accounts": accounts}, f, indent=2)
        
        return jsonify({"success": True, "message": "Account removed"})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/accounts/<address>/toggle', methods=['POST'])
def api_toggle_account(address):
    """Enable/disable an account"""
    global bot_instance
    
    try:
        data = request.json
        enabled = data.get('enabled', True)
        
        if bot_instance:
            success = bot_instance.toggle_account(address, enabled)
            if not success:
                return jsonify({"error": "Account not found"}), 404
        else:
            accounts = load_accounts()
            found = False
            
            for acc in accounts:
                if acc.get('address') == address:
                    acc['enabled'] = enabled
                    found = True
                    break
            
            if not found:
                return jsonify({"error": "Account not found"}), 404
            
            with open(ACCOUNTS_FILE, 'w') as f:
                json.dump({"accounts": accounts}, f, indent=2)
        
        return jsonify({"success": True, "enabled": enabled})
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# EXCEL EXPORT ROUTES
# ============================================================================

@app.route('/api/export/positions', methods=['GET'])
def export_positions():
    """Export current positions to Excel"""
    try:
        positions = get_positions()
        
        if not positions:
            return jsonify({"error": "No positions to export"}), 404
        
        # Prepare data for Excel
        data = []
        for pos in positions:
            data.append({
                'Market': pos.get('title', 'Unknown'),
                'Outcome': pos.get('outcome', 'Unknown'),
                'Size (shares)': pos.get('size', 0),
                'Entry Price': pos.get('price', 0),
                'Current Price': pos.get('currentPrice', 0),
                'Cost Basis': pos.get('cost_basis', 0),
                'Current Value': pos.get('current_value', 0),
                'P&L ($)': pos.get('pnl', 0),
                'P&L (%)': pos.get('pnl_percent', 0),
                'Condition ID': pos.get('conditionId', ''),
                'Token ID': pos.get('asset', '')
            })
        
        df = pd.DataFrame(data)
        
        # Create Excel file in memory
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Positions')
            
            # Auto-adjust column widths
            worksheet = writer.sheets['Positions']
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).apply(len).max(),
                    len(col)
                )
                worksheet.column_dimensions[chr(65 + idx)].width = min(max_length + 2, 50)
        
        output.seek(0)
        
        filename = f"polymarket_positions_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/export/history', methods=['GET'])
def export_history():
    """Export trade history to Excel"""
    try:
        conn = sqlite3.connect(DB_PATH)
        
        # Get all trades
        query = """
            SELECT 
                id,
                timestamp,
                created_date,
                market_title,
                outcome,
                side,
                size,
                price,
                status,
                pnl,
                hold_duration_hours
            FROM trades
            ORDER BY timestamp DESC
        """
        
        df = pd.read_sql_query(query, conn)
        conn.close()
        
        if df.empty:
            return jsonify({"error": "No trade history to export"}), 404
        
        # Format timestamp
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='s')
        
        # Rename columns for readability
        df.columns = [
            'Trade ID',
            'Timestamp',
            'Date',
            'Market',
            'Outcome',
            'Side',
            'Size',
            'Price',
            'Status',
            'P&L',
            'Hold Duration (hrs)'
        ]
        
        # Create Excel file
        output = BytesIO()
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Trade History')
            
            # Auto-adjust columns
            worksheet = writer.sheets['Trade History']
            for idx, col in enumerate(df.columns):
                max_length = max(
                    df[col].astype(str).apply(len).max(),
                    len(col)
                )
                worksheet.column_dimensions[chr(65 + idx)].width = min(max_length + 2, 50)
        
        output.seek(0)
        
        filename = f"polymarket_history_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/api/export/full', methods=['GET'])
def export_full_report():
    """Export comprehensive report with multiple sheets"""
    try:
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            # Sheet 1: Portfolio Summary
            stats = get_portfolio_stats()
            summary_data = {
                'Metric': [
                    'Open Positions',
                    'Total Cost Basis',
                    'Total Current Value',
                    'Unrealized P&L',
                    'Realized P&L',
                    'Total P&L',
                    'Total Withdrawn',
                    'Closed Positions'
                ],
                'Value': [
                    stats['open_positions'],
                    f"${stats['total_cost_basis']:.2f}",
                    f"${stats['total_current_value']:.2f}",
                    f"${stats['unrealized_pnl']:.2f}",
                    f"${stats['realized_pnl']:.2f}",
                    f"${stats['total_pnl']:.2f}",
                    f"${stats['total_withdrawn']:.2f}",
                    stats['closed_positions']
                ]
            }
            df_summary = pd.DataFrame(summary_data)
            df_summary.to_excel(writer, index=False, sheet_name='Summary')
            
            # Sheet 2: Open Positions
            positions = get_positions()
            if positions:
                pos_data = []
                for pos in positions:
                    pos_data.append({
                        'Market': pos.get('title', ''),
                        'Outcome': pos.get('outcome', ''),
                        'Size': pos.get('size', 0),
                        'Entry Price': pos.get('price', 0),
                        'Current Price': pos.get('currentPrice', 0),
                        'Cost Basis': pos.get('cost_basis', 0),
                        'Current Value': pos.get('current_value', 0),
                        'P&L': pos.get('pnl', 0),
                        'P&L %': pos.get('pnl_percent', 0)
                    })
                df_positions = pd.DataFrame(pos_data)
                df_positions.to_excel(writer, index=False, sheet_name='Open Positions')
            
            # Sheet 3: Trade History
            conn = sqlite3.connect(DB_PATH)
            df_history = pd.read_sql_query(
                """
                SELECT 
                    timestamp,
                    market_title as Market,
                    outcome as Outcome,
                    side as Side,
                    size as Size,
                    price as Price,
                    status as Status,
                    pnl as 'P&L'
                FROM trades
                ORDER BY timestamp DESC
                """,
                conn
            )
            if not df_history.empty:
                df_history['timestamp'] = pd.to_datetime(df_history['timestamp'], unit='s')
                df_history.to_excel(writer, index=False, sheet_name='Trade History')
            
            # Sheet 4: Withdrawals
            withdrawals = load_withdrawals()
            if withdrawals:
                df_withdrawals = pd.DataFrame(withdrawals)
                if 'timestamp' in df_withdrawals.columns:
                    df_withdrawals = df_withdrawals[['date', 'amount', 'note', 'timestamp']]
                    df_withdrawals.columns = ['Date', 'Amount', 'Note', 'Timestamp']
                df_withdrawals.to_excel(writer, index=False, sheet_name='Withdrawals')
            
            # Sheet 5: Account Stats
            if os.path.exists(STATUS_FILE):
                with open(STATUS_FILE, 'r') as f:
                    status = json.load(f)
                    account_stats = status.get('stats', {}).get('accounts', {})
                    
                    if account_stats:
                        acc_data = []
                        for addr, stats in account_stats.items():
                            acc_data.append({
                                'Address': addr[:10] + '...',
                                'Name': stats.get('name', ''),
                                'Trades Copied': stats.get('trades_copied', 0),
                                'Enabled': stats.get('enabled', True),
                                'Last Check': stats.get('last_check', '')
                            })
                        df_accounts = pd.DataFrame(acc_data)
                        df_accounts.to_excel(writer, index=False, sheet_name='Tracked Accounts')
            
            conn.close()
        
        output.seek(0)
        
        filename = f"polymarket_full_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        
        return send_file(
            output,
            mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
            as_attachment=True,
            download_name=filename
        )
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


if __name__ == '__main__':
    # Ensure database exists
    if not os.path.exists(DB_PATH):
        try:
            from betting_logger import BettingLogger
            logger = BettingLogger()
            print("Database initialized")
        except:
            print("Warning: Could not initialize database")
    
    # Ensure accounts file exists
    if not os.path.exists(ACCOUNTS_FILE):
        with open(ACCOUNTS_FILE, 'w') as f:
            json.dump({"accounts": []}, f, indent=2)
        logger.info("Created accounts.json")
    
    logger.info("\n" + "="*80)
    logger.info("  Polymarket Multi-Account Copy Trading Bot - Web GUI")
    logger.info("  Starting server at http://localhost:5000")
    logger.info("  Features:")
    logger.info("    • Multi-account tracking with configurable delays")
    logger.info("    • Excel export for positions, history, and full reports")
    logger.info("    • Real-time portfolio monitoring")
    logger.info("    • Per-account statistics and management")
    logger.info("="*80 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
