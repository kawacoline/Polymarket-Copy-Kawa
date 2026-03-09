import json
from datetime import datetime, timezone

def migrate():
    try:
        # Load profitable wallets
        with open('profitable_wallets.json', 'r', encoding='utf-8') as f:
            profitable_data = json.load(f)
        
        wallets = profitable_data.get('wallets', [])
        
        # Transform data
        new_accounts = []
        for w in wallets:
            account = {
                "address": w.get('address'),
                "name": w.get('userName'),
                "rank": w.get('rank'),
                "score": w.get('score'),
                "winRate": w.get('winRate'),
                "pnl": w.get('pnl'),
                "tags": w.get('tags', []),
                "enabled": False,
                "bet_amount_override": None,
                "added_date": datetime.now(timezone.utc).isoformat()
            }
            new_accounts.append(account)
            
        # Write to accounts.json
        with open('accounts.json', 'w', encoding='utf-8') as f:
            json.dump({"accounts": new_accounts}, f, indent=4)
            
        print(f"Successfully migrated {len(new_accounts)} wallets to accounts.json")
        
    except Exception as e:
        print(f"Error during migration: {e}")

if __name__ == "__main__":
    migrate()
