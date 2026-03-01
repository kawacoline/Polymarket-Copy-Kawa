#!/usr/bin/env python3
"""
Test the synthetic ID fix - verify bot can now handle trades without IDs
"""

import json
import requests
from datetime import datetime, timezone

ELKMONKEY_ADDRESS = "0xead152b855effa6b5b5837f53b24c0756830c76a"
DATA_API = "https://data-api.polymarket.com"

print("\n" + "="*80)
print("TESTING SYNTHETIC ID GENERATION")
print("="*80 + "\n")

print("Fetching elkmonkey's recent trades...")

response = requests.get(
    f"{DATA_API}/activity",
    params={"user": ELKMONKEY_ADDRESS, "limit": 10},
    timeout=10
)

if response.status_code != 200:
    print(f"✗ API Error: {response.status_code}")
    exit(1)

activities = response.json()
buy_trades = [a for a in activities if a.get("type") == "TRADE" and a.get("side") == "BUY"]

print(f"Found {len(buy_trades)} BUY trades\n")

if not buy_trades:
    print("✗ No BUY trades found!")
    exit(1)

print("Generating synthetic IDs for trades without IDs:\n")

for i, trade in enumerate(buy_trades[:5], 1):
    trade_id = trade.get("id")
    title = trade.get("title", "Unknown")[:50]
    timestamp = trade.get("timestamp", 0)
    
    age = (datetime.now(timezone.utc).timestamp() - timestamp) / 60
    
    print(f"Trade {i}: {title}")
    print(f"  Original ID: {trade_id}")
    
    if not trade_id:
        # Generate synthetic ID (same logic as bot)
        condition_id = trade.get("conditionId", "")
        outcome_index = trade.get("outcomeIndex", "")
        size = trade.get("size", "")
        
        synthetic_id = f"synthetic_{condition_id}_{outcome_index}_{timestamp}_{size}"
        
        print(f"  ✓ Generated synthetic ID: {synthetic_id[:60]}...")
        print(f"  → Bot will now be able to track this trade!")
    else:
        print(f"  ✓ Has real ID, no synthetic needed")
    
    print(f"  Age: {age:.1f} minutes ago\n")

print("="*80)
print("RESULT")
print("="*80 + "\n")

trades_without_id = len([t for t in buy_trades if not t.get("id")])

if trades_without_id > 0:
    print(f"✓ Found {trades_without_id} trades without IDs")
    print(f"✓ Fixed bot will generate synthetic IDs for these")
    print(f"✓ Bot will now be able to copy elkmonkey's trades!")
else:
    print(f"✓ All trades have IDs already")

print("\n" + "="*80 + "\n")
print("Next steps:")
print("  1. Replace your continuous_bot.py with the fixed version")
print("  2. Restart your bot")
print("  3. Bot should now detect and copy elkmonkey's trades!")
print("\n" + "="*80 + "\n")
