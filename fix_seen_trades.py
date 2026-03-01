#!/usr/bin/env python3
"""
Fix script for corrupted seen_trades.json file
This removes any null values and ensures the file is properly formatted
"""

import json
import os

SEEN_TRADES_FILE = "seen_trades.json"

print("="*60)
print("SEEN TRADES FIX SCRIPT")
print("="*60)
print()

# Check if file exists
if not os.path.exists(SEEN_TRADES_FILE):
    print(f"✓ Creating new {SEEN_TRADES_FILE} file...")
    with open(SEEN_TRADES_FILE, 'w') as f:
        json.dump([], f)
    print("✓ File created successfully!")
else:
    print(f"Found existing {SEEN_TRADES_FILE} file")
    
    # Read current content
    try:
        with open(SEEN_TRADES_FILE, 'r') as f:
            content = f.read()
            print(f"Current content: {content}")
            
        # Parse JSON
        with open(SEEN_TRADES_FILE, 'r') as f:
            data = json.load(f)
            
        # Filter out None/null values
        if isinstance(data, list):
            original_count = len(data)
            cleaned_data = [item for item in data if item is not None]
            removed_count = original_count - len(cleaned_data)
            
            print(f"✓ Found {original_count} entries")
            if removed_count > 0:
                print(f"✓ Removing {removed_count} null entries")
            
            # Write back cleaned data
            with open(SEEN_TRADES_FILE, 'w') as f:
                json.dump(cleaned_data, f)
                
            print(f"✓ File cleaned! Now has {len(cleaned_data)} valid entries")
        else:
            print("⚠ File format unexpected, creating fresh file")
            with open(SEEN_TRADES_FILE, 'w') as f:
                json.dump([], f)
            print("✓ Fresh file created")
            
    except json.JSONDecodeError as e:
        print(f"✗ JSON decode error: {e}")
        print("Creating fresh file...")
        with open(SEEN_TRADES_FILE, 'w') as f:
            json.dump([], f)
        print("✓ Fresh file created")
    except Exception as e:
        print(f"✗ Error: {e}")
        print("Creating fresh file...")
        with open(SEEN_TRADES_FILE, 'w') as f:
            json.dump([], f)
        print("✓ Fresh file created")

print()
print("="*60)
print("DONE!")
print("="*60)
print()
print("You can now restart your bot:")
print("  python continuous_bot.py")
print()
