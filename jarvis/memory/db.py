# memory/db.py - ENHANCED WITH CONNECTION POOLING & OPTIMIZATION

import sqlite3
import json
import logging
from datetime import datetime
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent


def _resolve_db_path() -> Path:
    """Resolve memory DB path from central Config with safe fallback."""
    try:
        from config import Config
    except ImportError:
        from ..config import Config

    try:
        return Path(Config.MEMORY_DB)
    except Exception:
        return BASE_DIR / "data" / "memory.db"


DB_PATH = _resolve_db_path()


def _json_dumps(value) -> str:
    try:
        return json.dumps(value, ensure_ascii=False)
    except Exception:
        return json.dumps(str(value), ensure_ascii=False)

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
            logger.info("[OK] Database initialized at %s", DB_PATH)

    def create_tables(self):
        """Create database tables with proper indexing and handle migrations."""
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
        
        # Migration: Ensure session_id exists if table was created by an older version
        cursor.execute("PRAGMA table_info(conversation)")
        columns = [row[1] for row in cursor.fetchall()]
        if "session_id" not in columns:
            logger.info("[MIGRATE] Adding session_id to conversation table")
            cursor.execute("ALTER TABLE conversation ADD COLUMN session_id TEXT DEFAULT 'default'")
        
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

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                task_id TEXT PRIMARY KEY,
                session_id TEXT,
                goal TEXT,
                status TEXT,
                source TEXT,
                notes TEXT,
                metadata TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_session ON tasks(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS task_steps (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_id TEXT,
                step_index INTEGER,
                action TEXT,
                args_json TEXT,
                status TEXT,
                result_text TEXT,
                created_at TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_task_steps_task ON task_steps(task_id)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tool_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                task_id TEXT,
                action TEXT,
                args_json TEXT,
                result_text TEXT,
                success INTEGER,
                duration_ms INTEGER,
                error_text TEXT,
                metadata TEXT,
                created_at TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tool_events_session ON tool_events(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_tool_events_task ON tool_events(task_id)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS evaluations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                task_id TEXT,
                category TEXT,
                metric TEXT,
                score REAL,
                details TEXT,
                created_at TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_evaluations_session ON evaluations(session_id)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS knowledge_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT,
                title TEXT,
                content TEXT,
                tags TEXT,
                source TEXT,
                created_at TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_session ON knowledge_items(session_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_knowledge_title ON knowledge_items(title)")

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS routines (
                routine_name TEXT PRIMARY KEY,
                session_id TEXT,
                goal TEXT,
                steps_json TEXT,
                created_at TEXT,
                updated_at TEXT
            )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_routines_session ON routines(session_id)")
        
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
        logger.info("[OK] Database tables ready")

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
            logger.debug("[OK] Added turn: %s (%s)", role, session_id)
        except Exception as e:
            logger.error("[ERROR] Error adding turn: %s", e)
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
            logger.info("[OK] Session started: %s", session_id)
        except Exception as e:
            logger.error("[ERROR] Error starting session: %s", e)
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
            logger.error("[ERROR] Error getting context: %s", e)
            return []

    def search_conversation(self, query: str, session_id: str | None = None, limit: int = 10):
        """Search recent conversation turns using LIKE matching."""
        try:
            cursor = self.conn.cursor()
            pattern = f"%{query}%"
            if session_id:
                cursor.execute(
                    """
                    SELECT role, content, timestamp
                    FROM conversation
                    WHERE session_id = ? AND content LIKE ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (session_id, pattern, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT role, content, timestamp
                    FROM conversation
                    WHERE content LIKE ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (pattern, limit),
                )
            rows = cursor.fetchall()
            return [
                {"role": row[0], "content": row[1], "timestamp": row[2]}
                for row in rows
            ]
        except Exception as e:
            logger.error("[ERROR] Error searching conversation: %s", e)
            return []

    def create_task(
        self,
        goal: str,
        session_id: str = "default",
        status: str = "queued",
        source: str = "agent",
        notes: str = "",
        metadata: dict | None = None,
    ) -> str:
        task_id = f"task_{int(datetime.now().timestamp() * 1000)}"
        timestamp = datetime.now().isoformat()
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO tasks (task_id, session_id, goal, status, source, notes, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    session_id,
                    goal,
                    status,
                    source,
                    notes,
                    _json_dumps(metadata or {}),
                    timestamp,
                    timestamp,
                ),
            )
            self.conn.commit()
            return task_id
        except Exception as e:
            logger.error("[ERROR] Error creating task: %s", e)
            self.conn.rollback()
            return task_id

    def update_task(self, task_id: str, status: str | None = None, notes: str | None = None, metadata: dict | None = None):
        try:
            updates = []
            values = []
            if status is not None:
                updates.append("status = ?")
                values.append(status)
            if notes is not None:
                updates.append("notes = ?")
                values.append(notes)
            if metadata is not None:
                updates.append("metadata = ?")
                values.append(_json_dumps(metadata))
            updates.append("updated_at = ?")
            values.append(datetime.now().isoformat())
            values.append(task_id)

            cursor = self.conn.cursor()
            cursor.execute(
                f"UPDATE tasks SET {', '.join(updates)} WHERE task_id = ?",
                values,
            )
            self.conn.commit()
        except Exception as e:
            logger.error("[ERROR] Error updating task: %s", e)
            self.conn.rollback()

    def add_task_step(
        self,
        task_id: str,
        step_index: int,
        action: str,
        args: dict | None = None,
        status: str = "planned",
        result_text: str = "",
    ):
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO task_steps (task_id, step_index, action, args_json, status, result_text, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    task_id,
                    step_index,
                    action,
                    _json_dumps(args or {}),
                    status,
                    result_text,
                    datetime.now().isoformat(),
                ),
            )
            self.conn.commit()
        except Exception as e:
            logger.error("[ERROR] Error adding task step: %s", e)
            self.conn.rollback()

    def list_tasks(self, session_id: str | None = None, limit: int = 20):
        try:
            cursor = self.conn.cursor()
            if session_id:
                cursor.execute(
                    """
                    SELECT task_id, goal, status, source, notes, created_at, updated_at
                    FROM tasks
                    WHERE session_id = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (session_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT task_id, goal, status, source, notes, created_at, updated_at
                    FROM tasks
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            rows = cursor.fetchall()
            return [
                {
                    "task_id": row[0],
                    "goal": row[1],
                    "status": row[2],
                    "source": row[3],
                    "notes": row[4],
                    "created_at": row[5],
                    "updated_at": row[6],
                }
                for row in rows
            ]
        except Exception as e:
            logger.error("[ERROR] Error listing tasks: %s", e)
            return []

    def log_tool_event(
        self,
        session_id: str,
        action: str,
        args: dict | None = None,
        result: object = "",
        success: bool = True,
        duration_ms: int = 0,
        task_id: str | None = None,
        error_text: str = "",
        metadata: dict | None = None,
    ):
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO tool_events (session_id, task_id, action, args_json, result_text, success, duration_ms, error_text, metadata, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    task_id,
                    action,
                    _json_dumps(args or {}),
                    str(result)[:4000],
                    1 if success else 0,
                    int(duration_ms),
                    error_text[:2000],
                    _json_dumps(metadata or {}),
                    datetime.now().isoformat(),
                ),
            )
            self.conn.commit()
        except Exception as e:
            logger.error("[ERROR] Error logging tool event: %s", e)
            self.conn.rollback()

    def record_evaluation(
        self,
        session_id: str,
        category: str,
        metric: str,
        score: float,
        details: dict | None = None,
        task_id: str | None = None,
    ):
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO evaluations (session_id, task_id, category, metric, score, details, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    task_id,
                    category,
                    metric,
                    float(score),
                    _json_dumps(details or {}),
                    datetime.now().isoformat(),
                ),
            )
            self.conn.commit()
        except Exception as e:
            logger.error("[ERROR] Error recording evaluation: %s", e)
            self.conn.rollback()

    def add_knowledge(
        self,
        title: str,
        content: str,
        session_id: str = "default",
        tags: list[str] | None = None,
        source: str = "user",
    ):
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO knowledge_items (session_id, title, content, tags, source, created_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    session_id,
                    title,
                    content,
                    _json_dumps(tags or []),
                    source,
                    datetime.now().isoformat(),
                ),
            )
            self.conn.commit()
        except Exception as e:
            logger.error("[ERROR] Error adding knowledge: %s", e)
            self.conn.rollback()

    def search_knowledge(self, query: str, session_id: str | None = None, limit: int = 10):
        try:
            cursor = self.conn.cursor()
            pattern = f"%{query}%"
            if session_id:
                cursor.execute(
                    """
                    SELECT title, content, tags, source, created_at
                    FROM knowledge_items
                    WHERE session_id = ? AND (title LIKE ? OR content LIKE ?)
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (session_id, pattern, pattern, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT title, content, tags, source, created_at
                    FROM knowledge_items
                    WHERE title LIKE ? OR content LIKE ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (pattern, pattern, limit),
                )
            rows = cursor.fetchall()
            return [
                {
                    "title": row[0],
                    "content": row[1],
                    "tags": json.loads(row[2] or "[]"),
                    "source": row[3],
                    "created_at": row[4],
                }
                for row in rows
            ]
        except Exception as e:
            logger.error("[ERROR] Error searching knowledge: %s", e)
            return []

    def save_routine(
        self,
        routine_name: str,
        goal: str,
        steps: list[dict] | None = None,
        session_id: str = "default",
    ):
        timestamp = datetime.now().isoformat()
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                INSERT INTO routines (routine_name, session_id, goal, steps_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(routine_name) DO UPDATE SET
                    session_id = excluded.session_id,
                    goal = excluded.goal,
                    steps_json = excluded.steps_json,
                    updated_at = excluded.updated_at
                """,
                (
                    routine_name,
                    session_id,
                    goal,
                    _json_dumps(steps or []),
                    timestamp,
                    timestamp,
                ),
            )
            self.conn.commit()
        except Exception as e:
            logger.error("[ERROR] Error saving routine: %s", e)
            self.conn.rollback()

    def get_routine(self, routine_name: str):
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                """
                SELECT routine_name, goal, steps_json, created_at, updated_at
                FROM routines
                WHERE routine_name = ?
                """,
                (routine_name,),
            )
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "routine_name": row[0],
                "goal": row[1],
                "steps": json.loads(row[2] or "[]"),
                "created_at": row[3],
                "updated_at": row[4],
            }
        except Exception as e:
            logger.error("[ERROR] Error reading routine: %s", e)
            return None

    def list_routines(self, session_id: str | None = None, limit: int = 20):
        try:
            cursor = self.conn.cursor()
            if session_id:
                cursor.execute(
                    """
                    SELECT routine_name, goal, updated_at
                    FROM routines
                    WHERE session_id = ?
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (session_id, limit),
                )
            else:
                cursor.execute(
                    """
                    SELECT routine_name, goal, updated_at
                    FROM routines
                    ORDER BY updated_at DESC
                    LIMIT ?
                    """,
                    (limit,),
                )
            rows = cursor.fetchall()
            return [
                {"routine_name": row[0], "goal": row[1], "updated_at": row[2]}
                for row in rows
            ]
        except Exception as e:
            logger.error("[ERROR] Error listing routines: %s", e)
            return []

    def get_dashboard_snapshot(self, session_id: str | None = None) -> dict:
        try:
            cursor = self.conn.cursor()
            if session_id:
                cursor.execute("SELECT COUNT(*) FROM knowledge_items WHERE session_id = ?", (session_id,))
                knowledge_count = int(cursor.fetchone()[0] or 0)
                cursor.execute("SELECT COUNT(*) FROM tool_events WHERE session_id = ?", (session_id,))
                tool_event_count = int(cursor.fetchone()[0] or 0)
                cursor.execute(
                    """
                    SELECT title, content, created_at
                    FROM knowledge_items
                    WHERE session_id = ?
                    ORDER BY id DESC
                    LIMIT 8
                    """,
                    (session_id,),
                )
                recent_notes = [
                    {"title": row[0], "content": row[1], "created_at": row[2]}
                    for row in cursor.fetchall()
                ]
                cursor.execute(
                    """
                    SELECT action, result_text, created_at
                    FROM tool_events
                    WHERE session_id = ?
                    ORDER BY id DESC
                    LIMIT 6
                    """,
                    (session_id,),
                )
            else:
                cursor.execute("SELECT COUNT(*) FROM knowledge_items")
                knowledge_count = int(cursor.fetchone()[0] or 0)
                cursor.execute("SELECT COUNT(*) FROM tool_events")
                tool_event_count = int(cursor.fetchone()[0] or 0)
                cursor.execute(
                    """
                    SELECT title, content, created_at
                    FROM knowledge_items
                    ORDER BY id DESC
                    LIMIT 8
                    """
                )
                recent_notes = [
                    {"title": row[0], "content": row[1], "created_at": row[2]}
                    for row in cursor.fetchall()
                ]
                cursor.execute(
                    """
                    SELECT action, result_text, created_at
                    FROM tool_events
                    ORDER BY id DESC
                    LIMIT 6
                    """
                )

            recent_actions = [
                {"action": row[0], "result": row[1], "created_at": row[2]}
                for row in cursor.fetchall()
            ]
            return {
                "tasks": self.list_tasks(session_id=session_id, limit=8),
                "routines": self.list_routines(session_id=session_id, limit=8),
                "knowledge_count": knowledge_count,
                "tool_event_count": tool_event_count,
                "recent_notes": recent_notes,
                "recent_actions": recent_actions,
            }
        except Exception as e:
            logger.error("[ERROR] Error building dashboard snapshot: %s", e)
            return {
                "tasks": [],
                "routines": [],
                "knowledge_count": 0,
                "tool_event_count": 0,
                "recent_notes": [],
                "recent_actions": [],
            }

    def prune(self, limit=100):
        """Remove old conversations, keeping only recent ones."""
        try:
            cursor = self.conn.cursor()
            cursor.execute(
                "DELETE FROM conversation WHERE id NOT IN (SELECT id FROM conversation ORDER BY id DESC LIMIT ?)",
                (limit,)
            )
            self.conn.commit()
            logger.debug("[OK] Pruned database (kept %s latest records)", limit)
        except Exception as e:
            logger.error("[ERROR] Error pruning database: %s", e)
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
            logger.debug("[OK] Set preference: %s", key)
        except Exception as e:
            logger.error("[ERROR] Error setting preference: %s", e)
            self.conn.rollback()

    def get_pref(self, key):
        """Get a preference."""
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT value FROM preferences WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception as e:
            logger.error("[ERROR] Error getting preference: %s", e)
            return None

    def cleanup(self):
        """Cleanup resources."""
        try:
            self.conn.close()
            logger.info("[OK] Database connection closed")
        except Exception as e:
            logger.error("[ERROR] Error closing database: %s", e)
