#!/usr/bin/env python3
"""
Test script with verbose output to debug betting_logger
"""

import os
import sys

print("\n" + "="*80)
print("BETTING LOGGER TEST - VERBOSE MODE")
print("="*80 + "\n")

# Step 1: Load environment
print("Step 1: Loading environment variables...")
try:
    from dotenv import load_dotenv
    load_dotenv()
    print("✓ dotenv loaded")
except Exception as e:
    print(f"✗ Failed to load dotenv: {e}")
    sys.exit(1)

# Step 2: Check FUNDER_ADDRESS
print("\nStep 2: Checking FUNDER_ADDRESS...")
FUNDER_ADDRESS = os.getenv("FUNDER_ADDRESS")
if FUNDER_ADDRESS:
    print(f"✓ FUNDER_ADDRESS found: {FUNDER_ADDRESS[:10]}...{FUNDER_ADDRESS[-6:]}")
else:
    print("✗ FUNDER_ADDRESS is missing!")
    print("   Add this to your .env file:")
    print("   FUNDER_ADDRESS=your_wallet_address")
    sys.exit(1)

# Step 3: Import dependencies
print("\nStep 3: Importing dependencies...")
try:
    import requests
    print("✓ requests imported")
except ImportError:
    print("✗ requests not installed. Run: pip install requests")
    sys.exit(1)

try:
    import sqlite3
    print("✓ sqlite3 available")
except ImportError:
    print("✗ sqlite3 not available (should be built-in)")
    sys.exit(1)

# Step 4: Test API connection
print("\nStep 4: Testing Polymarket API connection...")
DATA_API = "https://data-api.polymarket.com"

try:
    print(f"   Fetching positions for {FUNDER_ADDRESS[:10]}...")
    response = requests.get(
        f"{DATA_API}/positions",
        params={"user": FUNDER_ADDRESS, "sizeThreshold": 0},
        timeout=10
    )
    
    print(f"   Response status: {response.status_code}")
    
    if response.status_code == 200:
        positions = response.json()
        print(f"✓ API connection successful")
        print(f"   Found {len(positions)} open positions")
        
        if positions:
            print("\n   Your open positions:")
            for i, pos in enumerate(positions[:5], 1):
                title = pos.get('title', 'Unknown')[:50]
                outcome = pos.get('outcome', 'Unknown')
                print(f"   {i}. {title} - {outcome}")
            if len(positions) > 5:
                print(f"   ... and {len(positions) - 5} more")
    else:
        print(f"✗ API returned error {response.status_code}")
        print(f"   Response: {response.text[:500]}")
        sys.exit(1)
        
except requests.exceptions.Timeout:
    print("✗ API request timed out")
    print("   Check your internet connection")
    sys.exit(1)
except requests.exceptions.RequestException as e:
    print(f"✗ API request failed: {e}")
    sys.exit(1)

# Step 5: Test trade history
print("\nStep 5: Fetching trade history...")
try:
    response = requests.get(
        f"{DATA_API}/activity",
        params={"user": FUNDER_ADDRESS, "limit": 20},
        timeout=10
    )
    
    if response.status_code == 200:
        activities = response.json()
        trades = [a for a in activities if a.get('type') == 'TRADE']
        print(f"✓ Found {len(trades)} trades in recent activity")
        
        if trades:
            print("\n   Recent trades:")
            for i, trade in enumerate(trades[:3], 1):
                title = trade.get('title', 'Unknown')[:50]
                outcome = trade.get('outcome', 'Unknown')
                side = trade.get('side', 'Unknown')
                print(f"   {i}. {side} {outcome} on: {title}")
        else:
            print("   No trades found - you may not have traded yet")
    else:
        print(f"✗ Failed to fetch trade history: {response.status_code}")
        
except Exception as e:
    print(f"✗ Error fetching trades: {e}")

# Step 6: Test database creation
print("\nStep 6: Testing database creation...")
try:
    import sqlite3
    from datetime import datetime, timezone
    
    db_path = "test_betting_history.db"
    print(f"   Creating test database: {db_path}")
    
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS test_trades (
            id TEXT PRIMARY KEY,
            timestamp INTEGER
        )
    """)
    
    cursor.execute(
        "INSERT OR REPLACE INTO test_trades VALUES (?, ?)",
        ("test_1", int(datetime.now(timezone.utc).timestamp()))
    )
    
    conn.commit()
    
    cursor.execute("SELECT COUNT(*) FROM test_trades")
    count = cursor.fetchone()[0]
    
    conn.close()
    
    print(f"✓ Database created and tested successfully")
    print(f"   Test record count: {count}")
    
    # Clean up test database
    os.remove(db_path)
    print("   Test database cleaned up")
    
except Exception as e:
    print(f"✗ Database test failed: {e}")
    import traceback
    traceback.print_exc()

# Step 7: Try to run betting_logger
print("\nStep 7: Attempting to run betting_logger...")
try:
    print("   Importing betting_logger module...")
    from betting_logger import BettingLogger
    print("✓ betting_logger imported")
    
    print("\n   Creating BettingLogger instance...")
    logger = BettingLogger(db_path="test_run.db")
    print(f"✓ BettingLogger created (db: {logger.db_path})")
    
    print("\n   Importing 5 trades as test...")
    response = requests.get(
        f"{DATA_API}/activity",
        params={"user": FUNDER_ADDRESS, "limit": 5},
        timeout=10
    )
    
    if response.status_code == 200:
        activities = response.json()
        
        conn = sqlite3.connect("test_run.db")
        cursor = conn.cursor()
        
        imported = 0
        for activity in activities:
            if activity.get("type") == "TRADE":
                trade_id = activity.get('id', '')
                timestamp = activity.get("timestamp", 0)
                
                cursor.execute(
                    "SELECT id FROM trades WHERE id = ?",
                    (trade_id,)
                )
                
                if not cursor.fetchone():
                    from datetime import datetime, timezone
                    created_date = datetime.fromtimestamp(
                        timestamp, timezone.utc
                    ).strftime('%Y-%m-%d')
                    
                    cursor.execute("""
                        INSERT INTO trades 
                        (id, timestamp, market_title, condition_id, outcome_index, 
                         outcome, side, size, price, token_id, created_date)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        trade_id,
                        timestamp,
                        activity.get("title", "Unknown"),
                        activity.get("conditionId", ""),
                        activity.get("outcomeIndex"),
                        activity.get("outcome", "Unknown"),
                        activity.get("side", ""),
                        float(activity.get("size", 0)),
                        float(activity.get("price", 0)),
                        activity.get("asset", ""),
                        created_date
                    ))
                    imported += 1
        
        conn.commit()
        conn.close()
        
        print(f"✓ Successfully imported {imported} test trades")
        
        # Clean up
        os.remove("test_run.db")
        print("   Test database cleaned up")
        
    else:
        print(f"✗ Could not fetch trades for test")
        
except ImportError as e:
    print(f"✗ Failed to import betting_logger: {e}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"✗ Error during test: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80)
print("TEST COMPLETE")
print("="*80)
print("\nIf all steps passed with ✓, betting_logger should work.")
print("If you see ✗ errors, fix them and try again.")
print("\nTo run the actual logger:")
print("  python betting_logger.py")
print("="*80 + "\n")