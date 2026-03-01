#!/usr/bin/env python3
"""
AGGRESSIVE DIAGNOSTIC - Shows exactly what the API returns and why bot might miss trades
"""

import json
import os
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

ELKMONKEY_ADDRESS = "0x6031b6eed1c97e853c6e0f03ad3ce3529351f96d"
FUNDER_ADDRESS = os.getenv("FUNDER_ADDRESS")
DATA_API = "https://data-api.polymarket.com"
SEEN_TRADES_FILE = "seen_trades.json"

print("\n" + "="*80)
print("AGGRESSIVE DIAGNOSTIC - LIVE API INSPECTION")
print("="*80 + "\n")

# Step 1: Check seen_trades.json
print("Step 1: Inspecting seen_trades.json...")
try:
    with open(SEEN_TRADES_FILE, 'r') as f:
        content = f.read()
        print(f"  Raw content: {content}")
        
    with open(SEEN_TRADES_FILE, 'r') as f:
        seen_trades = json.load(f)
        
    print(f"  Parsed: {len(seen_trades)} entries")
    
    if seen_trades:
        print(f"  First 3 IDs: {seen_trades[:3]}")
        
        # Check for any None/null
        null_count = sum(1 for x in seen_trades if x is None)
        if null_count > 0:
            print(f"  ⚠️ WARNING: {null_count} null entries found!")
    else:
        print(f"  ✓ File is empty - bot should copy ANY new trade")
        
except FileNotFoundError:
    print(f"  ✓ File doesn't exist - bot will copy ANY trade")
    seen_trades = []
except Exception as e:
    print(f"  ✗ Error: {e}")
    seen_trades = []

# Step 2: Raw API call
print("\nStep 2: Making RAW API call to Polymarket...")
print(f"  URL: {DATA_API}/activity?user={ELKMONKEY_ADDRESS[:10]}...&limit=50")

try:
    start_time = datetime.now()
    response = requests.get(
        f"{DATA_API}/activity",
        params={"user": ELKMONKEY_ADDRESS, "limit": 50},
        timeout=10
    )
    elapsed = (datetime.now() - start_time).total_seconds()
    
    print(f"  Status Code: {response.status_code}")
    print(f"  Response Time: {elapsed:.2f}s")
    print(f"  Response Size: {len(response.text)} bytes")
    
    if response.status_code != 200:
        print(f"  ✗ API ERROR!")
        print(f"  Response: {response.text[:500]}")
        exit(1)
    
    activities = response.json()
    print(f"  ✓ Parsed JSON: {len(activities)} activities")
    
except Exception as e:
    print(f"  ✗ API call failed: {e}")
    import traceback
    traceback.print_exc()
    exit(1)

# Step 3: Analyze ALL activities
print("\nStep 3: Analyzing ALL activities (not just trades)...")
print(f"\n  Activity breakdown:")

types = {}
for act in activities:
    act_type = act.get("type", "UNKNOWN")
    types[act_type] = types.get(act_type, 0) + 1

for act_type, count in sorted(types.items(), key=lambda x: -x[1]):
    print(f"    {act_type}: {count}")

# Step 4: Focus on TRADE activities
print("\nStep 4: Examining TRADE activities in detail...")

trades = [a for a in activities if a.get("type") == "TRADE"]
print(f"  Total TRADE activities: {len(trades)}")

if not trades:
    print(f"\n  ✗✗✗ NO TRADES FOUND! ✗✗✗")
    print(f"  This is the problem - API returned no trades at all!")
    print(f"\n  Possible causes:")
    print(f"    1. elkmonkey's address is wrong")
    print(f"    2. API is not returning trade data")
    print(f"    3. There's a delay in API updates")
    exit(1)

# Analyze trades by side
buy_trades = [t for t in trades if t.get("side") == "BUY"]
sell_trades = [t for t in trades if t.get("side") == "SELL"]

print(f"  BUY trades: {len(buy_trades)}")
print(f"  SELL trades: {len(sell_trades)}")

if not buy_trades:
    print(f"\n  ✗✗✗ NO BUY TRADES FOUND! ✗✗✗")
    print(f"  All trades are SELLs - bot only copies BUYs")
    print(f"\n  Recent SELL trades:")
    for i, trade in enumerate(sell_trades[:3], 1):
        title = trade.get("title", "Unknown")
        timestamp = trade.get("timestamp", 0)
        age = (datetime.now(timezone.utc).timestamp() - timestamp) / 60
        print(f"    {i}. {title[:50]} ({age:.1f}m ago)")
    exit(1)

# Step 5: Detailed BUY trade analysis
print("\nStep 5: DETAILED BUY TRADE ANALYSIS")
print("="*80)

