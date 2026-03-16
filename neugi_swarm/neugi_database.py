#!/usr/bin/env python3
"""
🤖 NEUGI DATABASE LAYER
=========================

SQLite-based persistence layer:
- Conversations storage
- Memory persistence
- Workflow state
- Metrics history
- Audit logs

Version: 1.0
Date: March 16, 2026
"""

import os
import sqlite3
import json
import uuid
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from contextlib import contextmanager

NEUGI_DIR = os.path.expanduser("~/neugi")
DB_PATH = os.path.join(NEUGI_DIR, "neugi.db")
os.makedirs(NEUGI_DIR, exist_ok=True)


class Database:
    """SQLite Database Manager"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.db_path = DB_PATH
        self.init_database()

    @contextmanager
    def get_connection(self):
        """Get database connection with context manager"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def init_database(self):
        """Initialize database schema"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS conversations (
                    id TEXT PRIMARY KEY,
                    title TEXT,
                    created_at TEXT,
                    updated_at TEXT,
                    message_count INTEGER DEFAULT 0,
                    metadata TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id TEXT PRIMARY KEY,
                    conversation_id TEXT,
                    role TEXT,
                    content TEXT,
                    timestamp TEXT,
                    tools_used TEXT,
                    model TEXT,
                    tokens_used INTEGER,
                    FOREIGN KEY (conversation_id) REFERENCES conversations(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS memory (
                    id TEXT PRIMARY KEY,
                    key TEXT UNIQUE,
                    value TEXT,
                    category TEXT,
                    importance INTEGER DEFAULT 5,
                    created_at TEXT,
                    updated_at TEXT,
                    expires_at TEXT,
                    tags TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workflows (
                    id TEXT PRIMARY KEY,
                    name TEXT,
                    description TEXT,
                    definition TEXT,
                    enabled INTEGER DEFAULT 1,
                    schedule TEXT,
                    last_run TEXT,
                    run_count INTEGER DEFAULT 0,
                    created_at TEXT,
                    updated_at TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS workflow_runs (
                    id TEXT PRIMARY KEY,
                    workflow_id TEXT,
                    started_at TEXT,
                    completed_at TEXT,
                    status TEXT,
                    result TEXT,
                    error TEXT,
                    FOREIGN KEY (workflow_id) REFERENCES workflows(id)
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metrics (
                    id TEXT PRIMARY KEY,
                    metric_type TEXT,
                    value REAL,
                    timestamp TEXT,
                    tags TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    id TEXT PRIMARY KEY,
                    action TEXT,
                    user TEXT,
                    details TEXT,
                    ip_address TEXT,
                    timestamp TEXT
                )
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS settings (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT
                )
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_messages_conversation 
                ON messages(conversation_id)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_memory_key 
                ON memory(key)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metrics_type_time 
                ON metrics(metric_type, timestamp)
            """)


