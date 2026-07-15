import sqlite3
import os
from pathlib import Path

DB_DIR = Path(__file__).parent.parent / "data"
DB_FILE = DB_DIR / "auth.db"

def seed_players(conn):
    """Seed the players table from worldcup_players.json if empty."""
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM players")
    count = cursor.fetchone()[0]
    if count > 0:
        return
    
    import json
    json_path = Path(__file__).parent.parent.parent / "data" / "worldcup_players.json"
    if not json_path.exists():
        print(f"Warning: worldcup_players.json not found at {json_path}")
        return
        
    with open(json_path, 'r', encoding='utf-8') as f:
        players_data = json.load(f)
        
    for p in players_data:
        premium = p.get("premium_stats", {})
        cursor.execute(
            """
            INSERT OR IGNORE INTO players 
            (id, name, position, team, price, is_available, points, xg_per_game, injury_risk, scout_note, flag, number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                p["id"],
                p["name"],
                p["position"],
                p["team"],
                p["price"],
                1 if p["isAvailable"] else 0,
                p["points"],
                premium.get("xg_per_game", 0.0),
                premium.get("injury_risk", "Low"),
                premium.get("scout_note", ""),
                p.get("flag"),
                p.get("number")
            )
        )
    conn.commit()
    print("Database: Seeded players from JSON successfully.")

def init_db():
    """Initialize the SQLite database and create users, players, and squads tables."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    
    # 1. Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        security_question TEXT NOT NULL,
        security_answer_hash TEXT NOT NULL,
        budget REAL DEFAULT 100.0,
        cctp_used INTEGER DEFAULT 0
    )
    """)
    
    # Try adding budget columns if the users table already existed without them
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN budget REAL DEFAULT 100.0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN cctp_used INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN formation TEXT DEFAULT '4-3-3'")
    except sqlite3.OperationalError:
        pass
        
    # 2. Create players table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS players (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        position TEXT NOT NULL,
        team TEXT NOT NULL,
        price REAL NOT NULL,
        is_available INTEGER NOT NULL,
        points INTEGER NOT NULL,
        xg_per_game REAL NOT NULL,
        injury_risk TEXT NOT NULL,
        scout_note TEXT NOT NULL,
        flag TEXT,
        number INTEGER
    )
    """)

    # 3. Create squad_slots table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS squad_slots (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        position TEXT NOT NULL,
        slot_index INTEGER NOT NULL,
        player_id TEXT,
        is_bench INTEGER DEFAULT 0,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (player_id) REFERENCES players(id) ON DELETE SET NULL,
        UNIQUE(user_id, position, slot_index, is_bench)
    )
    """)

    # 4. Create cctp_transactions table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS cctp_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        wallet_address TEXT NOT NULL,
        amount REAL NOT NULL,
        source_chain TEXT NOT NULL,
        tx_hash TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
    )
    """)

    # 5. Create transfers table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS transfers (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        sell_player_id TEXT NOT NULL,
        buy_player_id TEXT NOT NULL,
        reasoning TEXT NOT NULL,
        tx_hash TEXT NOT NULL,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
        FOREIGN KEY (sell_player_id) REFERENCES players(id),
        FOREIGN KEY (buy_player_id) REFERENCES players(id)
    )
    """)
    
    conn.commit()
    
    # Seed players
    seed_players(conn)
    
    conn.close()

def get_db_connection():
    """Get a connection to the SQLite database."""
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    return conn

# Automatically initialize database when db module is imported
init_db()
