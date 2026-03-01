#!/usr/bin/env python3
"""
Flask Web GUI for Polymarket Copy Trading Bot
Enhanced with multi-account tracking and Excel export
"""

import os
import json
import sqlite3
import threading
from datetime import datetime, timezone
from flask import Flask, render_template, jsonify, request, send_file
from dotenv import load_dotenv
import requests
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import SELL
import pandas as pd
from io import BytesIO

load_dotenv()

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
    """Fetch current positions from Polymarket"""
    try:
        response = requests.get(
            f"{DATA_API}/positions",
            params={"user": FUNDER_ADDRESS, "sizeThreshold": 0},
            timeout=10
        )
        response.raise_for_status()
        positions = response.json()
        
        # Enhance positions with P&L data
        enhanced = []
        for pos in positions:
            size = float(pos.get("size", 0))
            entry_price = float(pos.get("price", 0))
            current_price = float(pos.get("currentPrice", entry_price))
            
            # Calculate P&L
            pnl = size * (current_price - entry_price)
            pnl_percent = ((current_price - entry_price) / entry_price * 100) if entry_price > 0 else 0
            
            enhanced.append({
                **pos,
                "pnl": round(pnl, 2),
                "pnl_percent": round(pnl_percent, 2),
                "current_value": round(size * current_price, 2),
                "cost_basis": round(size * entry_price, 2)
            })
        
        return enhanced
    
    except Exception as e:
        print(f"Error fetching positions: {e}")
        return []


