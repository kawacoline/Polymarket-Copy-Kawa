import sqlite3
from pathlib import Path
import os
import shutil

DB_PATH = Path("betting_history.db")
SIM_DB_PATH = Path("simulated_history.db")

def migrate():
    if not DB_PATH.exists():
        print(f"Source database {DB_PATH} does not exist. Nothing to migrate.")
        return

    # Backup the original database just in case
    backup_path = Path("betting_history_backup.db")
    shutil.copy2(DB_PATH, backup_path)
    print(f"Created backup of betting_history.db at {backup_path}")

    # Connect to both databases
    conn_live = sqlite3.connect(DB_PATH)
    conn_live.row_factory = sqlite3.Row
    cursor_live = conn_live.cursor()

    # Create the simulated database if it doesn't exist
    conn_sim = sqlite3.connect(SIM_DB_PATH)
    cursor_sim = conn_sim.cursor()

    # Create the exact same table structure in simulated_history.db
    cursor_sim.execute("""
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
            created_date TEXT,
            copied_from TEXT
        )
    """)
    conn_sim.commit()

    # Check if is_dry_run column exists in live DB
    try:
        cursor_live.execute("SELECT * FROM trades WHERE is_dry_run = 1")
        simulated_trades = cursor_live.fetchall()
    except sqlite3.OperationalError:
        print("Column 'is_dry_run' not found in betting_history.db. No simulated trades to migrate.")
        return

    print(f"Found {len(simulated_trades)} simulated trades to migrate.")

    if len(simulated_trades) == 0:
        return

    # Insert into simulated_history.db
    inserted_count = 0
    for row in simulated_trades:
        try:
            # We don't need to insert 'is_dry_run' anymore, but let's grab the other columns safely
            cursor_sim.execute("""
                INSERT OR IGNORE INTO trades (id, timestamp, market_title, condition_id, outcome_index, outcome, side, size, price, token_id, created_date, copied_from)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                row['id'], row['timestamp'], row['market_title'], row['condition_id'], 
                row['outcome_index'], row['outcome'], row['side'], row['size'], 
                row['price'], row['token_id'], row['created_date'], dict(row).get('copied_from') # use dict() to safely get copied_from
            ))
            inserted_count += cursor_sim.rowcount
        except Exception as e:
            print(f"Error inserting row {row['id']}: {e}")
            
    conn_sim.commit()
    print(f"Successfully migrated {inserted_count} simulated trades into {SIM_DB_PATH}.")

    # Delete the migrated rows from betting_history.db
    cursor_live.execute("DELETE FROM trades WHERE is_dry_run = 1")
    deleted_count = cursor_live.rowcount
    conn_live.commit()
    print(f"Deleted {deleted_count} simulated trades from {DB_PATH}.")

    # Optional: vacuum the live DB to reclaim space
    cursor_live.execute("VACUUM")
    
    conn_live.close()
    conn_sim.close()
    print("Migration complete.")

if __name__ == "__main__":
    migrate()
