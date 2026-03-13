#!/usr/bin/env python3
"""
🤖 NEUGI SWARM - MEMORY
========================

Memory system - long-term and short-term memory

Types:
- Short-term: Current conversation context
- Long-term: Persistent SQLite storage
- Agent memory: Per-agent memories
- Knowledge: Structured knowledge base

Usage:
    from neugi_swarm_memory import MemoryManager
    memory = MemoryManager()
    memory.remember("user", "preference", "likes coffee")
    memory.recall("preference")
"""

import os
import json
import sqlite3
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class MemoryType(Enum):
    CONVERSATION = "conversation"
    FACT = "fact"
    PREFERENCE = "preference"
    KNOWLEDGE = "knowledge"
    AGENT = "agent"
    SKILL = "skill"


class MemoryPriority(Enum):
    LOW = 1
    NORMAL = 5
    HIGH = 10
    CRITICAL = 20


@dataclass
class Memory:
    """Memory entry"""

    id: str
    type: MemoryType
    content: str
    importance: int
    tags: List[str]
    created_at: str
    last_accessed: str

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "importance": self.importance,
            "tags": self.tags,
            "created": self.created_at,
            "accessed": self.last_accessed,
        }


class MemoryManager:
    """Manages all memory types"""

    def __init__(self, db_path: str = "./data/memory.db"):
        self.db_path = db_path
        os.makedirs(os.path.dirname(db_path), exist_ok=True)

        self.conn = sqlite3.connect(db_path, check_same_thread=False)
        self.short_term = []  # In-memory cache

        self._init_tables()

    def _init_tables(self):
        """Initialize memory tables"""
        c = self.conn.cursor()

        # Long-term memory
        c.execute("""CREATE TABLE IF NOT EXISTS memories (
            id TEXT PRIMARY KEY,
            type TEXT,
            content TEXT,
            importance INTEGER,
            tags TEXT,
            created_at TEXT,
            last_accessed TEXT,
            metadata TEXT
        )""")

        # Conversations
        c.execute("""CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            session_id TEXT,
            role TEXT,
            content TEXT,
            timestamp TEXT
        )""")

        # Knowledge graph
        c.execute("""CREATE TABLE IF NOT EXISTS knowledge (
            id TEXT PRIMARY KEY,
            entity TEXT,
            relation TEXT,
            target TEXT,
            confidence REAL,
            created_at TEXT
        )""")

        # Indexes
        c.execute("CREATE INDEX IF NOT EXISTS idx_memories_type ON memories(type)")
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_memories_importance ON memories(importance)"
        )
        c.execute(
            "CREATE INDEX IF NOT EXISTS idx_knowledge_entity ON knowledge(entity)"
        )

        self.conn.commit()

    def remember(
        self,
        memory_type: str,
        content: str,
        importance: int = 5,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict] = None,
    ) -> str:
        """Store a memory"""
        memory_id = hashlib.md5(
            f"{content}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        now = datetime.now().isoformat()

        c = self.conn.cursor()
        c.execute(
            """INSERT OR REPLACE INTO memories VALUES (?,?,?,?,?,?,?,?)""",
            (
                memory_id,
                memory_type,
                content,
                importance,
                json.dumps(tags or []),
                now,
                now,
                json.dumps(metadata or {}),
            ),
        )
        self.conn.commit()

        # Also add to short-term
        self.short_term.append(
            Memory(
                id=memory_id,
                type=MemoryType(memory_type),
                content=content,
                importance=importance,
                tags=tags or [],
                created_at=now,
                last_accessed=now,
            )
        )

        # Limit short-term size
        if len(self.short_term) > 100:
            self.short_term = self.short_term[-100:]

        return memory_id

    def recall(
        self,
        query: Optional[str] = None,
        memory_type: Optional[str] = None,
        min_importance: int = 0,
        limit: int = 10,
    ) -> List[Dict]:
        """Recall memories"""
        c = self.conn.cursor()

        sql = "SELECT * FROM memories WHERE importance >= ?"
        params: List[Any] = [min_importance]

        if query:
            sql += " AND (content LIKE ? OR tags LIKE ?)"
            params.extend([f"%{query}%", f"%{query}%"])

        if memory_type:
            sql += " AND type = ?"
            params.append(memory_type)

        sql += " ORDER BY importance DESC, last_accessed DESC LIMIT ?"
        params.append(limit)

        c.execute(sql, params)

        results = []
        for row in c.fetchall():
            results.append(
                {
                    "id": row[0],
                    "type": row[1],
                    "content": row[2],
                    "importance": row[3],
                    "tags": json.loads(row[4]),
                    "created": row[5],
                    "accessed": row[6],
                }
            )

            # Update last accessed
            c.execute(
                "UPDATE memories SET last_accessed = ? WHERE id = ?",
                (datetime.now().isoformat(), row[0]),
            )

        self.conn.commit()
        return results

    def forget(self, memory_id: str) -> bool:
        """Delete a memory"""
        c = self.conn.cursor()
        c.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
        self.conn.commit()
        return c.rowcount > 0

    def consolidate(self) -> int:
        """Consolidate similar memories"""
        # Find duplicate/similar memories and merge
        c = self.conn.cursor()
        c.execute("""SELECT content, COUNT(*) as cnt FROM memories 
                    GROUP BY content HAVING cnt > 1""")

        duplicates = c.fetchall()

        for content, count in duplicates:
            # Keep highest importance, delete others
            c.execute(
                """DELETE FROM memories WHERE content = ? AND 
                        id NOT IN (SELECT id FROM memories WHERE content = ? 
                        ORDER BY importance DESC LIMIT 1)""",
                (content, content),
            )

        self.conn.commit()
        return len(duplicates)

    # Conversation memory
    def add_message(self, session_id: str, role: str, content: str):
        """Add conversation message"""
        msg_id = hashlib.md5(
            f"{session_id}{content}{datetime.now().isoformat()}".encode()
        ).hexdigest()[:16]

        c = self.conn.cursor()
        c.execute(
            "INSERT INTO conversations VALUES (?,?,?,?,?)",
            (msg_id, session_id, role, content, datetime.now().isoformat()),
        )
        self.conn.commit()

    def get_conversation(self, session_id: str, limit: int = 20) -> List[Dict]:
        """Get conversation history"""
        c = self.conn.cursor()
        c.execute(
            """SELECT * FROM conversations WHERE session_id = ? 
                    ORDER BY timestamp DESC LIMIT ?""",
            (session_id, limit),
        )

        messages = []
        for row in c.fetchall():
            messages.append(
                {"id": row[0], "role": row[2], "content": row[3], "timestamp": row[4]}
            )

        return list(reversed(messages))

    # Knowledge graph
    def add_knowledge(
        self, entity: str, relation: str, target: str, confidence: float = 1.0
    ):
        """Add knowledge fact"""
        kg_id = hashlib.md5(f"{entity}{relation}{target}".encode()).hexdigest()[:16]

        c = self.conn.cursor()
        c.execute(
            "INSERT OR REPLACE INTO knowledge VALUES (?,?,?,?,?,?)",
            (kg_id, entity, relation, target, confidence, datetime.now().isoformat()),
        )
        self.conn.commit()

    def query_knowledge(
        self, entity: Optional[str] = None, relation: Optional[str] = None
    ) -> List[Dict]:
        """Query knowledge graph"""
        c = self.conn.cursor()

        if entity:
            c.execute(
                """SELECT * FROM knowledge WHERE entity = ? OR target = ?""",
                (entity, entity),
            )
        elif relation:
            c.execute("SELECT * FROM knowledge WHERE relation = ?", (relation,))
        else:
            c.execute("SELECT * FROM knowledge")

        results = []
        for row in c.fetchall():
            results.append(
                {
                    "id": row[0],
                    "entity": row[1],
                    "relation": row[2],
                    "target": row[3],
                    "confidence": row[4],
                }
            )

        return results

    # Stats
    def stats(self) -> Dict:
        """Get memory statistics"""
        c = self.conn.cursor()

        c.execute("SELECT COUNT(*) FROM memories")
        total_memories = c.fetchone()[0]

        c.execute("SELECT type, COUNT(*) FROM memories GROUP BY type")
        by_type = dict(c.fetchall())

        c.execute("SELECT AVG(importance) FROM memories")
        avg_importance = c.fetchone()[0] or 0

        c.execute("SELECT COUNT(*) FROM conversations")
        total_messages = c.fetchone()[0]

        c.execute("SELECT COUNT(*) FROM knowledge")
        total_knowledge = c.fetchone()[0]

        return {
            "total_memories": total_memories,
            "by_type": by_type,
            "avg_importance": round(avg_importance, 2),
            "total_conversations": total_messages,
            "knowledge_facts": total_knowledge,
            "short_term_cache": len(self.short_term),
        }


# Main
if __name__ == "__main__":
    memory = MemoryManager()

    # Test
    memory.remember("fact", "Neugi is an AI agent", importance=10, tags=["ai", "neugi"])
    memory.remember(
        "preference", "User likes coffee", importance=8, tags=["preference"]
    )
    memory.add_knowledge("Neugi", "is_a", "AGI System", confidence=0.9)

    print("🤖 Neugi Swarm Memory")
    print("=" * 40)
    print(json.dumps(memory.stats(), indent=2))

    print("\nRecall 'AI':")
    print(json.dumps(memory.recall("AI"), indent=2))
