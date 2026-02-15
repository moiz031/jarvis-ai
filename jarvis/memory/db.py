# memory/db.py - ENHANCED WITH CONNECTION POOLING & OPTIMIZATION

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent
DB_PATH = BASE_DIR / "data" / "memory.db"

class MemoryDB:
    """Database with connection pooling and optimizations."""
    
    _instance = None
    _lock = Lock()
    _initialized = False  # Fix: Move _initialized to class level
    
    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
        return cls._instance
    
    def __init__(self):
        # Fix: Use class-level _initialized flag with lock
        with self._lock:
            if MemoryDB._initialized:
                return
            
            DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(DB_PATH, check_same_thread=False, timeout=10)
            self.conn.execute("PRAGMA journal_mode=WAL")  # Write-Ahead Logging for better concurrency
            self.conn.execute("PRAGMA synchronous=NORMAL")  # Faster writes
            self.create_tables()
            MemoryDB._initialized = True
            logger.info(f"✅ Database initialized at {DB_PATH}")

    def create_tables(self):
        """Create database tables with proper indexing."""
        cursor = self.conn.cursor()
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conversation (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                timestamp TEXT,
                role TEXT,
                content TEXT
            )
        """)
        
        # Add indexes for faster queries
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session ON conversation(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_timestamp ON conversation(timestamp DESC)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_role ON conversation(role)")
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                session_id TEXT PRIMARY KEY,
                start_time TEXT,
                summary TEXT
            )
        """)
        
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS preferences (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        """)
        
        # Vector storage for embeddings (future use)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS embeddings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                content_hash TEXT UNIQUE,
                embedding BLOB,
                created_at TEXT
            )
        """)
        
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_session_embeddings ON embeddings(session_id)")
        
        self.conn.commit()
        logger.info("✅ Database tables ready")

    def add_turn(self, role: str, content: str, session_id: str = "default"):
        """Add a conversation turn with auto-pruning."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT INTO conversation (session_id, timestamp, role, content) VALUES (?, ?, ?, ?)",
                (session_id, datetime.now().isoformat(), role, content)
            )
            self.conn.commit()
            self.prune(limit=100)
            logger.debug(f"✅ Added turn: {role} ({session_id})")
        except Exception as e:
            logger.error(f"❌ Error adding turn: {e}")
            self.conn.rollback()

    def start_session(self, session_id: str):
        """Start a new session."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO sessions (session_id, start_time) VALUES (?, ?)",
                (session_id, datetime.now().isoformat())
            )
            self.conn.commit()
            logger.info(f"✅ Session started: {session_id}")
        except Exception as e:
            logger.error(f"❌ Error starting session: {e}")
            self.conn.rollback()

    def get_context(self, limit=10, session_id: str = None):
        """Get conversation context with optional session filtering."""
        try:
            cursor = self.conn.cursor()
            if session_id:
                cursor.execute(
                    "SELECT role, content FROM conversation WHERE session_id = ? ORDER BY id DESC LIMIT ?",
                    (session_id, limit)
                )
            else:
                cursor.execute(
                    "SELECT role, content FROM conversation ORDER BY id DESC LIMIT ?",
                    (limit,)
                )
            rows = cursor.fetchall()
            return [{"role": r[0], "content": r[1]} for r in reversed(rows)]
        except Exception as e:
            logger.error(f"❌ Error getting context: {e}")
            return []

    def prune(self, limit=100):
        """Remove old conversations, keeping only recent ones."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "DELETE FROM conversation WHERE id NOT IN (SELECT id FROM conversation ORDER BY id DESC LIMIT ?)",
                (limit,)
            )
            self.conn.commit()
            logger.debug(f"✅ Pruned database (kept {limit} latest records)")
        except Exception as e:
            logger.error(f"❌ Error pruning database: {e}")
            self.conn.rollback()

    def set_pref(self, key, value):
        """Set a preference."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO preferences (key, value) VALUES (?, ?)",
                (key, str(value))
            )
            self.conn.commit()
            logger.debug(f"✅ Set preference: {key}")
        except Exception as e:
            logger.error(f"❌ Error setting preference: {e}")
            self.conn.rollback()

    def get_pref(self, key):
        """Get a preference."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT value FROM preferences WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            logger.error(f"❌ Error getting preference: {e}")
            return None

    def cleanup(self):
        """Cleanup resources."""
        try:
            self.conn.close()
            logger.info("✅ Database connection closed")
        except Exception as e:
            logger.error(f"❌ Error closing database: {e}")
