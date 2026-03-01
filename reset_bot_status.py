#!/usr/bin/env python3
"""
Reset bot_status.json to match the current accounts.json
Use this when you've modified accounts but the bot hasn't updated the status yet
"""

import json
import os

ACCOUNTS_FILE = "accounts.json"
STATUS_FILE = "bot_status.json"

print("\n" + "="*80)
print("BOT STATUS RESET UTILITY")
print("="*80 + "\n")

# Load current accounts
print("1. Reading accounts.json...")
if os.path.exists(ACCOUNTS_FILE):
    with open(ACCOUNTS_FILE, 'r') as f:
        data = json.load(f)
        accounts = data.get("accounts", [])
    
    enabled_count = sum(1 for acc in accounts if acc.get("enabled", True))
    
    print(f"   ✓ Found {len(accounts)} accounts ({enabled_count} enabled)")
    
    if accounts:
        for i, acc in enumerate(accounts, 1):
            name = acc.get("name", "Unknown")
            addr = acc.get("address", "")[:10]
            enabled = acc.get("enabled", True)
            status = "ENABLED" if enabled else "DISABLED"
            print(f"   {i}. {name} ({addr}...) - {status}")
    else:
        print("   ℹ  No accounts configured")
else:
    print("   ✗ accounts.json not found!")
    accounts = []
    enabled_count = 0

# Reset status file
print("\n2. Resetting bot_status.json...")

# Load existing status to preserve some data
existing_stats = {}
if os.path.exists(STATUS_FILE):
    try:
        with open(STATUS_FILE, 'r') as f:
            old_status = json.load(f)
            existing_stats = old_status.get("stats", {})
            print(f"   ℹ  Preserving existing stats...")
    except:
        pass

# Create fresh status
new_status = {
    "running": False,
    "dry_run": True,
    "last_check": None,
    "stats": {
        "total_copied": existing_stats.get("total_copied", 0),
        "successful_copies": existing_stats.get("successful_copies", 0),
        "failed_copies": existing_stats.get("failed_copies", 0),
        "last_trade_copied": existing_stats.get("last_trade_copied"),
        "accounts": {}
    },
    "message": "Status reset - start bot to begin monitoring",
    "tracked_accounts": len(accounts),
    "enabled_accounts": enabled_count
}

# Initialize stats for each account
for account in accounts:
    addr = account.get("address", "")
    if addr:
        new_status["stats"]["accounts"][addr] = {
            "name": account.get("name", addr[:10]),
            "trades_copied": 0,
            "last_check": None,
            "last_trade": None,
            "enabled": account.get("enabled", True)
        }

# Save the reset status
with open(STATUS_FILE, 'w') as f:
    json.dump(new_status, f, indent=2)

print(f"   ✓ Status file reset!")
print(f"   → Tracked accounts: {len(accounts)}")
print(f"   → Enabled accounts: {enabled_count}")

print("\n" + "="*80)
print("DONE!")
print("="*80 + "\n")

if len(accounts) == 0:
    print("ℹ  You have no accounts configured.")
    print("   Add accounts through the web GUI or by editing accounts.json")
else:
    print("✓ Status file now matches accounts.json")
    print("  Refresh your browser to see the updated count")
    print("  Start the bot when ready: python continuous_bot.py")

print("\n" + "="*80 + "\n")
