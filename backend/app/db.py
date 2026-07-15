import sqlite3
import os
from pathlib import Path

DB_DIR = Path(__file__).parent.parent / "data"
DB_FILE = DB_DIR / "auth.db"

def seed_players(conn):
    """Synchronize the SQLite player cache with the current roster catalog."""
    cursor = conn.cursor()
    from .data import get_players

    for player in get_players():
        premium = player.premium_stats
        cursor.execute(
            """
            INSERT INTO players
            (id, name, position, team, price, is_available, points, xg_per_game, injury_risk, scout_note, flag, number)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                position = excluded.position,
                team = excluded.team,
                price = excluded.price,
                is_available = excluded.is_available,
                points = excluded.points,
                xg_per_game = excluded.xg_per_game,
                injury_risk = excluded.injury_risk,
                scout_note = excluded.scout_note,
                flag = excluded.flag,
                number = excluded.number
            """,
            (
                player.id,
                player.name,
                player.position,
                player.team,
                player.price,
                1 if player.isAvailable else 0,
                player.points,
                premium.xg_per_game,
                premium.injury_risk,
                premium.scout_note,
                player.flag,
                player.number
            )
        )
    conn.commit()
    print("Database: synchronized FIFA World Cup 2026 roster catalog.")

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
    for statement in (
        "ALTER TABLE users ADD COLUMN membership_tier TEXT DEFAULT 'free'",
        "ALTER TABLE users ADD COLUMN membership_status TEXT DEFAULT 'inactive'",
        "ALTER TABLE users ADD COLUMN membership_source TEXT",
        "ALTER TABLE users ADD COLUMN membership_expires_at TEXT",
        "ALTER TABLE users ADD COLUMN access_pass_expires_at TEXT",
        "ALTER TABLE users ADD COLUMN wallet_address TEXT",
    ):
        try:
            cursor.execute(statement)
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

    # 6. Keep an auditable record of membership and x402 access grants.
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS access_transactions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        access_mode TEXT NOT NULL,
        amount REAL NOT NULL,
        currency TEXT NOT NULL DEFAULT 'USDC',
        source TEXT NOT NULL,
        receipt TEXT NOT NULL,
        simulated INTEGER DEFAULT 0,
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
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
