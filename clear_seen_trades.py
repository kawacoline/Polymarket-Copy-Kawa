#!/usr/bin/env python3
"""
Clear Seen Trades - Allows bot to re-copy recent trades
USE WITH CAUTION: This will make the bot copy trades it already copied before
"""

import json
import os
from datetime import datetime

SEEN_TRADES_FILE = "seen_trades.json"

print("\n" + "="*80)
print("CLEAR SEEN TRADES")
print("="*80 + "\n")

# Check current state
if os.path.exists(SEEN_TRADES_FILE):
    try:
        with open(SEEN_TRADES_FILE, 'r') as f:
            current_trades = json.load(f)
        
        print(f"Current state: {len(current_trades)} trades marked as seen")
        
        if current_trades:
            print("\n⚠️  WARNING: This will clear the history and allow the bot to")
            print("   re-copy trades it already copied before!")
            print("\n   This means you might:")
            print("   • Buy positions you already have")
            print("   • Double your exposure to certain markets")
            print("   • Execute duplicate trades")
            
            response = input("\n   Are you sure you want to continue? (yes/no): ")
            
            if response.lower() != "yes":
                print("\n✗ Cancelled. No changes made.")
                exit(0)
            
            # Backup current file
            backup_name = f"seen_trades_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(backup_name, 'w') as f:
                json.dump(current_trades, f)
            print(f"\n✓ Backup created: {backup_name}")
            
            # Clear the file
            with open(SEEN_TRADES_FILE, 'w') as f:
                json.dump([], f)
            
            print(f"✓ Cleared {len(current_trades)} trades from seen_trades.json")
            print("\n✓ Bot will now copy trades it sees next check cycle")
            print("  (including recent trades from elkmonkey)")
        else:
            print("File is already empty - nothing to clear")
            
    except Exception as e:
        print(f"✗ Error: {e}")
else:
    print("seen_trades.json doesn't exist yet")
    with open(SEEN_TRADES_FILE, 'w') as f:
        json.dump([], f)
    print("✓ Created new empty file")

print("\n" + "="*80 + "\n")
print("Next steps:")
print("  1. The bot will detect 'new' trades on next check (60 seconds)")
print("  2. Watch the terminal for copy messages")
print("  3. Check your positions to verify trades executed")
print("\n" + "="*80 + "\n")
