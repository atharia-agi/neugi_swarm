"""
NEUGI v2 Memory Core - Production-ready hierarchical memory system.

Combines Karpathy-style dreaming consolidation, CrewAI unified memory,
and LangGraph-style checkpointing into a single cohesive system.

Three-tier storage:
    CORE.md       - Permanent, high-importance knowledge
    daily/*.md    - Session notes with TTL (auto-expire)
    working.json  - Active task context (fast access)

Features:
    - Hierarchical scoped memory (/swarm/, /agent/{id}/, /task/{id}/, /user/, /global/)
    - Composite recall scoring (TF-IDF + recency + importance + frequency)
    - LLM-driven auto-categorization on save (with keyword fallback)
    - Non-blocking background saves with read barriers
    - SQLite FTS5 full-text search + optional sqlite-vec embeddings
    - Memory consolidation/deduplication
    - Source tracking + privacy (private memories per agent)
    - Knowledge graph (entity-relation-target triples)
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

from memory.scopes import ScopePath, MemoryScope, MemorySlice, ScopeAccessError, ScopeError
from memory.scoring import ScoringEngine, ScoreComponents, ScoreConfig
from memory.embeddings import EmbeddingEngine, VectorMemoryIndex

logger = logging.getLogger(__name__)


class MemoryError(Exception):
    """Base exception for memory system errors."""
    pass


class MemoryNotFoundError(MemoryError):
    """Raised when a requested memory entry does not exist."""
    pass


class MemoryWriteError(MemoryError):
    """Raised when a memory write operation fails."""
    pass


class MemoryTier(Enum):
    """
    Three-tier memory storage levels.

    CORE: Permanent, high-importance knowledge (survives dreaming consolidation)
    DAILY: Session notes with TTL (auto-expire after configured days)
    WORKING: Active task context (fast access, volatile)
    """
    CORE = "core"
    DAILY = "daily"
    WORKING = "working"


@dataclass
class MemoryEntry:
    """
    A single memory entry with full metadata.

    Attributes:
        id: Unique identifier (UUID4 by default).
        scope: Hierarchical scope path.
        tier: Storage tier (core/daily/working).
        content: The actual memory text.
        tags: Categorization labels.
        importance: Importance weight [0, 1].
        source: Origin identifier (agent_id, task_id, or "system").
        is_private: If True, only readable by the source agent.
        access_count: How many times this memory has been recalled.
        created_at: Creation timestamp.
        updated_at: Last modification timestamp.
        expires_at: TTL expiration (None = permanent).
        metadata: Arbitrary key-value store.
    """

    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    scope: ScopePath = field(default_factory=ScopePath.global_scope)
    tier: MemoryTier = MemoryTier.DAILY
    content: str = ""
    tags: list[str] = field(default_factory=list)
    importance: float = 0.5
    source: str = "system"
    is_private: bool = False
    access_count: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        d = asdict(self)
        d["scope"] = str(self.scope)
        d["tier"] = self.tier.value
        d["created_at"] = self.created_at.isoformat()
        d["updated_at"] = self.updated_at.isoformat()
        d["expires_at"] = self.expires_at.isoformat() if self.expires_at else None
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryEntry:
        """Deserialize from a dict."""
        data = data.copy()
        data["scope"] = ScopePath.from_string(data["scope"])
        data["tier"] = MemoryTier(data["tier"])
        data["created_at"] = datetime.fromisoformat(data["created_at"])
        data["updated_at"] = datetime.fromisoformat(data["updated_at"])
        if data.get("expires_at"):
            data["expires_at"] = datetime.fromisoformat(data["expires_at"])
        return cls(**data)

    def is_expired(self, now: Optional[datetime] = None) -> bool:
        """Check if this memory has passed its TTL."""
        if self.expires_at is None:
            return False
        now = now or datetime.now(timezone.utc)
        if now.tzinfo is None:
            now = now.replace(tzinfo=timezone.utc)
        return now >= self.expires_at

    def touch(self) -> None:
        """Update the access timestamp and increment counter."""
        self.access_count += 1
        self.updated_at = datetime.now(timezone.utc)


@dataclass
class KnowledgeTriple:
    """
    A knowledge graph triple: (entity, relation, target).

    Used for structured knowledge extraction and reasoning.
    """

    entity: str
    relation: str
    target: str
    confidence: float = 0.5
    source_memory_id: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "entity": self.entity,
            "relation": self.relation,
            "target": self.target,
            "confidence": self.confidence,
            "source_memory_id": self.source_memory_id,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> KnowledgeTriple:
        return cls(
            entity=data["entity"],
            relation=data["relation"],
            target=data["target"],
            confidence=data.get("confidence", 0.5),
            source_memory_id=data.get("source_memory_id"),
            created_at=datetime.fromisoformat(data["created_at"]),
        )


# -- LLM categorization (optional, with keyword fallback) --------------------

_DEFAULT_KEYWORD_CATEGORIES = {
    "preference": ["prefer", "like", "want", "need", "should", "always", "never", "default"],
    "fact": ["is", "are", "was", "has", "have", "contains", "uses", "runs on"],
    "instruction": ["do", "make", "create", "build", "run", "execute", "deploy", "test"],
    "error": ["error", "fail", "bug", "crash", "broken", "issue", "problem", "wrong"],
    "decision": ["decided", "chose", "selected", "agreed", "approved", "rejected"],
    "context": ["working on", "building", "implementing", "refactoring", "fixing"],
}


def _keyword_categorize(content: str) -> tuple[list[str], float]:
    """
    Categorize content using keyword matching (LLM fallback).

    Returns:
        (tags, importance) - inferred tags and importance score.
    """
    lower = content.lower()
    tags: list[str] = []
    max_hits = 0

    for category, keywords in _DEFAULT_KEYWORD_CATEGORIES.items():
        hits = sum(1 for kw in keywords if kw in lower)
        if hits > 0:
            tags.append(category)
        if hits > max_hits:
            max_hits = hits

    # Importance heuristic: more keyword matches = higher importance
    importance = min(1.0, max_hits / 5.0) if max_hits > 0 else 0.3
    return tags, importance


# -- Main Memory System ------------------------------------------------------

class MemorySystem:
    """
    Production-ready hierarchical memory system for NEUGI v2.

    Combines three-tier storage, scoped access, composite scoring,
    SQLite FTS5 search, knowledge graph, and background persistence.

    Usage:
        ms = MemorySystem(base_dir="/data/neugi/memory")
        ms.save("User prefers dark mode", scope=ScopePath.agent_scope("cipher"))
        results = ms.recall("dark mode", agent_id="cipher")
    """

    def __init__(
        self,
        base_dir: str = "./memory_data",
        db_name: str = "memory.db",
        daily_ttl_days: int = 30,
        scoring_config: Optional[ScoreConfig] = None,
        categorizer: Optional[Callable[[str], tuple[list[str], float]]] = None,
        enable_fts: bool = True,
        enable_vec: bool = False,
    ) -> None:
        """
        Initialize the memory system.

        Args:
            base_dir: Root directory for file-based storage (CORE.md, daily/, working.json).
            db_name: SQLite database filename.
            daily_ttl_days: Default TTL for daily memories in days.
            scoring_config: Scoring engine configuration.
            categorizer: Optional LLM-based categorizer function.
                Signature: (content: str) -> (tags: list[str], importance: float)
                Falls back to keyword matching if None.
            enable_fts: Enable SQLite FTS5 full-text search.
            enable_vec: Enable optional sqlite-vec embeddings (requires sqlite-vec).
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.daily_ttl_days = daily_ttl_days
        self.categorizer = categorizer or _keyword_categorize
        self._scoring_config = scoring_config or ScoreConfig()

        # In-memory store (read barrier)
        self._store: dict[str, MemoryEntry] = {}
        self._store_lock = threading.RLock()

        # Knowledge graph
        self._triples: list[KnowledgeTriple] = []
        self._triples_lock = threading.RLock()

        # Background save queue
        self._save_queue: list[MemoryEntry] = []
        self._save_lock = threading.Lock()
        self._save_event = threading.Event()
        self._save_thread: Optional[threading.Thread] = None
        self._running = False

        # Scoring engine
        self.scoring = ScoringEngine(config=self._scoring_config)

        # SQLite connection
        self._db_path = self.base_dir / db_name
        self._conn: Optional[sqlite3.Connection] = None
        self._enable_fts = enable_fts
        self._enable_vec = enable_vec

        # Embedding engine (lazy-loaded)
        self._embedding: Optional[EmbeddingEngine] = None
        self._vector_index: Optional[VectorMemoryIndex] = None

        # Initialize
        self._init_db()
        self._load_from_disk()
        self._start_background_saver()

    def _get_embedding(self) -> Optional[EmbeddingEngine]:
        """Lazy-load embedding engine."""
        if self._embedding is None and self._enable_vec:
            try:
                self._embedding = EmbeddingEngine()
                self._vector_index = VectorMemoryIndex(
                    embedding=self._embedding,
                    db_conn=self._conn,
                )
                logger.info("Vector memory enabled with backend: %s", self._embedding.backend_name)
            except Exception as e:
                logger.warning("Failed to initialize embeddings: %s", e)
                self._enable_vec = False
        return self._embedding

    # -- Database initialization ---------------------------------------------

    def _init_db(self) -> None:
        """Initialize SQLite database with schema and FTS5 index."""
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA synchronous=NORMAL")

        # Main memory table
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                scope TEXT NOT NULL,
                tier TEXT NOT NULL,
                content TEXT NOT NULL,
                tags TEXT,
                importance REAL DEFAULT 0.5,
                source TEXT DEFAULT 'system',
                is_private INTEGER DEFAULT 0,
                access_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL,
                expires_at TEXT,
                metadata TEXT
            );

            CREATE INDEX IF NOT EXISTS idx_memories_scope ON memories(scope);
            CREATE INDEX IF NOT EXISTS idx_memories_tier ON memories(tier);
            CREATE INDEX IF NOT EXISTS idx_memories_source ON memories(source);
            CREATE INDEX IF NOT EXISTS idx_memories_expires ON memories(expires_at);
        """)

        # Knowledge graph table
        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS knowledge_triples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                entity TEXT NOT NULL,
                relation TEXT NOT NULL,
                target TEXT NOT NULL,
                confidence REAL DEFAULT 0.5,
                source_memory_id TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY (source_memory_id) REFERENCES memories(id)
            );

            CREATE INDEX IF NOT EXISTS idx_triples_entity ON knowledge_triples(entity);
            CREATE INDEX IF NOT EXISTS idx_triples_relation ON knowledge_triples(relation);
            CREATE INDEX IF NOT EXISTS idx_triples_target ON knowledge_triples(target);
        """)

        # FTS5 virtual table
        if self._enable_fts:
            try:
                self._conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts
                    USING fts5(content, scope, tags, source, content='memories', content_rowid='rowid');
                """)
                # Create triggers to keep FTS in sync
                self._conn.executescript("""
                    CREATE TRIGGER IF NOT EXISTS memories_ai AFTER INSERT ON memories BEGIN
                        INSERT INTO memories_fts(rowid, content, scope, tags, source)
                        VALUES (new.rowid, new.content, new.scope, new.tags, new.source);
                    END;
                    CREATE TRIGGER IF NOT EXISTS memories_ad AFTER DELETE ON memories BEGIN
                        INSERT INTO memories_fts(memories_fts, rowid, content, scope, tags, source)
                        VALUES ('delete', old.rowid, old.content, old.scope, old.tags, old.source);
                    END;
                    CREATE TRIGGER IF NOT EXISTS memories_au AFTER UPDATE ON memories BEGIN
                        INSERT INTO memories_fts(memories_fts, rowid, content, scope, tags, source)
                        VALUES ('delete', old.rowid, old.content, old.scope, old.tags, old.source);
                        INSERT INTO memories_fts(rowid, content, scope, tags, source)
                        VALUES (new.rowid, new.content, new.scope, new.tags, new.source);
                    END;
                """)
            except sqlite3.OperationalError as e:
                logger.warning("FTS5 not available, falling back to LIKE search: %s", e)
                self._enable_fts = False

        # Optional sqlite-vec extension
        if self._enable_vec:
            try:
                self._conn.enable_load_extension(True)
                # sqlite-vec would be loaded here if available
                # conn.load_extension("vec0")
                self._conn.execute("""
                    CREATE VIRTUAL TABLE IF NOT EXISTS memory_embeddings
                    USING vec0(
                        memory_id TEXT PRIMARY KEY,
                        embedding float[384]
                    );
                """)
            except Exception as e:
                logger.warning("sqlite-vec not available, embeddings disabled: %s", e)
                self._enable_vec = False

        self._conn.commit()

    # -- Disk I/O (file-based tier storage) ----------------------------------

    def _load_from_disk(self) -> None:
        """Load memories from SQLite into the in-memory store."""
        try:
            rows = self._conn.execute("SELECT * FROM memories").fetchall()
            for row in rows:
                entry = self._row_to_entry(row)
                if not entry.is_expired():
                    self._store[entry.id] = entry
                    self.scoring.index(
                        entry.id, entry.content, entry.importance, entry.created_at
                    )
            logger.info("Loaded %d memories from disk", len(self._store))
        except Exception as e:
            logger.error("Failed to load memories from disk: %s", e)

    def _row_to_entry(self, row: sqlite3.Row) -> MemoryEntry:
        """Convert a SQLite row to a MemoryEntry."""
        data = dict(row)
        data["tags"] = json.loads(data["tags"] or "[]")
        data["is_private"] = bool(data["is_private"])
        data["metadata"] = json.loads(data["metadata"] or "{}")
        return MemoryEntry.from_dict(data)

    def _entry_to_row_values(self, entry: MemoryEntry) -> tuple:
        """Convert a MemoryEntry to SQLite insert values."""
        return (
            entry.id,
            str(entry.scope),
            entry.tier.value,
            entry.content,
            json.dumps(entry.tags),
            entry.importance,
            entry.source,
            int(entry.is_private),
            entry.access_count,
            entry.created_at.isoformat(),
            entry.updated_at.isoformat(),
            entry.expires_at.isoformat() if entry.expires_at else None,
            json.dumps(entry.metadata),
        )

    # -- Background saver ----------------------------------------------------

    def _start_background_saver(self) -> None:
        """Start the background save thread."""
        self._running = True
        self._save_thread = threading.Thread(
            target=self._background_save_loop, daemon=True, name="memory-saver"
        )
        self._save_thread.start()

    def _background_save_loop(self) -> None:
        """Background thread that flushes pending saves to disk."""
        while self._running:
            self._save_event.wait(timeout=5.0)
            self._save_event.clear()
            self._flush_save_queue()

    def _flush_save_queue(self) -> None:
        """Persist all queued entries to SQLite."""
        with self._save_lock:
            entries = list(self._save_queue)
            self._save_queue.clear()

        if not entries:
            return

        try:
            conn = self._conn
            if conn is None:
                return
            for entry in entries:
                conn.execute(
                    """
                    INSERT OR REPLACE INTO memories
                    (id, scope, tier, content, tags, importance, source,
                     is_private, access_count, created_at, updated_at,
                     expires_at, metadata)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    self._entry_to_row_values(entry),
                )
            conn.commit()
            logger.debug("Flushed %d entries to disk", len(entries))
        except Exception as e:
            logger.error("Background save failed: %s", e)
            # Re-queue on failure
            with self._save_lock:
                self._save_queue.extend(entries)

    def _queue_save(self, entry: MemoryEntry) -> None:
        """Queue an entry for background save."""
        with self._save_lock:
            self._save_queue.append(entry)
        self._save_event.set()

    # -- Public API: Save ----------------------------------------------------

    def save(
        self,
        content: str,
        scope: Optional[ScopePath] = None,
        tier: MemoryTier = MemoryTier.DAILY,
        tags: Optional[list[str]] = None,
        importance: Optional[float] = None,
        source: str = "system",
        is_private: bool = False,
        ttl_days: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
        extract_triples: bool = True,
    ) -> MemoryEntry:
        """
        Save a new memory entry.

        Auto-categorizes content (via LLM or keyword fallback) to determine
        tags and importance if not explicitly provided.

        Args:
            content: The memory text.
            scope: Hierarchical scope path (defaults to /global/).
            tier: Storage tier (core/daily/working).
            tags: Categorization labels (auto-inferred if None).
            importance: Importance weight [0, 1] (auto-inferred if None).
            source: Origin identifier (agent_id, task_id, etc.).
            is_private: If True, only readable by the source agent.
            ttl_days: TTL for daily memories (uses default if None).
            metadata: Arbitrary key-value store.
            extract_triples: Whether to extract knowledge graph triples.

        Returns:
            The saved MemoryEntry.
        """
        if not content.strip():
            raise MemoryWriteError("Cannot save empty memory content")

        scope = scope or ScopePath.global_scope()

        # Auto-categorize if tags/importance not provided
        if tags is None or importance is None:
            auto_tags, auto_importance = self.categorizer(content)
            if tags is None:
                tags = auto_tags
            if importance is None:
                importance = auto_importance

        # Set TTL for daily tier
        expires_at = None
        if tier == MemoryTier.DAILY:
            ttl = ttl_days if ttl_days is not None else self.daily_ttl_days
            expires_at = datetime.now(timezone.utc) + timedelta(days=ttl)

        entry = MemoryEntry(
            scope=scope,
            tier=tier,
            content=content,
            tags=tags or [],
            importance=importance,
            source=source,
            is_private=is_private,
            expires_at=expires_at,
            metadata=metadata or {},
        )

        # Thread-safe store update
        with self._store_lock:
            self._store[entry.id] = entry

        # Update scoring index
        self.scoring.index(entry.id, entry.content, entry.importance, entry.created_at)

        # Update vector index (async-friendly, non-blocking)
        if self._enable_vec:
            try:
                embed = self._get_embedding()
                if embed and self._vector_index:
                    self._vector_index.add(entry.id, entry.content)
            except Exception as e:
                logger.debug("Vector indexing skipped: %s", e)

        # Queue background save
        self._queue_save(entry)

        # Extract knowledge triples
        if extract_triples:
            self._extract_triples(entry)

        logger.debug("Saved memory %s to %s (tier=%s)", entry.id, scope, tier.value)
        return entry

    # -- Public API: Recall --------------------------------------------------

    def recall(
        self,
        query: str,
        agent_id: Optional[str] = None,
        scope: Optional[ScopePath] = None,
        tier: Optional[MemoryTier] = None,
        tags: Optional[list[str]] = None,
        min_importance: float = 0.0,
        limit: int = 20,
        include_expired: bool = False,
    ) -> list[tuple[MemoryEntry, float, ScoreComponents]]:
        """
        Recall memories matching a query with composite scoring.

        Args:
            query: Search/recall query text.
            agent_id: Requesting agent (enforces scope access control).
            scope: Filter to a specific scope (and its descendants).
            tier: Filter by storage tier.
            tags: Filter by tags (must match at least one).
            min_importance: Minimum importance threshold.
            limit: Maximum number of results.
            include_expired: Include expired daily memories.

        Returns:
            List of (entry, composite_score, score_components) sorted by score.
        """
        with self._store_lock:
            candidates = list(self._store.values())

        # Filter expired
        if not include_expired:
            candidates = [e for e in candidates if not e.is_expired()]

        # Filter by tier
        if tier is not None:
            candidates = [e for e in candidates if e.tier == tier]

        # Filter by scope
        if scope is not None:
            candidates = [e for e in candidates if e.scope.is_subtree_of(scope)]

        # Filter by tags
        if tags:
            tag_set = set(tags)
            candidates = [e for e in candidates if tag_set & set(e.tags)]

        # Filter by importance
        if min_importance > 0:
            candidates = [e for e in candidates if e.importance >= min_importance]

        # Access control
        if agent_id is not None:
            candidates = [e for e in candidates if e.scope.can_read(agent_id)]
            candidates = [e for e in candidates if not e.is_private or e.source == agent_id]

        # Vector similarity boost (if available)
        vector_scores: dict[str, float] = {}
        if self._enable_vec and self._vector_index:
            try:
                vec_results = self._vector_index.search(query, top_k=limit * 3)
                for mid, sim in vec_results:
                    vector_scores[mid] = sim
            except Exception as e:
                logger.debug("Vector search failed: %s", e)

        # Score and rank
        scored = self.scoring.score_all(query, [e.id for e in candidates])
        results: list[tuple[MemoryEntry, float, ScoreComponents]] = []
        for mid, composite, components in scored:
            entry = self._store.get(mid)
            if entry is not None:
                entry.touch()
                self.scoring.record_access(mid)
                # Boost with vector similarity if available
                if mid in vector_scores:
                    composite = composite * 0.7 + vector_scores[mid] * 0.3
                results.append((entry, composite, components))

        # Also include high-similarity vector results that scoring missed
        if vector_scores:
            existing_ids = {r[0].id for r in results}
            for mid, sim in vector_scores.items():
                if mid not in existing_ids and mid in self._store:
                    entry = self._store[mid]
                    if entry not in candidates:
                        continue
                    entry.touch()
                    results.append((entry, sim * 0.5, ScoreComponents()))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    # -- Public API: FTS Search ----------------------------------------------

    def search(
        self,
        query: str,
        agent_id: Optional[str] = None,
        scope: Optional[ScopePath] = None,
        limit: int = 20,
    ) -> list[MemoryEntry]:
        """
        Full-text search using SQLite FTS5.

        Falls back to LIKE-based search if FTS5 is unavailable.

        Args:
            query: Search text.
            agent_id: Requesting agent (enforces access control).
            scope: Filter to a specific scope.
            limit: Maximum results.

        Returns:
            List of matching MemoryEntries.
        """
        results: list[MemoryEntry] = []

        if self._enable_fts and self._conn:
            try:
                sql = "SELECT m.* FROM memories m JOIN memories_fts f ON m.rowid = f.rowid WHERE f.content MATCH ?"
                params: list = [query]
                if scope is not None:
                    sql += " AND m.scope LIKE ?"
                    params.append(f"{scope}%")
                sql += " ORDER BY rank LIMIT ?"
                params.append(limit)

                rows = self._conn.execute(sql, params).fetchall()
                results = [self._row_to_entry(r) for r in rows]
            except Exception as e:
                logger.warning("FTS5 search failed, falling back to LIKE: %s", e)
                results = self._like_search(query, scope, limit)
        else:
            results = self._like_search(query, scope, limit)

        # Access control
        if agent_id is not None:
            results = [e for e in results if e.scope.can_read(agent_id)]
            results = [e for e in results if not e.is_private or e.source == agent_id]

        return results

    def _like_search(
        self, query: str, scope: Optional[ScopePath], limit: int
    ) -> list[MemoryEntry]:
        """Fallback LIKE-based search."""
        with self._store_lock:
            candidates = list(self._store.values())

        query_lower = query.lower()
        results = [e for e in candidates if query_lower in e.content.lower()]

        if scope is not None:
            results = [e for e in results if e.scope.is_subtree_of(scope)]

        return results[:limit]

    # -- Public API: Get / Update / Delete -----------------------------------

    def get(self, memory_id: str) -> Optional[MemoryEntry]:
        """Get a single memory entry by ID."""
        return self._store.get(memory_id)

    def update(
        self,
        memory_id: str,
        content: Optional[str] = None,
        tags: Optional[list[str]] = None,
        importance: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> MemoryEntry:
        """
        Update an existing memory entry.

        Args:
            memory_id: ID of the entry to update.
            content: New content (None to keep existing).
            tags: New tags list (None to keep existing).
            importance: New importance (None to keep existing).
            metadata: Merged into existing metadata.

        Returns:
            The updated MemoryEntry.

        Raises:
            MemoryNotFoundError: If the entry does not exist.
        """
        with self._store_lock:
            entry = self._store.get(memory_id)
            if entry is None:
                raise MemoryNotFoundError(f"Memory {memory_id} not found")

            if content is not None:
                entry.content = content
            if tags is not None:
                entry.tags = tags
            if importance is not None:
                entry.importance = max(0.0, min(1.0, importance))
            if metadata is not None:
                entry.metadata.update(metadata)

            entry.updated_at = datetime.now(timezone.utc)
            self._store[memory_id] = entry

        # Re-index for scoring
        self.scoring.index(entry.id, entry.content, entry.importance, entry.created_at)
        self._queue_save(entry)

        return entry

    def delete(self, memory_id: str) -> bool:
        """
        Delete a memory entry.

        Returns:
            True if the entry was found and deleted.
        """
        with self._store_lock:
            if memory_id not in self._store:
                return False
            del self._store[memory_id]

        self.scoring.remove(memory_id)

        # Remove from SQLite
        if self._conn:
            try:
                self._conn.execute("DELETE FROM memories WHERE id = ?", (memory_id,))
                self._conn.commit()
            except Exception as e:
                logger.error("Failed to delete memory from DB: %s", e)

        return True

    # -- Public API: Knowledge Graph -----------------------------------------

    def _extract_triples(self, entry: MemoryEntry) -> None:
        """
        Extract knowledge graph triples from memory content.

        Uses simple pattern matching as fallback; override with LLM-based
        extraction for production use.
        """
        triples = self._simple_triple_extraction(entry.content, entry.id)
        with self._triples_lock:
            self._triples.extend(triples)

        # Persist to SQLite
        if self._conn and triples:
            try:
                for t in triples:
                    self._conn.execute(
                        """
                        INSERT INTO knowledge_triples
                        (entity, relation, target, confidence, source_memory_id, created_at)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (t.entity, t.relation, t.target, t.confidence,
                         t.source_memory_id, t.created_at.isoformat()),
                    )
                self._conn.commit()
            except Exception as e:
                logger.error("Failed to persist triples: %s", e)

    def _simple_triple_extraction(
        self, content: str, source_id: str
    ) -> list[KnowledgeTriple]:
        """
        Extract simple (entity, relation, target) triples from text.

        Looks for patterns like "X is Y", "X uses Y", "X has Y".
        """
        triples: list[KnowledgeTriple] = []
        sentences = [s.strip() for s in content.replace("\n", ". ").split(".") if s.strip()]

        relation_patterns = [
            (" is ", "is"),
            (" are ", "are"),
            (" uses ", "uses"),
            (" has ", "has"),
            (" contains ", "contains"),
            (" depends on ", "depends_on"),
            (" connects to ", "connects_to"),
            (" runs on ", "runs_on"),
        ]

        for sentence in sentences:
            if len(sentence) < 10:
                continue
            for pattern, relation in relation_patterns:
                if pattern in sentence.lower():
                    parts = sentence.split(pattern, 1)
                    if len(parts) == 2:
                        entity = parts[0].strip().rstrip("s").strip()
                        target = parts[1].strip().rstrip(".").strip()
                        if entity and target and len(entity) > 2 and len(target) > 2:
                            triples.append(KnowledgeTriple(
                                entity=entity,
                                relation=relation,
                                target=target,
                                confidence=0.6,
                                source_memory_id=source_id,
                            ))
                            break  # One triple per sentence

        return triples

    def query_triples(
        self,
        entity: Optional[str] = None,
        relation: Optional[str] = None,
        target: Optional[str] = None,
        min_confidence: float = 0.0,
    ) -> list[KnowledgeTriple]:
        """
        Query the knowledge graph for matching triples.

        Args:
            entity: Filter by entity (partial match).
            relation: Filter by relation (exact match).
            target: Filter by target (partial match).
            min_confidence: Minimum confidence threshold.

        Returns:
            List of matching KnowledgeTriples.
        """
        with self._triples_lock:
            results = list(self._triples)

        if entity:
            entity_lower = entity.lower()
            results = [t for t in results if entity_lower in t.entity.lower()]
        if relation:
            results = [t for t in results if t.relation == relation]
        if target:
            target_lower = target.lower()
            results = [t for t in results if target_lower in t.target.lower()]
        if min_confidence > 0:
            results = [t for t in results if t.confidence >= min_confidence]

        return results

    def add_triple(self, triple: KnowledgeTriple) -> None:
        """Manually add a knowledge triple."""
        with self._triples_lock:
            self._triples.append(triple)

        if self._conn:
            try:
                self._conn.execute(
                    """
                    INSERT INTO knowledge_triples
                    (entity, relation, target, confidence, source_memory_id, created_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    """,
                    (triple.entity, triple.relation, triple.target,
                     triple.confidence, triple.source_memory_id,
                     triple.created_at.isoformat()),
                )
                self._conn.commit()
            except Exception as e:
                logger.error("Failed to persist triple: %s", e)

    # -- Public API: Consolidation / Deduplication ---------------------------

    def deduplicate(self, threshold: float = 0.85) -> list[tuple[str, str]]:
        """
        Find and merge duplicate memories based on content similarity.

        Args:
            threshold: Cosine similarity threshold for considering duplicates.

        Returns:
            List of (kept_id, removed_id) pairs.
        """
        with self._store_lock:
            entries = list(self._store.values())

        merged: list[tuple[str, str]] = []
        seen: set[str] = set()

        for i, entry_a in enumerate(entries):
            if entry_a.id in seen:
                continue
            for entry_b in entries[i + 1:]:
                if entry_b.id in seen:
                    continue
                # Quick check: same scope and tier
                if entry_a.scope != entry_b.scope or entry_a.tier != entry_b.tier:
                    continue
                # Score similarity
                score = self.scoring._semantic_score(entry_a.content, entry_b.id)
                if score >= threshold:
                    # Keep the one with higher importance
                    if entry_a.importance >= entry_b.importance:
                        kept, removed = entry_a, entry_b
                    else:
                        kept, removed = entry_b, entry_a
                    # Merge tags
                    kept.tags = list(set(kept.tags) | set(removed.tags))
                    kept.metadata["merged_from"] = removed.id
                    kept.updated_at = datetime.now(timezone.utc)
                    self._store[kept.id] = kept
                    self.scoring.index(kept.id, kept.content, kept.importance, kept.created_at)
                    self._queue_save(kept)
                    self.delete(removed.id)
                    seen.add(removed.id)
                    merged.append((kept.id, removed.id))

        if merged:
            logger.info("Deduplicated %d memory pairs", len(merged))
        return merged

    def consolidate(self, agent_id: Optional[str] = None) -> dict[str, Any]:
        """
        Run memory consolidation: merge related entries, promote important
        daily memories to core tier.

        Args:
            agent_id: Limit consolidation to a specific agent's scope.

        Returns:
            Summary dict with consolidation stats.
        """
        scope = ScopePath.agent_scope(agent_id) if agent_id else None
        with self._store_lock:
            entries = [
                e for e in self._store.values()
                if e.tier == MemoryTier.DAILY
                and (scope is None or e.scope.is_subtree_of(scope))
                and not e.is_expired()
            ]

        promoted = 0
        merged = 0

        # Promote high-importance, frequently accessed memories to core
        for entry in entries:
            if entry.importance >= 0.8 and entry.access_count >= 3:
                entry.tier = MemoryTier.CORE
                entry.expires_at = None  # Core memories are permanent
                entry.updated_at = datetime.now(timezone.utc)
                self._store[entry.id] = entry
                self._queue_save(entry)
                promoted += 1

        # Deduplicate within the scope
        if entries:
            merged_pairs = self.deduplicate()
            merged = len(merged_pairs)

        stats = {"promoted": promoted, "merged": merged, "total_reviewed": len(entries)}
        logger.info("Consolidation complete: %s", stats)
        return stats

    # -- Public API: Memory Slices -------------------------------------------

    def recall_slice(
        self,
        mem_slice: MemorySlice,
        query: str,
        limit: int = 20,
    ) -> list[tuple[MemoryEntry, float, ScoreComponents]]:
        """
        Recall memories across multiple scopes defined in a MemorySlice.

        Args:
            mem_slice: The memory slice defining which scopes to search.
            query: Search query.
            limit: Maximum results.

        Returns:
            Scored memory entries from all slice scopes.
        """
        mem_slice.validate_access()
        all_results: list[tuple[MemoryEntry, float, ScoreComponents]] = []

        for scope in mem_slice.scopes:
            results = self.recall(query, agent_id=mem_slice.agent_id, scope=scope, limit=limit)
            all_results.extend(results)

        # Deduplicate and re-sort
        seen: set[str] = set()
        unique: list[tuple[MemoryEntry, float, ScoreComponents]] = []
        for entry, score, components in sorted(all_results, key=lambda x: x[1], reverse=True):
            if entry.id not in seen:
                seen.add(entry.id)
                unique.append((entry, score, components))

        return unique[:limit]

    # -- Public API: File-based tier storage ---------------------------------

    def write_core_md(self, scope: Optional[ScopePath] = None) -> Path:
        """
        Write CORE.md file for a scope (permanent knowledge export).

        Returns:
            Path to the written file.
        """
        scope = scope or ScopePath.global_scope()
        dir_path = self.base_dir / str(scope).replace("/", "_").strip("_")
        dir_path.mkdir(parents=True, exist_ok=True)
        core_path = dir_path / "CORE.md"

        with self._store_lock:
            entries = [
                e for e in self._store.values()
                if e.tier == MemoryTier.CORE and e.scope.is_subtree_of(scope)
            ]

        entries.sort(key=lambda e: e.importance, reverse=True)

        with open(core_path, "w", encoding="utf-8") as f:
            f.write(f"# Core Memory - {scope}\n\n")
            f.write(f"Generated: {datetime.now(timezone.utc).isoformat()}\n")
            f.write(f"Entries: {len(entries)}\n\n")
            f.write("---\n\n")

            for entry in entries:
                f.write(f"## [{entry.id}] (importance: {entry.importance:.2f})\n\n")
                f.write(f"Tags: {', '.join(entry.tags)}\n\n")
                f.write(f"{entry.content}\n\n")
                f.write("---\n\n")

        return core_path

    def write_daily_note(self, date: Optional[datetime] = None) -> Path:
        """
        Write a daily note file with all daily-tier memories for a date.

        Returns:
            Path to the written file.
        """
        date = date or datetime.now(timezone.utc)
        daily_dir = self.base_dir / "daily"
        daily_dir.mkdir(parents=True, exist_ok=True)
        filename = date.strftime("%Y-%m-%d.md")
        filepath = daily_dir / filename

        with self._store_lock:
            entries = [
                e for e in self._store.values()
                if e.tier == MemoryTier.DAILY
                and e.created_at.date() == date.date()
            ]

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(f"# Daily Notes - {date.strftime('%Y-%m-%d')}\n\n")
            f.write(f"Entries: {len(entries)}\n\n")
            f.write("---\n\n")

            for entry in entries:
                f.write(f"### [{entry.id}] {entry.scope} (source: {entry.source})\n\n")
                f.write(f"Tags: {', '.join(entry.tags)} | "
                        f"Importance: {entry.importance:.2f} | "
                        f"Accesses: {entry.access_count}\n\n")
                f.write(f"{entry.content}\n\n")
                f.write("---\n\n")

        return filepath

    def write_working_json(self, agent_id: Optional[str] = None) -> Path:
        """
        Write working.json with active task context.

        Returns:
            Path to the written file.
        """
        filepath = self.base_dir / "working.json"

        with self._store_lock:
            entries = [
                e for e in self._store.values()
                if e.tier == MemoryTier.WORKING
                and (agent_id is None or e.source == agent_id)
            ]

        data = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "agent_id": agent_id,
            "entries": [e.to_dict() for e in entries],
        }

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

        return filepath

    # -- Cleanup -------------------------------------------------------------

    def cleanup_expired(self) -> int:
        """
        Remove expired daily memories.

        Returns:
            Number of entries removed.
        """
        now = datetime.now(timezone.utc)
        with self._store_lock:
            expired = [e.id for e in self._store.values() if e.is_expired(now)]

        for mid in expired:
            del self._store[mid]
            self.scoring.remove(mid)

        if expired and self._conn:
            try:
                placeholders = ",".join("?" * len(expired))
                self._conn.execute(
                    f"DELETE FROM memories WHERE id IN ({placeholders})", expired
                )
                self._conn.commit()
            except Exception as e:
                logger.error("Failed to cleanup expired memories from DB: %s", e)

        if expired:
            logger.info("Cleaned up %d expired memories", len(expired))
        return len(expired)

    # -- Lifecycle -----------------------------------------------------------

    def close(self) -> None:
        """Shut down the memory system, flushing all pending saves."""
        self._running = False
        self._save_event.set()
        if self._save_thread:
            self._save_thread.join(timeout=10.0)
        self._flush_save_queue()
        if self._conn:
            self._conn.close()
            self._conn = None
        logger.info("Memory system closed")

    def __enter__(self) -> "MemorySystem":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()

    def __del__(self) -> None:
        try:
            self.close()
        except Exception:
            pass

    # -- Stats ---------------------------------------------------------------

    @property
    def stats(self) -> dict[str, Any]:
        """Get memory system statistics."""
        with self._store_lock:
            entries = list(self._store.values())

        tier_counts: dict[str, int] = {}
        for e in entries:
            tier_counts[e.tier.value] = tier_counts.get(e.tier.value, 0) + 1

        return {
            "total_entries": len(entries),
            "tier_counts": tier_counts,
            "knowledge_triples": len(self._triples),
            "pending_saves": len(self._save_queue),
            "scoring_indexed": self.scoring.indexed_count,
            "db_path": str(self._db_path),
        }