class ConversationStore:
    """Conversation storage"""

    @staticmethod
    def create(title: str = "New Conversation") -> Dict:
        """Create new conversation"""
        db = Database()
        conv_id = str(uuid.uuid4())[:12]
        now = datetime.now().isoformat()

        with db.get_connection() as conn:
            conn.execute(
                "INSERT INTO conversations (id, title, created_at, updated_at, message_count) VALUES (?, ?, ?, ?, 0)",
                (conv_id, title, now, now),
            )

        return {"id": conv_id, "title": title, "created_at": now, "updated_at": now}

    @staticmethod
    def add_message(
        conversation_id: str,
        role: str,
        content: str,
        tools_used: List[str] = None,
        model: str = None,
        tokens: int = 0,
    ):
        """Add message to conversation"""
        db = Database()
        msg_id = str(uuid.uuid4())[:12]
        now = datetime.now().isoformat()

        with db.get_connection() as conn:
            conn.execute(
                """INSERT INTO messages (id, conversation_id, role, content, timestamp, tools_used, model, tokens_used) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    msg_id,
                    conversation_id,
                    role,
                    content,
                    now,
                    json.dumps(tools_used or []),
                    model,
                    tokens,
                ),
            )

            conn.execute(
                "UPDATE conversations SET message_count = message_count + 1, updated_at = ? WHERE id = ?",
                (now, conversation_id),
            )

    @staticmethod
    def get(conversation_id: str) -> Optional[Dict]:
        """Get conversation"""
        db = Database()
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM conversations WHERE id = ?", (conversation_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return dict(row)

    @staticmethod
    def get_messages(conversation_id: str, limit: int = 100) -> List[Dict]:
        """Get conversation messages"""
        db = Database()
        with db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM messages WHERE conversation_id = ? ORDER BY timestamp ASC LIMIT ?",
                (conversation_id, limit),
            )
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def list(limit: int = 50) -> List[Dict]:
        """List conversations"""
        db = Database()
        with db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM conversations ORDER BY updated_at DESC LIMIT ?", (limit,)
            )
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def delete(conversation_id: str):
        """Delete conversation"""
        db = Database()
        with db.get_connection() as conn:
            conn.execute("DELETE FROM messages WHERE conversation_id = ?", (conversation_id,))
            conn.execute("DELETE FROM conversations WHERE id = ?", (conversation_id,))


class MemoryStore:
    """Memory storage"""

    @staticmethod
    def set(
        key: str,
        value: Any,
        category: str = "general",
        importance: int = 5,
        tags: List[str] = None,
        ttl_days: int = None,
    ):
        """Store memory"""
        db = Database()
        now = datetime.now().isoformat()
        expires = None
        if ttl_days:
            expires = (datetime.now() + timedelta(days=ttl_days)).isoformat()

        with db.get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO memory (key, value, category, importance, created_at, updated_at, expires_at, tags) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    key,
                    json.dumps(value),
                    category,
                    importance,
                    now,
                    now,
                    expires,
                    json.dumps(tags or []),
                ),
            )

    @staticmethod
    def get(key: str) -> Optional[Any]:
        """Get memory"""
        db = Database()
        with db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM memory WHERE key = ? AND (expires_at IS NULL OR expires_at > ?)",
                (key, datetime.now().isoformat()),
            )
            row = cursor.fetchone()
            if row:
                return json.loads(row["value"])
        return None

    @staticmethod
    def search(query: str, category: str = None, limit: int = 20) -> List[Dict]:
        """Search memories"""
        db = Database()
        with db.get_connection() as conn:
            if category:
                cursor = conn.execute(
                    "SELECT * FROM memory WHERE category = ? AND key LIKE ? ORDER BY importance DESC LIMIT ?",
                    (category, f"%{query}%", limit),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM memory WHERE key LIKE ? OR value LIKE ? ORDER BY importance DESC LIMIT ?",
                    (f"%{query}%", f"%{query}%", limit),
                )
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def delete(key: str):
        """Delete memory"""
        db = Database()
        with db.get_connection() as conn:
            conn.execute("DELETE FROM memory WHERE key = ?", (key,))

    @staticmethod
    def cleanup():
        """Clean expired memories"""
        db = Database()
        with db.get_connection() as conn:
            conn.execute(
                "DELETE FROM memory WHERE expires_at IS NOT NULL AND expires_at < ?",
                (datetime.now().isoformat(),),
            )


class WorkflowStore:
    """Workflow storage"""

    @staticmethod
    def save(workflow_data: Dict):
        """Save workflow"""
        db = Database()
        now = datetime.now().isoformat()

        with db.get_connection() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO workflows 
                   (id, name, description, definition, enabled, schedule, last_run, run_count, created_at, updated_at) 
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    workflow_data.get("id"),
                    workflow_data.get("name"),
                    workflow_data.get("description"),
                    json.dumps(workflow_data.get("nodes", [])),
                    workflow_data.get("enabled", 1),
                    workflow_data.get("schedule"),
                    workflow_data.get("last_run"),
                    workflow_data.get("run_count", 0),
                    workflow_data.get("created_at", now),
                    now,
                ),
            )

    @staticmethod
    def get(workflow_id: str) -> Optional[Dict]:
        """Get workflow"""
        db = Database()
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM workflows WHERE id = ?", (workflow_id,))
            row = cursor.fetchone()
            if row:
                data = dict(row)
                data["nodes"] = json.loads(data.get("definition", "[]"))
                return data
        return None

    @staticmethod
    def list() -> List[Dict]:
        """List workflows"""
        db = Database()
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT * FROM workflows ORDER BY updated_at DESC")
            workflows = []
            for row in cursor.fetchall():
                data = dict(row)
                data["nodes"] = json.loads(data.get("definition", "[]"))
                workflows.append(data)
            return workflows

    @staticmethod
    def delete(workflow_id: str):
        """Delete workflow"""
        db = Database()
        with db.get_connection() as conn:
            conn.execute("DELETE FROM workflow_runs WHERE workflow_id = ?", (workflow_id,))
            conn.execute("DELETE FROM workflows WHERE id = ?", (workflow_id,))

    @staticmethod
    def log_run(workflow_id: str, status: str, result: Any = None, error: str = None):
        """Log workflow run"""
        db = Database()
        run_id = str(uuid.uuid4())[:12]
        now = datetime.now().isoformat()

        with db.get_connection() as conn:
            conn.execute(
                """INSERT INTO workflow_runs (id, workflow_id, started_at, completed_at, status, result, error) 
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    run_id,
                    workflow_id,
                    now,
                    now,
                    status,
                    json.dumps(result) if result else None,
                    error,
                ),
            )

            conn.execute(
                "UPDATE workflows SET last_run = ?, run_count = run_count + 1 WHERE id = ?",
                (now, workflow_id),
            )


