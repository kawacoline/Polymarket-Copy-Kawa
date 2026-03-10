import os
import json
import sqlite3
from datetime import datetime, timezone
from typing import Dict, List, Optional
import requests
from dotenv import load_dotenv
from logging_utils import setup_logger

load_dotenv()
logger = setup_logger("BettingLogger")

FUNDER_ADDRESS = os.getenv("FUNDER_ADDRESS")
DATA_API = "https://data-api.polymarket.com"
DB_PATH = os.getenv("DB_PATH", "betting_history.db")


class BettingLogger:
    def __init__(self, db_path: str = DB_PATH):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialize SQLite database with required tables"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Trades table - records every bet placed
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                timestamp INTEGER,
                market_title TEXT,
                condition_id TEXT,
                outcome_index INTEGER,
                outcome TEXT,
                side TEXT,
                size REAL,
                price REAL,
                token_id TEXT,
                status TEXT DEFAULT 'OPEN',
                closed_timestamp INTEGER,
                pnl REAL,
                created_date TEXT,
                closed_by TEXT,
                hold_duration_hours REAL
            )
        """)
        
        # Add new columns if they don't exist (for existing databases)
        try:
            cursor.execute("ALTER TABLE trades ADD COLUMN closed_by TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        
        try:
            cursor.execute("ALTER TABLE trades ADD COLUMN hold_duration_hours REAL")
        except sqlite3.OperationalError:
            pass  # Column already exists
            
        try:
            cursor.execute("ALTER TABLE trades ADD COLUMN is_dry_run INTEGER DEFAULT 1")
        except sqlite3.OperationalError:
            pass
            
        try:
            cursor.execute("ALTER TABLE trades ADD COLUMN copied_from TEXT")
        except sqlite3.OperationalError:
            pass
        
        # Daily stats table - aggregated daily performance
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,
                total_bets INTEGER,
                total_wagered REAL,
                open_positions INTEGER,
                closed_positions INTEGER,
                wins INTEGER,
                losses INTEGER,
                total_pnl REAL,
                win_rate REAL
            )
        """)
        
        # Market resolutions table - track when markets resolve
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS market_resolutions (
                condition_id TEXT,
                resolved_outcome_index INTEGER,
                resolved_timestamp INTEGER,
                PRIMARY KEY (condition_id)
            )
        """)
        
        conn.commit()
        conn.close()
    
    def fetch_trade_history(self, limit: int = 100) -> List[Dict]:
        """Fetch trade history from Polymarket API"""
        response = requests.get(
            f"{DATA_API}/activity",
            params={"user": FUNDER_ADDRESS, "limit": limit}
        )
        response.raise_for_status()
        return response.json()
    
    def fetch_current_positions(self) -> List[Dict]:
        """Fetch current open positions"""
        response = requests.get(
            f"{DATA_API}/positions",
            params={"user": FUNDER_ADDRESS, "sizeThreshold": 0}
        )
        response.raise_for_status()
        return response.json()
    
    def fetch_market_info(self, condition_id: str) -> Optional[Dict]:
        """Fetch market information to check resolution status"""
        try:
            response = requests.get(f"{DATA_API}/markets/{condition_id}")
            response.raise_for_status()
            return response.json()
        except:
            return None
    
    def import_historical_trades(self):
        """Import trade history into database"""
        logger.info("Importing historical trades...")
        trades = self.fetch_trade_history(limit=1000)
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        imported = 0
        for trade in trades:
            if trade.get("type") != "TRADE":
                continue
            
            trade_id = f"{trade.get('id', '')}"
            timestamp = trade.get("timestamp", 0)
            
            # Check if trade already exists
            cursor.execute("SELECT id FROM trades WHERE id = ?", (trade_id,))
            if cursor.fetchone():
                continue
            
            created_date = datetime.fromtimestamp(timestamp, timezone.utc).strftime('%Y-%m-%d')
            
            cursor.execute("""
                INSERT INTO trades 
                (id, timestamp, market_title, condition_id, outcome_index, outcome, 
                 side, size, price, token_id, created_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                trade_id,
                timestamp,
                trade.get("title", "Unknown"),
                trade.get("conditionId", ""),
                trade.get("outcomeIndex"),
                trade.get("outcome", "Unknown"),
                trade.get("side", ""),
                float(trade.get("size", 0)),
                float(trade.get("price", 0)),
                trade.get("asset", ""),
                created_date
            ))
            imported += 1
        
        conn.commit()
        conn.close()
        
        logger.info(f"Imported {imported} new trades")
        return imported
    
    def update_position_outcomes(self):
        """
        Check and update outcomes for closed positions
        
        This method now properly distinguishes between:
        1. Manual sells (user closed position)
        2. Market resolutions (market settled)
        """
        logger.info("Checking for closed positions and resolved markets...")
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Step 1: Get all SELL trades from activity and mark positions as closed by sell
        logger.info("  Checking for manual sells...")
        try:
            response = requests.get(
                f"{DATA_API}/activity",
                params={"user": FUNDER_ADDRESS, "limit": 100},
                timeout=10
            )
            response.raise_for_status()
            activities = response.json()
            
            sells_found = 0
            for activity in activities:
                if activity.get("type") == "TRADE" and activity.get("side") == "SELL":
                    trade_id = activity.get("id")
                    timestamp = activity.get("timestamp")
                    condition_id = activity.get("conditionId")
                    outcome_index = activity.get("outcomeIndex")
                    size = float(activity.get("size", 0))
                    price = float(activity.get("price", 0))
                    
                    # Find matching BUY trade(s) to close
                    cursor.execute("""
                        SELECT id, timestamp, size, price
                        FROM trades 
                        WHERE condition_id = ? 
                            AND outcome_index = ? 
                            AND status = 'OPEN'
                            AND side = 'BUY'
                        ORDER BY timestamp ASC
                    """, (condition_id, outcome_index))
                    
                    open_buy = cursor.fetchone()
                    if open_buy:
                        buy_id, buy_timestamp, buy_size, buy_price = open_buy
                        
                        # Calculate hold duration
                        duration_seconds = timestamp - buy_timestamp
                        duration_hours = duration_seconds / 3600
                        
                        # Calculate P&L: size * (sell_price - buy_price)
                        pnl = size * (price - buy_price)
                        
                        # Mark as closed by manual sell
                        cursor.execute("""
                            UPDATE trades 
                            SET status = 'CLOSED',
                                closed_timestamp = ?,
                                closed_by = 'MANUAL_SELL',
                                pnl = ?,
                                hold_duration_hours = ?
                            WHERE id = ?
                        """, (timestamp, pnl, duration_hours, buy_id))
                        
                        sells_found += 1
                        logger.info(f"    ✓ Marked position as sold: {activity.get('title', 'Unknown')[:40]} | P&L: ${pnl:.2f}")
            
            logger.info(f"  Found {sells_found} manual sells")
            
        except Exception as e:
            logger.info(f"  Error checking for sells: {e}")
        
        # Step 2: Check for market resolutions
        logger.info("  Checking for resolved markets...")
        
        # Get all remaining open trades
        cursor.execute("""
            SELECT DISTINCT condition_id, outcome_index 
            FROM trades 
            WHERE status = 'OPEN'
        """)
        open_positions = cursor.fetchall()
        
        # Get current positions from API
        current_positions = self.fetch_current_positions()
        current_keys = set()
        for pos in current_positions:
            key = f"{pos.get('conditionId')}_{pos.get('outcomeIndex')}"
            current_keys.add(key)
        
        resolved = 0
        for condition_id, outcome_index in open_positions:
            position_key = f"{condition_id}_{outcome_index}"
            
            # If position no longer exists in current positions
            if position_key not in current_keys:
                # Fetch market info to check if it's actually resolved
                market_info = self.fetch_market_info(condition_id)
                
                if market_info:
                    # Check if market is actually resolved
                    # A market is resolved when enableOrderBook is False or outcomePrices show a winner
                    enable_order_book = market_info.get("enableOrderBook", True)
                    outcome_prices = market_info.get("outcomePrices", [])
                    
                    # A resolved market has one outcome at 1.0 and others at 0.0
                    is_resolved = False
                    if len(outcome_prices) > 0:
                        # Check if any outcome is exactly 1.0 (winner)
                        if any(float(p) == 1.0 for p in outcome_prices):
                            is_resolved = True
                    
                    # Also consider it resolved if order book is disabled
                    if not enable_order_book:
                        is_resolved = True
                    
                    if is_resolved:
                        # Get the trades for this position
                        cursor.execute("""
                            SELECT id, timestamp, size, price
                            FROM trades 
                            WHERE condition_id = ? 
                                AND outcome_index = ? 
                                AND status = 'OPEN'
                        """, (condition_id, outcome_index))
                        
                        for trade_id, buy_timestamp, size, buy_price in cursor.fetchall():
                            # Get final price for this outcome
                            final_price = 0.0
                            if len(outcome_prices) > outcome_index:
                                final_price = float(outcome_prices[outcome_index])
                            
                            # Calculate P&L
                            pnl = size * (final_price - buy_price)
                            
                            # Calculate hold duration
                            now_timestamp = int(datetime.now(timezone.utc).timestamp())
                            duration_seconds = now_timestamp - buy_timestamp
                            duration_hours = duration_seconds / 3600
                            
                            # Mark as closed by market resolution
                            cursor.execute("""
                                UPDATE trades 
                                SET status = 'CLOSED',
                                    closed_timestamp = ?,
                                    closed_by = 'MARKET_RESOLVED',
                                    pnl = ?,
                                    hold_duration_hours = ?
                                WHERE id = ?
                            """, (now_timestamp, pnl, duration_hours, trade_id))
                            
                            result = "WIN" if pnl > 0 else "LOSS" if pnl < 0 else "BREAK EVEN"
                            logger.info(f"    ✓ Market resolved: {market_info.get('title', 'Unknown')[:40]} | {result} | P&L: ${pnl:.2f}")
                            
                            resolved += 1
                    else:
                        # Position disappeared but market not resolved - might be sold via another method
                        # We'll leave it as OPEN for now and let it be caught in next sell check
                        pass
        
        conn.commit()
        conn.close()
        
        logger.info(f"  Resolved {resolved} market outcomes")
        return sells_found + resolved
    
    def calculate_pnl(self):
        """Calculate P&L for closed positions"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Get closed trades without PnL calculated
        cursor.execute("""
            SELECT id, size, price, condition_id, outcome_index
            FROM trades 
            WHERE status = 'CLOSED' AND pnl IS NULL
        """)
        
        for trade_id, size, entry_price, condition_id, outcome_index in cursor.fetchall():
            # Fetch market to see final outcome
            market_info = self.fetch_market_info(condition_id)
            
            if market_info:
                outcome_prices = market_info.get("outcomePrices", [])
                if len(outcome_prices) > outcome_index:
                    final_price = float(outcome_prices[outcome_index])
                    
                    # PnL = size * (final_price - entry_price)
                    pnl = size * (final_price - entry_price)
                    
                    cursor.execute("""
                        UPDATE trades 
                        SET pnl = ?
                        WHERE id = ?
                    """, (pnl, trade_id))
        
        conn.commit()
        conn.close()
    
    def generate_daily_stats(self, date: str = None):
        """Generate daily statistics"""
        if date is None:
            date = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        # Count trades for the day
        cursor.execute("""
            SELECT COUNT(*), SUM(size) 
            FROM trades 
            WHERE created_date = ?
        """, (date,))
        total_bets, total_wagered = cursor.fetchone()
        total_bets = total_bets or 0
        total_wagered = total_wagered or 0.0
        
        # Count positions by status
        cursor.execute("""
            SELECT status, COUNT(*), SUM(pnl)
            FROM trades 
            WHERE created_date <= ?
            GROUP BY status
        """, (date,))
        
        stats = {"OPEN": 0, "CLOSED": 0, "pnl": 0.0}
        for status, count, pnl in cursor.fetchall():
            stats[status] = count
            if pnl:
                stats["pnl"] += pnl
        
        # Calculate wins and losses
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses
            FROM trades 
            WHERE status = 'CLOSED' AND created_date <= ?
        """, (date,))
        wins, losses = cursor.fetchone()
        wins = wins or 0
        losses = losses or 0
        
        win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0.0
        
        # Insert or update daily stats
        cursor.execute("""
            INSERT OR REPLACE INTO daily_stats 
            (date, total_bets, total_wagered, open_positions, closed_positions, 
             wins, losses, total_pnl, win_rate)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            date, total_bets, total_wagered, stats["OPEN"], stats["CLOSED"],
            wins, losses, stats["pnl"], win_rate
        ))
        
        conn.commit()
        conn.close()
        
        return {
            "date": date,
            "total_bets": total_bets,
            "total_wagered": total_wagered,
            "open_positions": stats["OPEN"],
            "closed_positions": stats["CLOSED"],
            "wins": wins,
            "losses": losses,
            "total_pnl": stats["pnl"],
            "win_rate": win_rate
        }
    
    def get_trade_details(self, limit: int = 50) -> List[Dict]:
        """Get detailed trade information"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT 
                id, timestamp, market_title, outcome, side, size, price,
                status, closed_timestamp, pnl, created_date
            FROM trades 
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,))
        
        trades = []
        for row in cursor.fetchall():
            trade_data = {
                "id": row[0],
                "timestamp": datetime.fromtimestamp(row[1], timezone.utc).strftime('%Y-%m-%d %H:%M:%S'),
                "market_title": row[2],
                "outcome": row[3],
                "side": row[4],
                "size": row[5],
                "price": row[6],
                "status": row[7],
                "closed_timestamp": datetime.fromtimestamp(row[8], timezone.utc).strftime('%Y-%m-%d %H:%M:%S') if row[8] else None,
                "pnl": row[9],
                "created_date": row[10]
            }
            
            # Calculate hold duration
            if row[8]:
                duration_seconds = row[8] - row[1]
                duration_hours = duration_seconds / 3600
                trade_data["hold_duration_hours"] = round(duration_hours, 2)
            
            trades.append(trade_data)
        
        conn.close()
        return trades
    
    def print_summary_report(self):
        """Print a summary report of betting activity"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        
        logger.info("\n" + "=" * 80)
        logger.info("BETTING ACTIVITY SUMMARY")
        logger.info("=" * 80)
        
        # Overall stats
        cursor.execute("""
            SELECT 
                COUNT(*) as total_trades,
                SUM(size) as total_wagered,
                SUM(CASE WHEN status = 'OPEN' THEN 1 ELSE 0 END) as open_count,
                SUM(CASE WHEN status = 'CLOSED' THEN 1 ELSE 0 END) as closed_count
            FROM trades
        """)
        total_trades, total_wagered, open_count, closed_count = cursor.fetchone()
        
        cursor.execute("""
            SELECT 
                SUM(CASE WHEN pnl > 0 THEN 1 ELSE 0 END) as wins,
                SUM(CASE WHEN pnl < 0 THEN 1 ELSE 0 END) as losses,
                SUM(pnl) as total_pnl
            FROM trades 
            WHERE status = 'CLOSED'
        """)
        wins, losses, total_pnl = cursor.fetchone()
        wins = wins or 0
        losses = losses or 0
        total_pnl = total_pnl or 0.0
        
        logger.info(f"\nOverall Performance:")
        logger.info(f"  Total Trades: {total_trades or 0}")
        logger.info(f"  Total Wagered: ${total_wagered or 0:.2f}")
        logger.info(f"  Open Positions: {open_count or 0}")
        logger.info(f"  Closed Positions: {closed_count or 0}")
        
        if closed_count and closed_count > 0:
            win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0
            logger.info(f"\n  Wins: {wins}")
            logger.info(f"  Losses: {losses}")
            logger.info(f"  Win Rate: {win_rate:.1f}%")
            logger.info(f"  Total P&L: ${total_pnl:.2f}")
            
            roi = (total_pnl / total_wagered * 100) if total_wagered > 0 else 0
            logger.info(f"  ROI: {roi:.1f}%")
        
        # Recent activity
        logger.info(f"\n{'-' * 80}")
        logger.info("Recent Trades (Last 10):")
        logger.info(f"{'-' * 80}")
        
        cursor.execute("""
            SELECT 
                created_date, market_title, outcome, size, price, status, pnl
            FROM trades 
            ORDER BY timestamp DESC
            LIMIT 10
        """)
        
        for row in cursor.fetchall():
            date, title, outcome, size, price, status, pnl = row
            pnl_str = f"${pnl:+.2f}" if pnl else "---"
            logger.info(f"  [{date}] {title[:40]}")
            logger.info(f"             {outcome} | ${size:.2f} @ {price*100:.1f}¢ | {status} | P&L: {pnl_str}")
        
        conn.close()
        logger.info("=" * 80 + "\n")
    
    def daily_update(self):
        """Run the full daily update process"""
        logger.info(f"\n{'='*80}")
        logger.info(f"Daily Betting Logger - {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
        logger.info(f"{'='*80}\n")
        
        # Import new trades
        self.import_historical_trades()
        
        # Update position outcomes
        self.update_position_outcomes()
        
        # Calculate P&L
        self.calculate_pnl()
        
        # Generate today's stats
        today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
        stats = self.generate_daily_stats(today)
        
        logger.info(f"\nToday's Stats ({today}):")
        logger.info(f"  New Bets: {stats['total_bets']}")
        logger.info(f"  Amount Wagered: ${stats['total_wagered']:.2f}")
        logger.info(f"  Open Positions: {stats['open_positions']}")
        logger.info(f"  Closed Positions: {stats['closed_positions']}")
        logger.info(f"  Wins: {stats['wins']} | Losses: {stats['losses']}")
        logger.info(f"  Win Rate: {stats['win_rate']:.1f}%")
        logger.info(f"  Total P&L: ${stats['total_pnl']:.2f}")
        
        # Print summary report
        self.print_summary_report()


def main():
    if not FUNDER_ADDRESS:
        logger.info("Error: FUNDER_ADDRESS not found in .env file")
        return
    
    logger = BettingLogger()
    logger.daily_update()


if __name__ == "__main__":
    main()