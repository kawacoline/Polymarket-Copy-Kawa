import re
import json
from datetime import datetime, timezone

try:
    with open('profitable_wallets.json', 'r', encoding='utf-8') as f:
        content = f.read()

    chunks = content.split('"address"')
    new_accounts = []
    seen = set()
    
    for chunk in chunks[1:]:
        # Extracted address
        addr_match = re.search(r'^\s*:\s*"(0x[a-fA-F0-9]+)"', chunk)
        if not addr_match: continue
        addr = addr_match.group(1).lower()
        
        if addr in seen: continue
        seen.add(addr)
        
        # Name
        name = 'Unknown'
        name_match = re.search(r'"userName"\s*:\s*"([^"]+)"', chunk)
        if name_match: name = name_match.group(1)
            
        # rank
        rank = 0
        rank_match = re.search(r'"rank"\s*:\s*(\d+)', chunk)
        if rank_match: rank = int(rank_match.group(1))
        
        # score
        score = 0.0
        score_match = re.search(r'"score"\s*:\s*([\d\.]+)', chunk)
        if score_match: score = float(score_match.group(1))
        
        # winRate
        winRate = 0.0
        win_match = re.search(r'"winRate"\s*:\s*([\d\.]+)', chunk)
        if win_match: winRate = float(win_match.group(1))
        
        # pnl
        pnl = 0.0
        pnl_match = re.search(r'"pnl"\s*:\s*([\-\d\.]+)', chunk)
        if pnl_match: pnl = float(pnl_match.group(1))
        
        # tags
        tags = []
        tags_match = re.search(r'"tags"\s*:\s*\[([\s\S]*?)\]', chunk)
        if tags_match:
            tags_str = tags_match.group(1)
            tags = [t.strip(' "\n\r') for t in tags_str.split(',') if t.strip()]
            
        new_accounts.append({
            'address': addr,
            'name': name,
            'rank': rank,
            'score': score,
            'winRate': winRate,
            'pnl': pnl,
            'tags': tags,
            'enabled': False,
            'bet_amount_override': None,
            'added_date': datetime.now(timezone.utc).isoformat()
        })
            
    with open('accounts.json', 'w', encoding='utf-8') as f:
        json.dump({'accounts': new_accounts}, f, indent=4)
        
    print(f'Imported {len(new_accounts)} accounts successfully.')
except Exception as e:
    print(f'Error: {e}')
