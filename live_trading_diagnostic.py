#!/usr/bin/env python3
"""
Live Trading Diagnostics - Check if bot can enable live mode
"""

import os
import sys
from dotenv import load_dotenv

print("\n" + "="*80)
print("LIVE TRADING DIAGNOSTICS")
print("="*80 + "\n")

load_dotenv()

# Step 1: Check critical environment variables
print("Step 1: Checking environment variables...")

FUNDER_ADDRESS = os.getenv("FUNDER_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
SIGNATURE_TYPE = os.getenv("SIGNATURE_TYPE")
DRY_RUN = os.getenv("DRY_RUN", "True")

issues = []

if not FUNDER_ADDRESS:
    print("  ✗ FUNDER_ADDRESS: MISSING")
    issues.append("FUNDER_ADDRESS is not set in .env")
else:
    print(f"  ✓ FUNDER_ADDRESS: {FUNDER_ADDRESS[:10]}...{FUNDER_ADDRESS[-6:]}")

if not PRIVATE_KEY:
    print("  ✗ PRIVATE_KEY: MISSING")
    issues.append("PRIVATE_KEY is not set in .env")
else:
    # Check if it looks like a valid private key
    if len(PRIVATE_KEY) < 32:
        print(f"  ⚠ PRIVATE_KEY: TOO SHORT ({len(PRIVATE_KEY)} chars)")
        issues.append("PRIVATE_KEY seems invalid (too short)")
    elif PRIVATE_KEY.startswith("your_"):
        print("  ✗ PRIVATE_KEY: PLACEHOLDER VALUE")
        issues.append("PRIVATE_KEY is still the placeholder value")
    else:
        print(f"  ✓ PRIVATE_KEY: Set ({len(PRIVATE_KEY)} chars)")

if not SIGNATURE_TYPE:
    print("  ⚠ SIGNATURE_TYPE: Using default (1)")
else:
    print(f"  ✓ SIGNATURE_TYPE: {SIGNATURE_TYPE}")

print(f"  • DRY_RUN: {DRY_RUN}")

# Step 2: Test CLOB Client Authentication
print("\nStep 2: Testing CLOB client authentication...")

if not PRIVATE_KEY or PRIVATE_KEY.startswith("your_"):
    print("  ✗ Skipping (PRIVATE_KEY not properly set)")
    issues.append("Cannot test authentication without valid PRIVATE_KEY")
else:
    try:
        from py_clob_client.client import ClobClient
        
        CLOB_API = "https://clob.polymarket.com"
        sig_type = int(SIGNATURE_TYPE) if SIGNATURE_TYPE else 1
        
        print(f"  Attempting to create CLOB client...")
        client = ClobClient(
            CLOB_API,
            key=PRIVATE_KEY,
            chain_id=137,
            signature_type=sig_type,
            funder=FUNDER_ADDRESS
        )
        
        print(f"  Deriving API credentials...")
        creds = client.derive_api_key()
        client.set_api_creds(creds)
        
        print(f"  ✓ CLOB client authenticated successfully!")
        print(f"    API Key: {creds.api_key[:20]}...")
        
    except ImportError as e:
        print(f"  ✗ py_clob_client not installed: {e}")
        issues.append("py_clob_client library is not installed")
    except Exception as e:
        print(f"  ✗ Authentication failed: {e}")
        issues.append(f"CLOB authentication error: {str(e)}")
        print(f"\n    This usually means:")
        print(f"      - PRIVATE_KEY is incorrect")
        print(f"      - SIGNATURE_TYPE is wrong")
        print(f"      - FUNDER_ADDRESS doesn't match the private key")

# Step 3: Check accounts.json
print("\nStep 3: Checking target accounts...")

try:
    import json
    if os.path.exists("accounts.json"):
        with open("accounts.json", 'r') as f:
            data = json.load(f)
            accounts = data.get("accounts", [])
            
        if not accounts:
            print("  ✗ No accounts configured")
            issues.append("accounts.json has no accounts")
        else:
            enabled = [a for a in accounts if a.get("enabled", True)]
            print(f"  ✓ Found {len(accounts)} accounts ({len(enabled)} enabled)")
            for acc in enabled:
                name = acc.get("name", "Unknown")
                addr = acc.get("address", "")[:10]
                print(f"    • {name} ({addr}...)")
    else:
        print("  ✗ accounts.json not found")
        issues.append("accounts.json file missing")
except Exception as e:
    print(f"  ✗ Error reading accounts.json: {e}")
    issues.append(f"Error reading accounts: {str(e)}")

# Step 4: Test a simple API call
print("\nStep 4: Testing Polymarket API access...")

try:
    import requests
    DATA_API = "https://data-api.polymarket.com"
    
    response = requests.get(
        f"{DATA_API}/positions",
        params={"user": FUNDER_ADDRESS, "sizeThreshold": 0},
        timeout=10
    )
    
    if response.status_code == 200:
        positions = response.json()
        print(f"  ✓ API access working ({len(positions)} positions)")
    else:
        print(f"  ⚠ API returned {response.status_code}")
        
except Exception as e:
    print(f"  ✗ API test failed: {e}")
    issues.append("Cannot connect to Polymarket API")

# Summary
print("\n" + "="*80)
print("DIAGNOSTIC SUMMARY")
print("="*80 + "\n")

if not issues:
    print("✅ ALL CHECKS PASSED!")
    print("\nYour bot is ready for live trading.")
    print("\nTo enable live trading:")
    print("  1. Edit .env and set: DRY_RUN=False")
    print("  2. Start bot: python continuous_bot.py")
    print("  3. Monitor closely for first few trades")
    print("\n⚠️  IMPORTANT: Start with small BET_AMOUNT (e.g., $1.00)")
    
else:
    print("❌ ISSUES FOUND:")
    for i, issue in enumerate(issues, 1):
        print(f"  {i}. {issue}")
    
    print("\n📋 HOW TO FIX:")
    
    if any("PRIVATE_KEY" in issue for issue in issues):
        print("\n  PRIVATE_KEY Issue:")
        print("  1. Get your private key from your wallet (MetaMask, etc.)")
        print("  2. Add to .env file: PRIVATE_KEY=0x...")
        print("  3. NEVER share this key with anyone!")
        print("  4. Make sure .env is in .gitignore")
    
    if any("accounts" in issue for issue in issues):
        print("\n  Accounts Issue:")
        print("  1. Create accounts.json if missing")
        print("  2. Add traders to track:")
        print("     {\"accounts\": [{\"address\": \"0x...\", \"name\": \"Trader\", \"enabled\": true}]}")
    
    if any("py_clob_client" in issue for issue in issues):
        print("\n  Library Issue:")
        print("  Run: pip install py-clob-client")
    
    if any("authentication" in issue.lower() for issue in issues):
        print("\n  Authentication Issue:")
        print("  1. Verify PRIVATE_KEY matches FUNDER_ADDRESS")
        print("  2. Check SIGNATURE_TYPE (usually 1 or 2)")
        print("  3. Make sure private key has correct format")

print("\n" + "="*80 + "\n")
