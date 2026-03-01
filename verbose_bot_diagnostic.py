#!/usr/bin/env python3
"""
Verbose Diagnostic Version of Continuous Bot
Prints debug messages at every step to find where it hangs
"""

import os
import time
import json
import requests
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

FUNDER_ADDRESS = os.getenv("FUNDER_ADDRESS")
DATA_API = "https://data-api.polymarket.com"
ACCOUNTS_FILE = "accounts.json"
SEEN_TRADES_FILE = "seen_trades.json"

print("\n" + "="*80)
print("VERBOSE DIAGNOSTIC MODE - Bot with Debug Output")
print("="*80 + "\n")

# Load accounts
print("[1/5] Loading accounts...")
try:
    with open(ACCOUNTS_FILE, 'r') as f:
        data = json.load(f)
        accounts = data.get("accounts", [])
    enabled_accounts = [acc for acc in accounts if acc.get("enabled", True)]
    print(f"✓ Loaded {len(accounts)} accounts ({len(enabled_accounts)} enabled)")
except Exception as e:
    print(f"✗ Error loading accounts: {e}")
    exit(1)

# Load seen trades
print("[2/5] Loading seen trades...")
try:
    with open(SEEN_TRADES_FILE, 'r') as f:
        seen_trades = set(json.load(f))
    print(f"✓ Loaded {len(seen_trades)} seen trades")
except:
    seen_trades = set()
    print("✓ No seen trades file (will create new)")

# Test API connectivity
print("[3/5] Testing API connectivity...")
try:
    response = requests.get(
        f"{DATA_API}/positions",
        params={"user": FUNDER_ADDRESS, "sizeThreshold": 0},
        timeout=5
    )
    if response.status_code == 200:
        print(f"✓ API responding (found {len(response.json())} positions)")
    else:
        print(f"⚠ API returned status {response.status_code}")
except Exception as e:
    print(f"✗ API test failed: {e}")
    print("  This might cause hangs later!")

print("[4/5] Testing account data fetch...")
for i, account in enumerate(enabled_accounts, 1):
    address = account.get("address")
    name = account.get("name", address[:10])
    
    print(f"\n  [{i}/{len(enabled_accounts)}] Fetching data for {name}...")
    
    try:
        print(f"      → Calling /activity API...")
        response = requests.get(
            f"{DATA_API}/activity",
            params={"user": address, "limit": 50},
            timeout=10
        )
        
        print(f"      → Status: {response.status_code}")
        
        if response.status_code == 200:
            activities = response.json()
            buy_trades = [a for a in activities if a.get("type") == "TRADE" and a.get("side") == "BUY"]
            print(f"      → Found {len(activities)} activities ({len(buy_trades)} BUY trades)")
            
            # Check for unseen trades
            unseen = [t for t in buy_trades if t.get("id") not in seen_trades]
            print(f"      → {len(unseen)} unseen BUY trades")
            
            if unseen:
                latest = unseen[0]
                print(f"      → Latest unseen: {latest.get('title', 'Unknown')[:40]}")
        else:
            print(f"      ✗ API error: {response.status_code}")
            
    except requests.Timeout:
        print(f"      ✗ TIMEOUT after 10 seconds!")
        print(f"      This is likely causing the hang!")
    except Exception as e:
        print(f"      ✗ Error: {e}")

print("\n[5/5] Running one check cycle (verbose)...\n")

def check_account_verbose(account):
    """Check one account with verbose output"""
    address = account.get("address")
    name = account.get("name", address[:10])
    
    print(f"=" * 60)
    print(f"Checking: {name}")
    print(f"=" * 60)
    
    print(f"  [1] Starting API call to /activity...")
    start_time = time.time()
    
    try:
        response = requests.get(
            f"{DATA_API}/activity",
            params={"user": address, "limit": 50},
            timeout=10
        )
        
        elapsed = time.time() - start_time
        print(f"  [2] API responded in {elapsed:.2f}s (status: {response.status_code})")
        
        if response.status_code != 200:
            print(f"  [3] Error response, skipping")
            return
        
        print(f"  [3] Parsing JSON...")
        activities = response.json()
        
        print(f"  [4] Found {len(activities)} activities")
        
        print(f"  [5] Filtering for BUY trades...")
        buy_trades = [a for a in activities if a.get("type") == "TRADE" and a.get("side") == "BUY"]
        
        print(f"  [6] Found {len(buy_trades)} BUY trades")
        
        if not buy_trades:
            print(f"  [7] No BUY trades, done")
            return
        
        print(f"  [7] Checking for unseen trades...")
        for trade in buy_trades:
            trade_id = trade.get("id")
            if trade_id not in seen_trades:
                print(f"  [8] Found unseen trade: {trade.get('title', 'Unknown')[:40]}")
                print(f"      Would copy this in live mode!")
                return
        
        print(f"  [8] All trades already seen")
        
    except requests.Timeout:
        elapsed = time.time() - start_time
        print(f"  [2] TIMEOUT after {elapsed:.2f}s!")
        print(f"      This is the problem - API is not responding")
    except Exception as e:
        elapsed = time.time() - start_time
        print(f"  [2] ERROR after {elapsed:.2f}s: {e}")

# Run one check for each account
for i, account in enumerate(enabled_accounts, 1):
    print(f"\n[Account {i}/{len(enabled_accounts)}]")
    check_account_verbose(account)
    print()

print("="*80)
print("DIAGNOSTIC COMPLETE")
print("="*80)
print("\nWhat to look for:")
print("  - If you see TIMEOUT messages → API is slow/unresponsive")
print("  - If it hangs before 'DIAGNOSTIC COMPLETE' → Note where it stopped")
print("  - If all checks pass quickly → Bot should work fine")
print("\nIf API is timing out:")
print("  - Polymarket API might be down or rate limiting")
print("  - Try again in a few minutes")
print("  - Check your internet connection")
print("="*80 + "\n")