for i, trade in enumerate(buy_trades[:10], 1):
    print(f"\nTrade #{i}:")
    print("-" * 60)
    
    # Extract all fields
    trade_id = trade.get("id")
    title = trade.get("title", "Unknown")
    outcome = trade.get("outcome", "Unknown")
    side = trade.get("side", "Unknown")
    price = trade.get("price", 0)
    size = trade.get("size", 0)
    timestamp = trade.get("timestamp", 0)
    condition_id = trade.get("conditionId")
    outcome_index = trade.get("outcomeIndex")
    asset = trade.get("asset")
    
    # Calculate age
    if timestamp:
        trade_time = datetime.fromtimestamp(timestamp, timezone.utc)
        now = datetime.now(timezone.utc)
        age_seconds = (now.timestamp() - timestamp)
        age_minutes = age_seconds / 60
        age_str = f"{age_minutes:.1f}m ago" if age_minutes < 60 else f"{age_minutes/60:.1f}h ago"
    else:
        trade_time = "NO TIMESTAMP"
        age_str = "UNKNOWN AGE"
    
    # Check if seen
    is_seen = trade_id in seen_trades if trade_id else False
    
    # Print details
    print(f"  Market: {title}")
    print(f"  Outcome: {outcome}")
    print(f"  Side: {side}")
    print(f"  Price: {price*100:.1f}¢")
    print(f"  Size: {size:.2f} shares")
    print(f"  Amount: ${size * price:.2f}")
    print(f"  Time: {trade_time} ({age_str})")
    print(f"  Trade ID: {trade_id}")
    print(f"  Condition ID: {condition_id}")
    print(f"  Outcome Index: {outcome_index}")
    print(f"  Asset: {asset}")
    
    # Decision logic
    print(f"\n  BOT DECISION:")
    
    if not trade_id:
        print(f"    ✗ SKIP - No trade ID")
        continue
    
    if is_seen:
        print(f"    ✗ SKIP - Already in seen_trades.json")
        continue
    
    print(f"    ✓✓✓ SHOULD COPY THIS TRADE! ✓✓✓")
    
    # Check if user has position
    print(f"\n  Checking if you already have this position...")
    try:
        pos_response = requests.get(
            f"{DATA_API}/positions",
            params={"user": FUNDER_ADDRESS, "sizeThreshold": 0},
            timeout=10
        )
        
        if pos_response.status_code == 200:
            positions = pos_response.json()
            has_position = False
            
            for pos in positions:
                if (pos.get("conditionId") == condition_id and 
                    pos.get("outcomeIndex") == outcome_index):
                    has_position = True
                    pos_size = pos.get("size", 0)
                    print(f"    ✗ You already have {pos_size} shares")
                    print(f"    → Bot would SKIP (already have position)")
                    break
            
            if not has_position:
                print(f"    ✓ You DON'T have this position")
                print(f"    → Bot SHOULD COPY!")
        else:
            print(f"    ⚠️ Could not check positions: {pos_response.status_code}")
            
    except Exception as e:
        print(f"    ⚠️ Error checking positions: {e}")

# Step 6: Summary
print("\n" + "="*80)
print("DIAGNOSTIC SUMMARY")
print("="*80 + "\n")

copyable_trades = [
    t for t in buy_trades 
    if t.get("id") and t.get("id") not in seen_trades
]

print(f"Total activities fetched: {len(activities)}")
print(f"Total TRADE activities: {len(trades)}")
print(f"Total BUY trades: {len(buy_trades)}")
print(f"Trades already seen: {len([t for t in buy_trades if t.get('id') in seen_trades])}")
print(f"Trades without ID: {len([t for t in buy_trades if not t.get('id')])}")
print(f"\n>>> COPYABLE TRADES: {len(copyable_trades)} <<<\n")

if copyable_trades:
    print("✓✓✓ THESE TRADES SHOULD BE COPIED: ✓✓✓")
    for trade in copyable_trades[:5]:
        title = trade.get("title", "Unknown")
        timestamp = trade.get("timestamp", 0)
        age = (datetime.now(timezone.utc).timestamp() - timestamp) / 60
        print(f"  • {title[:60]} ({age:.1f}m ago)")
    
    print(f"\nIf bot isn't copying these, the problem is in the bot code!")
    print(f"Check:")
    print(f"  1. Is elkmonkey account enabled in accounts.json?")
    print(f"  2. Are there errors in bot console?")
    print(f"  3. Is bot actually running (not frozen)?")
    
else:
    print("✗ NO COPYABLE TRADES FOUND")
    print("\nReasons why:")
    
    if len(buy_trades) == 0:
        print("  • No BUY trades from elkmonkey")
    elif len(copyable_trades) == 0:
        print("  • All BUY trades already in seen_trades.json")
        print(f"  • Clear seen_trades.json to re-copy them")

print("\n" + "="*80 + "\n")
