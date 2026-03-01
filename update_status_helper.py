"""
Helper function to update bot_status.json when accounts change
This keeps the GUI in sync even when the bot isn't running
"""

import json
import os
from datetime import datetime, timezone

STATUS_FILE = "bot_status.json"
ACCOUNTS_FILE = "accounts.json"

def update_bot_status_for_accounts():
    """
    Update bot_status.json to reflect current accounts.json
    Call this whenever accounts are added/removed/toggled when bot isn't running
    """
    try:
        # Load current accounts
        accounts = []
        if os.path.exists(ACCOUNTS_FILE):
            with open(ACCOUNTS_FILE, 'r') as f:
                data = json.load(f)
                accounts = data.get("accounts", [])
        
        # Load existing status or create new one
        status = {
            "running": False,
            "dry_run": True,
            "last_check": None,
            "stats": {
                "total_copied": 0,
                "successful_copies": 0,
                "failed_copies": 0,
                "last_trade_copied": None,
                "accounts": {}
            },
            "message": "Bot stopped",
            "tracked_accounts": 0,
            "enabled_accounts": 0
        }
        
        if os.path.exists(STATUS_FILE):
            try:
                with open(STATUS_FILE, 'r') as f:
                    existing = json.load(f)
                    # Preserve important data
                    status["running"] = existing.get("running", False)
                    status["dry_run"] = existing.get("dry_run", True)
                    status["last_check"] = existing.get("last_check")
                    status["message"] = existing.get("message", "Bot stopped")
                    status["stats"]["total_copied"] = existing.get("stats", {}).get("total_copied", 0)
                    status["stats"]["successful_copies"] = existing.get("stats", {}).get("successful_copies", 0)
                    status["stats"]["failed_copies"] = existing.get("stats", {}).get("failed_copies", 0)
                    status["stats"]["last_trade_copied"] = existing.get("stats", {}).get("last_trade_copied")
                    # Preserve per-account stats for accounts that still exist
                    old_account_stats = existing.get("stats", {}).get("accounts", {})
            except:
                old_account_stats = {}
        else:
            old_account_stats = {}
        
        # Update account counts
        status["tracked_accounts"] = len(accounts)
        status["enabled_accounts"] = sum(1 for acc in accounts if acc.get("enabled", True))
        
        # Sync account stats
        for account in accounts:
            addr = account.get("address", "")
            if addr:
                # Preserve stats if they exist
                if addr in old_account_stats:
                    status["stats"]["accounts"][addr] = old_account_stats[addr]
                    # Update name and enabled status
                    status["stats"]["accounts"][addr]["name"] = account.get("name", addr[:10])
                    status["stats"]["accounts"][addr]["enabled"] = account.get("enabled", True)
                else:
                    # Create new stats entry
                    status["stats"]["accounts"][addr] = {
                        "name": account.get("name", addr[:10]),
                        "trades_copied": 0,
                        "last_check": None,
                        "last_trade": None,
                        "enabled": account.get("enabled", True)
                    }
        
        # Save updated status
        with open(STATUS_FILE, 'w') as f:
            json.dump(status, f, indent=2)
        
        return True
    
    except Exception as e:
        print(f"Error updating bot status: {e}")
        return False
