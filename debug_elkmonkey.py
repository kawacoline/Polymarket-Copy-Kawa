#!/usr/bin/env python3
"""
Debug elkmonkey's trades specifically
"""

import requests
from datetime import datetime, timezone

# From your screenshot
ELKMONKEY_ADDRESS = "0xead152b855effa6b5b5837f53b24c0756830c76a"
DATA_API = "https://data-api.polymarket.com"

print("\n" + "="*80)
print("ELKMONKEY TRADE DEBUG")
print("="*80 + "\n")

print(f"Address: {ELKMONKEY_ADDRESS}\n")

# Test 1: Get activity
print("Test 1: Fetching activity from Polymarket API...")
try:
    response = requests.get(
        f"{DATA_API}/activity",
        params={"user": ELKMONKEY_ADDRESS, "limit": 50},
        timeout=10
    )
    
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        activities = response.json()
        print(f"Total activities: {len(activities)}")
        
        # Filter for trades
        trades = [a for a in activities if a.get("type") == "TRADE"]
        buy_trades = [a for a in activities if a.get("type") == "TRADE" and a.get("side") == "BUY"]
        
        print(f"Total TRADE activities: {len(trades)}")
        print(f"BUY trades: {len(buy_trades)}")
        print(f"SELL trades: {len(trades) - len(buy_trades)}")
        
        if buy_trades:
            print(f"\n✓ FOUND {len(buy_trades)} BUY TRADES!\n")
            print("Most recent 5 BUY trades:")
            for i, trade in enumerate(buy_trades[:5], 1):
                title = trade.get("title", "Unknown")
                outcome = trade.get("outcome", "Unknown")
                side = trade.get("side", "?")
                timestamp = trade.get("timestamp", 0)
                trade_id = trade.get("id", "")
                
                trade_time = datetime.fromtimestamp(timestamp, timezone.utc)
                age_minutes = (datetime.now(timezone.utc).timestamp() - timestamp) / 60
                
                print(f"\n{i}. {title[:60]}")
                print(f"   Outcome: {outcome}")
                print(f"   Side: {side}")
                print(f"   Time: {trade_time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
                print(f"   Age: {age_minutes:.1f} minutes ago")
                print(f"   Trade ID: {trade_id[:20]}...")
        else:
            print(f"\n✗ NO BUY TRADES FOUND!")
            print("This is the problem - bot can't find any BUY trades for this address")
            
            if trades:
                print(f"\nBut there ARE {len(trades)} trades total:")
                for i, trade in enumerate(trades[:3], 1):
                    print(f"{i}. {trade.get('title', 'Unknown')[:50]} - {trade.get('side', '?')}")
    else:
        print(f"✗ API Error: {response.status_code}")
        print(f"Response: {response.text[:500]}")
        
except Exception as e:
    print(f"✗ Error: {e}")
    import traceback
    traceback.print_exc()

# Test 2: Check if address is correct
print("\n" + "="*80)
print("Test 2: Verifying address format...")
print("="*80 + "\n")

if len(ELKMONKEY_ADDRESS) == 42 and ELKMONKEY_ADDRESS.startswith("0x"):
    print("✓ Address format looks correct (42 chars, starts with 0x)")
else:
    print("✗ Address format looks WRONG!")
    print(f"  Length: {len(ELKMONKEY_ADDRESS)} (should be 42)")
    print(f"  Starts with 0x: {ELKMONKEY_ADDRESS.startswith('0x')}")

# Test 3: Compare with what bot sees
print("\n" + "="*80)
print("Test 3: Checking accounts.json...")
print("="*80 + "\n")

try:
    import json
    with open("accounts.json", 'r') as f:
        data = json.load(f)
        accounts = data.get("accounts", [])
    
    elkmonkey_found = False
    for acc in accounts:
        name = acc.get("name", "")
        address = acc.get("address", "")
        enabled = acc.get("enabled", True)
        
        if "elk" in name.lower() or address.lower() == ELKMONKEY_ADDRESS.lower():
            elkmonkey_found = True
            print(f"Found elkmonkey in accounts.json:")
            print(f"  Name: {name}")
            print(f"  Address: {address}")
            print(f"  Enabled: {enabled}")
            
            if address.lower() == ELKMONKEY_ADDRESS.lower():
                print(f"  ✓ Address MATCHES")
            else:
                print(f"  ✗ Address MISMATCH!")
                print(f"    Expected: {ELKMONKEY_ADDRESS}")
                print(f"    In file:  {address}")
    
    if not elkmonkey_found:
        print("✗ elkmonkey NOT FOUND in accounts.json!")
        print("\nAccounts in file:")
        for acc in accounts:
            print(f"  - {acc.get('name', 'Unknown')}: {acc.get('address', '')[:20]}...")
            
except Exception as e:
    print(f"Error reading accounts.json: {e}")

print("\n" + "="*80)
print("DIAGNOSIS")
print("="*80 + "\n")

print("If you saw 'FOUND X BUY TRADES' above:")
print("  → API is working")
print("  → Address is correct") 
print("  → Problem is in bot's get_latest_bet() logic")
print("  → Check seen_trades.json - trades might be marked as seen")
print()
print("If you saw 'NO BUY TRADES FOUND':")
print("  → Either wrong address")
print("  → Or trades are all SELLs")
print("  → Or Polymarket profile uses different address")
print()
print("If you saw API Error:")
print("  → Network/API issue")
print("  → Bot can't fetch data")
print()
print("="*80 + "\n")
