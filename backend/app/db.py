import sqlite3
import os
from pathlib import Path

DB_DIR = Path(__file__).parent.parent / "data"
DB_FILE = DB_DIR / "auth.db"

def init_db():
    """Initialize the SQLite database and create users table if not exists."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = sqlite3.connect(str(DB_FILE))
    cursor = conn.cursor()
    
    # Create users table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE NOT NULL,
        email TEXT UNIQUE NOT NULL,
        password_hash TEXT NOT NULL,
        security_question TEXT NOT NULL,
        security_answer_hash TEXT NOT NULL
    )
    """)
    
    conn.commit()
    conn.close()

def get_db_connection():
    """Get a connection to the SQLite database."""
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    return conn

# Automatically initialize database when db module is imported
init_db()