def get_portfolio_stats():
    """Calculate overall portfolio statistics and fetch USDC balance"""
    try:
        balance = 0
        
        # Method 1: Try using authenticated CLOB client
        try:
            print("[DEBUG] Attempting to fetch balance using CLOB client...")
            client = get_clob_client()
            
            # Try the get_balance_allowance method
            try:
                bal_data = client.get_balance_allowance()
                print(f"[DEBUG] get_balance_allowance() returned: {bal_data}")
                
                if isinstance(bal_data, dict):
                    # Try different possible keys
                    for key in ["balance", "amount", "allowance"]:
                        if key in bal_data:
                            raw_balance = float(bal_data[key])
                            balance = raw_balance / 1_000_000  # USDC has 6 decimals
                            print(f"[DEBUG] Extracted balance from '{key}': {balance} USDC")
                            break
            except AttributeError:
                print("[DEBUG] get_balance_allowance() method not available")
            
            # Method 1b: Try get_balance if get_balance_allowance didn't work
            if balance == 0:
                try:
                    bal_data = client.get_balance()
                    print(f"[DEBUG] get_balance() returned: {bal_data}")
                    
                    if isinstance(bal_data, (int, float)):
                        balance = float(bal_data) / 1_000_000
                        print(f"[DEBUG] Balance from get_balance(): {balance} USDC")
                    elif isinstance(bal_data, dict) and "balance" in bal_data:
                        balance = float(bal_data["balance"]) / 1_000_000
                        print(f"[DEBUG] Balance from get_balance() dict: {balance} USDC")
                except AttributeError:
                    print("[DEBUG] get_balance() method not available")
                    
        except Exception as e:
            print(f"[DEBUG] CLOB client balance fetch failed: {e}")
        
        # Method 2: Try direct API call to gamma-api
        if balance == 0:
            try:
                print(f"[DEBUG] Attempting gamma-api balance fetch for {FUNDER_ADDRESS[:10]}...")
                balance_resp = requests.get(
                    f"{PROFILE_API}/balance",
                    params={"address": FUNDER_ADDRESS},
                    timeout=10
                )
                print(f"[DEBUG] Gamma API response status: {balance_resp.status_code}")
                
                if balance_resp.status_code == 200:
                    data = balance_resp.json()
                    print(f"[DEBUG] Gamma API response data: {data}")
                    
                    if isinstance(data, dict) and "balance" in data:
                        balance = float(data["balance"])
                        print(f"[DEBUG] Balance from gamma-api: {balance} USDC")
                else:
                    print(f"[DEBUG] Gamma API error: {balance_resp.text[:200]}")
            except Exception as e:
                print(f"[DEBUG] Gamma API balance fetch failed: {e}")
        
        # Method 3: Try CLOB API balances endpoint
        if balance == 0:
            try:
                print(f"[DEBUG] Attempting CLOB API balance fetch...")
                balance_resp = requests.get(
                    f"{CLOB_API}/balances",
                    params={"address": FUNDER_ADDRESS},
                    timeout=10
                )
                print(f"[DEBUG] CLOB API balances response status: {balance_resp.status_code}")
                
                if balance_resp.status_code == 200:
                    data = balance_resp.json()
                    print(f"[DEBUG] CLOB API balances data: {data}")
                    
                    if isinstance(data, list) and len(data) > 0:
                        # Look for USDC token
                        for token in data:
                            if isinstance(token, dict):
                                bal = float(token.get("balance", 0))
                                if bal > 0:
                                    balance = bal / 1_000_000
                                    print(f"[DEBUG] Balance from CLOB API: {balance} USDC")
                                    break
                    elif isinstance(data, dict) and "balance" in data:
                        balance = float(data["balance"]) / 1_000_000
                        print(f"[DEBUG] Balance from CLOB API dict: {balance} USDC")
                else:
                    print(f"[DEBUG] CLOB API error: {balance_resp.text[:200]}")
            except Exception as e:
                print(f"[DEBUG] CLOB API balance fetch failed: {e}")
        
        print(f"[DEBUG] Final balance value: ${balance:.2f} USDC")
        
        # Method 4: Check blockchain directly using web3 (most reliable)
        if balance == 0:
            try:
                print(f"[DEBUG] Attempting direct blockchain balance check...")
                from web3 import Web3
                
                # Connect to Polygon RPC (using dRPC for reliable public access)
                w3 = Web3(Web3.HTTPProvider('https://polygon.drpc.org'))
                
                # USDC contract on Polygon
                usdc_address = Web3.to_checksum_address('0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174')
                
                # ERC20 ABI for balanceOf
                erc20_abi = [
                    {
                        "constant": True,
                        "inputs": [{"name": "_owner", "type": "address"}],
                        "name": "balanceOf",
                        "outputs": [{"name": "balance", "type": "uint256"}],
                        "type": "function"
                    }
                ]
                
                usdc_contract = w3.eth.contract(address=usdc_address, abi=erc20_abi)
                user_address = Web3.to_checksum_address(FUNDER_ADDRESS)
                
                raw_balance = usdc_contract.functions.balanceOf(user_address).call()
                balance = raw_balance / 1_000_000  # USDC has 6 decimals
                
                print(f"[DEBUG] Blockchain balance: {balance} USDC (raw: {raw_balance})")
            except ImportError:
                print("[DEBUG] web3 not installed - skipping blockchain check")
                print("[DEBUG] Install with: pip install web3")
            except Exception as e:
                print(f"[DEBUG] Blockchain balance check failed: {e}")
        
        if balance == 0:
            print("[WARNING] Could not fetch balance from any source!")
            print("[INFO] Make sure you have USDC in your wallet on Polygon network")
        
        # ---------------------------------

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
        
        return {
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
                status = json.load(f)
        else:
            status = {
                "running": False,
                "dry_run": True,
                "last_check": None,
                "stats": {},
                "message": "Bot not started",
                "tracked_accounts": 0,
                "enabled_accounts": 0
            }
        
        return jsonify(status)
    
    except Exception as e:
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
        bot_thread = threading.Thread(target=bot_instance.start, kwargs={"check_interval": 60})
        bot_thread.daemon = True
        bot_thread.start()
        
        return jsonify({"success": True, "message": "Bot started"})
    
    except Exception as e:
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


@app.route('/api/accounts', methods=['POST'])
def api_add_account():
    """Add a new target account"""
    global bot_instance
    
    try:
        data = request.json
        address = data.get('address', '').strip()
        name = data.get('name', '').strip()
        bet_amount = data.get('bet_amount')
        
        if not address:
            return jsonify({"error": "Address is required"}), 400
        
        # Validate address format (basic check)
        if not address.startswith('0x') or len(address) != 42:
            return jsonify({"error": "Invalid Ethereum address format"}), 400
        
        if bot_instance:
            success, message = bot_instance.add_target_account(address, name, bet_amount)
            if not success:
                return jsonify({"error": message}), 400
        else:
            # Bot not running, manually add to file
            accounts = load_accounts()
            
            # Check if already exists
            if any(acc.get('address') == address for acc in accounts):
                return jsonify({"error": "Account already exists"}), 400
            
            accounts.append({
                "address": address,
                "name": name or address[:10] + "...",
                "enabled": True,
                "bet_amount_override": bet_amount,
                "added_date": datetime.now(timezone.utc).isoformat()
            })
            
            with open(ACCOUNTS_FILE, 'w') as f:
                json.dump({"accounts": accounts}, f, indent=2)
        
        return jsonify({"success": True, "message": "Account added successfully"})
    
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
        print("Created accounts.json")
    
    print("\n" + "="*80)
    print("  Polymarket Multi-Account Copy Trading Bot - Web GUI")
    print("  Starting server at http://localhost:5000")
    print("  Features:")
    print("    • Multi-account tracking with configurable delays")
    print("    • Excel export for positions, history, and full reports")
    print("    • Real-time portfolio monitoring")
    print("    • Per-account statistics and management")
    print("="*80 + "\n")
    
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