class MetricsStore:
    """Metrics storage"""

    @staticmethod
    def record(metric_type: str, value: float, tags: Dict = None):
        """Record metric"""
        db = Database()
        metric_id = str(uuid.uuid4())[:12]
        now = datetime.now().isoformat()

        with db.get_connection() as conn:
            conn.execute(
                "INSERT INTO metrics (id, metric_type, value, timestamp, tags) VALUES (?, ?, ?, ?, ?)",
                (metric_id, metric_type, value, now, json.dumps(tags or {})),
            )

    @staticmethod
    def query(
        metric_type: str, since: datetime = None, until: datetime = None, limit: int = 1000
    ) -> List[Dict]:
        """Query metrics"""
        db = Database()

        query = "SELECT * FROM metrics WHERE metric_type = ?"
        params = [metric_type]

        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())
        if until:
            query += " AND timestamp <= ?"
            params.append(until.isoformat())

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with db.get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]

    @staticmethod
    def aggregate(metric_type: str, since: datetime, until: datetime = None) -> Dict:
        """Aggregate metrics"""
        db = Database()

        query = "SELECT AVG(value) as avg, MIN(value) as min, MAX(value) as max, COUNT(*) as count FROM metrics WHERE metric_type = ? AND timestamp >= ?"
        params = [metric_type, since.isoformat()]

        if until:
            query += " AND timestamp <= ?"
            params.append(until.isoformat())

        with db.get_connection() as conn:
            cursor = conn.execute(query, params)
            row = cursor.fetchone()
            return {"avg": row["avg"], "min": row["min"], "max": row["max"], "count": row["count"]}


class AuditLog:
    """Audit logging"""

    @staticmethod
    def log(action: str, details: Dict = None, user: str = "system", ip_address: str = None):
        """Log action"""
        db = Database()
        log_id = str(uuid.uuid4())[:12]
        now = datetime.now().isoformat()

        with db.get_connection() as conn:
            conn.execute(
                "INSERT INTO audit_log (id, action, user, details, ip_address, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                (log_id, action, user, json.dumps(details or {}), ip_address, now),
            )

    @staticmethod
    def query(action: str = None, user: str = None, limit: int = 100) -> List[Dict]:
        """Query audit logs"""
        db = Database()

        query = "SELECT * FROM audit_log"
        conditions = []
        params = []

        if action:
            conditions.append("action = ?")
            params.append(action)
        if user:
            conditions.append("user = ?")
            params.append(user)

        if conditions:
            query += " WHERE " + " AND ".join(conditions)

        query += " ORDER BY timestamp DESC LIMIT ?"
        params.append(limit)

        with db.get_connection() as conn:
            cursor = conn.execute(query, params)
            return [dict(row) for row in cursor.fetchall()]


class Settings:
    """Settings storage"""

    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """Get setting"""
        db = Database()
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT value FROM settings WHERE key = ?", (key,))
            row = cursor.fetchone()
            if row:
                try:
                    return json.loads(row["value"])
                except:
                    return row["value"]
        return default

    @staticmethod
    def set(key: str, value: Any):
        """Set setting"""
        db = Database()
        now = datetime.now().isoformat()

        with db.get_connection() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
                (key, json.dumps(value), now),
            )


def init_db():
    """Initialize database"""
    db = Database()
    print(f"Database initialized at: {DB_PATH}")
    return db


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Database")
    parser.add_argument("--init", action="store_true", help="Initialize database")
    parser.add_argument("--cleanup", action="store_true", help="Cleanup expired data")
    parser.add_argument("--stats", action="store_true", help="Show database stats")

    args = parser.parse_args()

    if args.init or args.stats:
        db = init_db()

    if args.cleanup:
        MemoryStore.cleanup()
        print("Cleaned up expired memories")

    if args.stats:
        print("\n📊 Database Statistics:")
        print(f"   Database: {DB_PATH}")

        with Database().get_connection() as conn:
            for table in [
                "conversations",
                "messages",
                "memory",
                "workflows",
                "workflow_runs",
                "metrics",
                "audit_log",
                "settings",
            ]:
                cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
                count = cursor.fetchone()[0]
                print(f"   {table}: {count} rows")


if __name__ == "__main__":
    main()
