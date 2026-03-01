#!/usr/bin/env python3
"""
Test script to debug USDC balance fetching
"""

import os
import requests
from dotenv import load_dotenv

load_dotenv()

FUNDER_ADDRESS = os.getenv("FUNDER_ADDRESS")
PRIVATE_KEY = os.getenv("PRIVATE_KEY")
SIGNATURE_TYPE = int(os.getenv("SIGNATURE_TYPE", 1))

DATA_API = "https://data-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"
PROFILE_API = "https://gamma-api.polymarket.com"

print("\n" + "="*80)
print("POLYMARKET BALANCE CHECKER")
print("="*80 + "\n")

print(f"Testing balance fetch for: {FUNDER_ADDRESS[:10]}...{FUNDER_ADDRESS[-6:]}\n")

# Test 1: Authenticated CLOB Client
print("Test 1: Checking with authenticated CLOB client...")
try:
    from py_clob_client.client import ClobClient
    
    client = ClobClient(
        CLOB_API,
        key=PRIVATE_KEY,
        chain_id=137,
        signature_type=SIGNATURE_TYPE,
        funder=FUNDER_ADDRESS
    )
    creds = client.derive_api_key()
    client.set_api_creds(creds)
    
    # Try get_balance_allowance
    try:
        result = client.get_balance_allowance()
        print(f"  ✓ get_balance_allowance() returned: {result}")
        
        if isinstance(result, dict):
            for key in ["balance", "amount", "allowance"]:
                if key in result:
                    balance = float(result[key]) / 1_000_000
                    print(f"  → Balance: ${balance:.2f} USDC (from '{key}' field)")
    except AttributeError as e:
        print(f"  ✗ get_balance_allowance() not available: {e}")
    
    # Try get_balance
    try:
        result = client.get_balance()
        print(f"  ✓ get_balance() returned: {result}")
        
        if isinstance(result, (int, float)):
            balance = float(result) / 1_000_000
            print(f"  → Balance: ${balance:.2f} USDC")
        elif isinstance(result, dict) and "balance" in result:
            balance = float(result["balance"]) / 1_000_000
            print(f"  → Balance: ${balance:.2f} USDC")
    except AttributeError as e:
        print(f"  ✗ get_balance() not available: {e}")
        
except Exception as e:
    print(f"  ✗ Failed: {e}")

# Test 2: Gamma API
print("\nTest 2: Checking Gamma API...")
try:
    response = requests.get(
        f"{PROFILE_API}/balance",
        params={"address": FUNDER_ADDRESS},
        timeout=10
    )
    print(f"  Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"  Response: {data}")
        
        if isinstance(data, dict) and "balance" in data:
            balance = float(data["balance"])
            print(f"  → Balance: ${balance:.2f} USDC")
    else:
        print(f"  Error: {response.text[:200]}")
except Exception as e:
    print(f"  ✗ Failed: {e}")

# Test 3: CLOB API balances endpoint
print("\nTest 3: Checking CLOB API /balances endpoint...")
try:
    response = requests.get(
        f"{CLOB_API}/balances",
        params={"address": FUNDER_ADDRESS},
        timeout=10
    )
    print(f"  Status: {response.status_code}")
    
    if response.status_code == 200:
        data = response.json()
        print(f"  Response: {data}")
        
        if isinstance(data, list) and len(data) > 0:
            for token in data:
                if isinstance(token, dict):
                    bal = float(token.get("balance", 0))
                    if bal > 0:
                        balance = bal / 1_000_000
                        asset = token.get("asset", "Unknown")
                        print(f"  → {asset}: ${balance:.2f}")
        elif isinstance(data, dict) and "balance" in data:
            balance = float(data["balance"]) / 1_000_000
            print(f"  → Balance: ${balance:.2f} USDC")
    else:
        print(f"  Error: {response.text[:200]}")
except Exception as e:
    print(f"  ✗ Failed: {e}")

# Test 4: Direct blockchain check
print("\nTest 4: Checking blockchain directly (most reliable)...")
try:
    from web3 import Web3
    
    # Connect to Polygon RPC (using Ankr as it's more reliable for scripts)
    w3 = Web3(Web3.HTTPProvider('https://rpc.ankr.com/polygon'))
    
    if not w3.is_connected():
        print("  ✗ Failed to connect to Polygon RPC")
    else:
        print(f"  ✓ Connected to Polygon (block: {w3.eth.block_number})")
        
        # USDC contract on Polygon
        usdc_address = Web3.to_checksum_address('0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174')
        
        # ERC20 ABI for balanceOf
        erc20_abi = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function"
            }
        ]
        
        usdc_contract = w3.eth.contract(address=usdc_address, abi=erc20_abi)
        user_address = Web3.to_checksum_address(FUNDER_ADDRESS)
        
        raw_balance = usdc_contract.functions.balanceOf(user_address).call()
        balance = raw_balance / 1_000_000  # USDC has 6 decimals
        
        print(f"  Raw balance: {raw_balance}")
        print(f"  → Balance: ${balance:.2f} USDC")
        
except ImportError:
    print("  ✗ web3 not installed")
    print("  Install with: pip install web3")
except Exception as e:
    print(f"  ✗ Failed: {e}")

print("\n" + "="*80)
print("If all tests failed, check:")
print("  1. Your FUNDER_ADDRESS is correct in .env")
print("  2. You have USDC on Polygon network (not Ethereum mainnet)")
print("  3. Your internet connection is working")
print("  4. Consider installing web3: pip install web3")
print("="*80 + "\n")
