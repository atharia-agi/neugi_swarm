"""
Session lifecycle management with isolation modes, persistence,
checkpointing, and write-lock support.

Provides the core session infrastructure that NEUGI v2 agents
operate within, including session creation, activation, pausing,
resuming, resetting, and termination.
"""

try:
    import fcntl
except ImportError:
    # Windows compatibility stub
    fcntl = None
import json
import logging
import os
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class SessionState(str, Enum):
    """Lifecycle states of a session."""
    CREATED = "created"
    ACTIVE = "active"
    PAUSED = "paused"
    RESETTING = "resetting"
    TERMINATED = "terminated"


class SessionIsolationMode(str, Enum):
    """Session key-space isolation strategies."""
    SHARED = "shared"
    PER_PEER = "per-peer"
    PER_CHANNEL_PEER = "per-channel-peer"
    PER_ACCOUNT_CHANNEL_PEER = "per-account-channel-peer"


@dataclass
class SessionConfig:
    """Configuration for session behavior."""
    isolation_mode: SessionIsolationMode = SessionIsolationMode.SHARED
    daily_reset_hour: int = 4
    idle_reset_minutes: Optional[int] = None
    max_transcript_lines: int = 10000
    enable_checkpointing: bool = True
    checkpoint_dir: Optional[str] = None
    session_dir: Optional[str] = None
    lock_timeout_seconds: float = 30.0
    compaction_token_threshold: int = 32768
    metadata_ttl_days: int = 90

    def __post_init__(self) -> None:
        if not (0 <= self.daily_reset_hour <= 23):
            raise ValueError("daily_reset_hour must be 0-23")
        if self.idle_reset_minutes is not None and self.idle_reset_minutes <= 0:
            raise ValueError("idle_reset_minutes must be positive")


@dataclass
class SessionMetadata:
    """Serializable metadata for a session."""
    session_id: str
    state: str
    isolation_mode: str
    created_at: str
    activated_at: Optional[str] = None
    last_activity_at: Optional[str] = None
    last_reset_at: Optional[str] = None
    terminated_at: Optional[str] = None
    peer_id: Optional[str] = None
    channel_id: Optional[str] = None
    account_id: Optional[str] = None
    transcript_path: Optional[str] = None
    message_count: int = 0
    token_estimate: int = 0
    reset_count: int = 0
    compaction_count: int = 0
    custom_fields: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize metadata to a dictionary."""
        return {
            "session_id": self.session_id,
            "state": self.state,
            "isolation_mode": self.isolation_mode,
            "created_at": self.created_at,
            "activated_at": self.activated_at,
            "last_activity_at": self.last_activity_at,
            "last_reset_at": self.last_reset_at,
            "terminated_at": self.terminated_at,
            "peer_id": self.peer_id,
            "channel_id": self.channel_id,
            "account_id": self.account_id,
            "transcript_path": self.transcript_path,
            "message_count": self.message_count,
            "token_estimate": self.token_estimate,
            "reset_count": self.reset_count,
            "compaction_count": self.compaction_count,
            "custom_fields": self.custom_fields,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionMetadata":
        """Deserialize metadata from a dictionary."""
        return cls(
            session_id=data["session_id"],
            state=data["state"],
            isolation_mode=data["isolation_mode"],
            created_at=data["created_at"],
            activated_at=data.get("activated_at"),
            last_activity_at=data.get("last_activity_at"),
            last_reset_at=data.get("last_reset_at"),
            terminated_at=data.get("terminated_at"),
            peer_id=data.get("peer_id"),
            channel_id=data.get("channel_id"),
            account_id=data.get("account_id"),
            transcript_path=data.get("transcript_path"),
            message_count=data.get("message_count", 0),
            token_estimate=data.get("token_estimate", 0),
            reset_count=data.get("reset_count", 0),
            compaction_count=data.get("compaction_count", 0),
            custom_fields=data.get("custom_fields", {}),
        )


@dataclass
class SessionCheckpoint:
    """Snapshot of session state for recovery."""
    checkpoint_id: str
    session_id: str
    timestamp: str
    kind: str  # "before" or "after"
    state_snapshot: Dict[str, Any]
    transcript_head: int
    token_estimate: int
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize checkpoint to a dictionary."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "session_id": self.session_id,
            "timestamp": self.timestamp,
            "kind": self.kind,
            "state_snapshot": self.state_snapshot,
            "transcript_head": self.transcript_head,
            "token_estimate": self.token_estimate,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SessionCheckpoint":
        """Deserialize checkpoint from a dictionary."""
        return cls(
            checkpoint_id=data["checkpoint_id"],
            session_id=data["session_id"],
            timestamp=data["timestamp"],
            kind=data["kind"],
            state_snapshot=data["state_snapshot"],
            transcript_head=data["transcript_head"],
            token_estimate=data["token_estimate"],
            metadata=data.get("metadata", {}),
        )


class Session:
    """
    Represents a single conversation session with lifecycle management.

    A session encapsulates a conversation context including its transcript,
    metadata, key-space isolation, and write-lock state. Sessions transition
    through states: CREATED -> ACTIVE -> (PAUSED <-> ACTIVE) -> TERMINATED.

    Attributes:
        session_id: Unique identifier for this session.
        config: Session configuration governing behavior.
        metadata: Serializable session metadata.
        key_space: Isolated key-value store for this session's sub-agents.
    """

    def __init__(
        self,
        session_id: str,
        config: SessionConfig,
        peer_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> None:
        self.session_id = session_id
        self.config = config
        self.metadata = SessionMetadata(
            session_id=session_id,
            state=SessionState.CREATED.value,
            isolation_mode=config.isolation_mode.value,
            created_at=datetime.now(timezone.utc).isoformat(),
            peer_id=peer_id,
            channel_id=channel_id,
            account_id=account_id,
        )
        self.key_space: Dict[str, Any] = {}
        self._lock = threading.Lock()
        self._write_locked = False
        self._write_lock_owner: Optional[str] = None
        self._last_daily_reset_check: Optional[datetime] = None

        if config.session_dir:
            self._session_dir = Path(config.session_dir)
        else:
            self._session_dir = Path.cwd() / "sessions" / session_id

        self._session_dir.mkdir(parents=True, exist_ok=True)
        self.metadata.transcript_path = str(self._session_dir / "transcript.jsonl")

    @property
    def state(self) -> SessionState:
        """Current session state."""
        return SessionState(self.metadata.state)

    @property
    def is_active(self) -> bool:
        """Whether the session is currently active."""
        return self.state == SessionState.ACTIVE

    @property
    def is_write_locked(self) -> bool:
        """Whether the session has an exclusive write lock."""
        return self._write_locked

    def activate(self) -> None:
        """Transition session to ACTIVE state."""
        with self._lock:
            if self.state == SessionState.TERMINATED:
                raise RuntimeError("Cannot activate a terminated session")
            now = datetime.now(timezone.utc).isoformat()
            self.metadata.state = SessionState.ACTIVE.value
            self.metadata.activated_at = now
            self.metadata.last_activity_at = now
            self._last_daily_reset_check = datetime.now(timezone.utc)
            logger.info("Session %s activated", self.session_id)

    def pause(self) -> None:
        """Transition session to PAUSED state."""
        with self._lock:
            if self.state != SessionState.ACTIVE:
                raise RuntimeError("Can only pause an active session")
            self.metadata.state = SessionState.PAUSED.value
            logger.info("Session %s paused", self.session_id)

    def resume(self) -> None:
        """Transition session from PAUSED back to ACTIVE."""
        with self._lock:
            if self.state != SessionState.PAUSED:
                raise RuntimeError("Can only resume a paused session")
            now = datetime.now(timezone.utc).isoformat()
            self.metadata.state = SessionState.ACTIVE.value
            self.metadata.last_activity_at = now
            logger.info("Session %s resumed", self.session_id)

    def reset(self) -> None:
        """
        Reset the session, clearing context and starting fresh.

        Creates a checkpoint before reset, clears the key space,
        and starts a new transcript.
        """
        with self._lock:
            if self.state == SessionState.TERMINATED:
                raise RuntimeError("Cannot reset a terminated session")

            now = datetime.now(timezone.utc)

            if self.config.enable_checkpointing:
                self._create_checkpoint("before_reset")

            self.metadata.state = SessionState.RESETTING.value
            self.metadata.last_reset_at = now.isoformat()
            self.metadata.reset_count += 1
            self.metadata.token_estimate = 0
            self.metadata.message_count = 0

            self.key_space.clear()

            transcript_path = Path(self.metadata.transcript_path or "")
            if transcript_path.exists():
                backup = transcript_path.with_suffix(".jsonl.bak")
                transcript_path.rename(backup)

            self.metadata.state = SessionState.ACTIVE.value
            self.metadata.last_activity_at = now.isoformat()
            logger.info("Session %s reset (count=%d)", self.session_id, self.metadata.reset_count)

    def terminate(self) -> None:
        """Permanently terminate the session."""
        with self._lock:
            if self.state == SessionState.TERMINATED:
                return
            now = datetime.now(timezone.utc).isoformat()
            self.metadata.state = SessionState.TERMINATED.value
            self.metadata.terminated_at = now
            self._release_write_lock()
            logger.info("Session %s terminated", self.session_id)

    def record_activity(self) -> None:
        """Update last activity timestamp."""
        with self._lock:
            self.metadata.last_activity_at = datetime.now(timezone.utc).isoformat()

    def check_daily_reset(self) -> bool:
        """
        Check if the session should be reset due to daily schedule.

        Returns True if a reset was performed, False otherwise.
        """
        with self._lock:
            if self.state != SessionState.ACTIVE:
                return False

            now = datetime.now(timezone.utc)
            if self._last_daily_reset_check is None:
                self._last_daily_reset_check = now
                return False

            last_check = self._last_daily_reset_check
            self._last_daily_reset_check = now

            reset_hour = self.config.daily_reset_hour
            last_reset = self.metadata.last_reset_at

            if last_reset:
                last_reset_dt = datetime.fromisoformat(last_reset)
                if (now - last_reset_dt).total_seconds() < 3600:
                    return False

            if now.hour == reset_hour and last_check.hour != reset_hour:
                logger.info(
                    "Daily reset triggered for session %s at hour %d",
                    self.session_id,
                    reset_hour,
                )
                self.reset()
                return True

            return False

    def check_idle_reset(self) -> bool:
        """
        Check if the session should be reset due to idle timeout.

        Returns True if a reset was performed, False otherwise.
        """
        with self._lock:
            if self.state != SessionState.ACTIVE:
                return False
            if self.config.idle_reset_minutes is None:
                return False

            last_activity = self.metadata.last_activity_at
            if not last_activity:
                return False

            last_dt = datetime.fromisoformat(last_activity)
            idle_seconds = (datetime.now(timezone.utc) - last_dt).total_seconds()
            idle_threshold = self.config.idle_reset_minutes * 60

            if idle_seconds > idle_threshold:
                logger.info(
                    "Idle reset triggered for session %s (idle=%.0f min)",
                    self.session_id,
                    idle_seconds / 60,
                )
                self.reset()
                return True

            return False

    def acquire_write_lock(self, owner: str) -> bool:
        """
        Acquire an exclusive write lock on the session.

        Used during compaction to prevent concurrent writes.

        Args:
            owner: Identifier for the lock owner (e.g., compaction engine).

        Returns:
            True if lock acquired, False if timeout or already locked.
        """
        deadline = time.monotonic() + self.config.lock_timeout_seconds
        while time.monotonic() < deadline:
            with self._lock:
                if not self._write_locked:
                    self._write_locked = True
                    self._write_lock_owner = owner
                    logger.debug("Write lock acquired by %s on session %s", owner, self.session_id)
                    return True
            time.sleep(0.05)

        logger.warning(
            "Write lock timeout for %s on session %s (owner=%s)",
            owner,
            self.session_id,
            self._write_lock_owner,
        )
        return False

    def release_write_lock(self, owner: str) -> None:
        """Release the write lock if owned by the caller."""
        with self._lock:
            if self._write_lock_owner == owner:
                self._write_locked = False
                self._write_lock_owner = None
                logger.debug("Write lock released by %s on session %s", owner, self.session_id)

    def _release_write_lock(self) -> None:
        """Force release the write lock (internal use)."""
        self._write_locked = False
        self._write_lock_owner = None

    def set_key(self, key: str, value: Any) -> None:
        """Set a value in the session's key space."""
        with self._lock:
            self.key_space[key] = value

    def get_key(self, key: str, default: Any = None) -> Any:
        """Get a value from the session's key space."""
        with self._lock:
            return self.key_space.get(key, default)

    def delete_key(self, key: str) -> bool:
        """Delete a key from the session's key space. Returns True if found."""
        with self._lock:
            if key in self.key_space:
                del self.key_space[key]
                return True
            return False

    def get_isolated_key_prefix(self, sub_agent_id: str) -> str:
        """
        Generate an isolated key prefix for a sub-agent.

        Ensures sub-agents cannot access each other's keys.
        """
        mode = self.config.isolation_mode
        parts = ["ks", self.session_id[:8]]

        if mode == SessionIsolationMode.PER_PEER and self.metadata.peer_id:
            parts.append(self.metadata.peer_id)
        elif mode == SessionIsolationMode.PER_CHANNEL_PEER:
            if self.metadata.channel_id:
                parts.append(self.metadata.channel_id)
            if self.metadata.peer_id:
                parts.append(self.metadata.peer_id)
        elif mode == SessionIsolationMode.PER_ACCOUNT_CHANNEL_PEER:
            if self.metadata.account_id:
                parts.append(self.metadata.account_id)
            if self.metadata.channel_id:
                parts.append(self.metadata.channel_id)
            if self.metadata.peer_id:
                parts.append(self.metadata.peer_id)

        parts.append(sub_agent_id)
        return ":".join(parts)

    def _create_checkpoint(self, kind: str) -> Optional[SessionCheckpoint]:
        """
        Create a checkpoint of the current session state.

        Args:
            kind: Checkpoint kind, typically "before_reset" or "after_compaction".

        Returns:
            The created checkpoint, or None if checkpointing is disabled.
        """
        if not self.config.enable_checkpointing:
            return None

        checkpoint_dir = Path(self.config.checkpoint_dir or self._session_dir / "checkpoints")
        checkpoint_dir.mkdir(parents=True, exist_ok=True)

        checkpoint = SessionCheckpoint(
            checkpoint_id=str(uuid.uuid4())[:12],
            session_id=self.session_id,
            timestamp=datetime.now(timezone.utc).isoformat(),
            kind=kind,
            state_snapshot={
                "state": self.metadata.state,
                "key_space": dict(self.key_space),
                "message_count": self.metadata.message_count,
                "token_estimate": self.metadata.token_estimate,
            },
            transcript_head=self.metadata.message_count,
            token_estimate=self.metadata.token_estimate,
        )

        checkpoint_path = checkpoint_dir / f"{checkpoint.checkpoint_id}.json"
        try:
            with open(checkpoint_path, "w") as f:
                json.dump(checkpoint.to_dict(), f, indent=2)
            logger.debug("Checkpoint %s created (%s)", checkpoint.checkpoint_id, kind)
        except OSError as e:
            logger.error("Failed to write checkpoint: %s", e)

        return checkpoint

    def load_checkpoint(self, checkpoint_id: str) -> Optional[SessionCheckpoint]:
        """Load a checkpoint by ID and restore session state."""
        checkpoint_dir = Path(self.config.checkpoint_dir or self._session_dir / "checkpoints")
        checkpoint_path = checkpoint_dir / f"{checkpoint_id}.json"

        if not checkpoint_path.exists():
            return None

        try:
            with open(checkpoint_path) as f:
                data = json.load(f)
            checkpoint = SessionCheckpoint.from_dict(data)

            with self._lock:
                self.key_space.clear()
                self.key_space.update(checkpoint.state_snapshot.get("key_space", {}))
                self.metadata.message_count = checkpoint.transcript_head
                self.metadata.token_estimate = checkpoint.token_estimate

            logger.info("Session %s restored from checkpoint %s", self.session_id, checkpoint_id)
            return checkpoint
        except (OSError, json.JSONDecodeError) as e:
            logger.error("Failed to load checkpoint %s: %s", checkpoint_id, e)
            return None

    def save_metadata(self) -> None:
        """Persist session metadata to disk."""
        metadata_path = self._session_dir / "metadata.json"
        try:
            with open(metadata_path, "w") as f:
                json.dump(self.metadata.to_dict(), f, indent=2)
                f.flush()
                os.fsync(f.fileno())
        except OSError as e:
            logger.error("Failed to save metadata for session %s: %s", self.session_id, e)

    def increment_message_count(self, token_delta: int = 0) -> None:
        """Increment message count and optionally token estimate."""
        with self._lock:
            self.metadata.message_count += 1
            self.metadata.token_estimate += token_delta
            self.metadata.last_activity_at = datetime.now(timezone.utc).isoformat()

    def increment_compaction_count(self) -> None:
        """Increment compaction counter."""
        with self._lock:
            self.metadata.compaction_count += 1

    def to_dict(self) -> Dict[str, Any]:
        """Serialize session to a dictionary."""
        return {
            "session_id": self.session_id,
            "state": self.metadata.state,
            "isolation_mode": self.metadata.isolation_mode,
            "created_at": self.metadata.created_at,
            "last_activity_at": self.metadata.last_activity_at,
            "message_count": self.metadata.message_count,
            "token_estimate": self.metadata.token_estimate,
        }


class SessionRegistry:
    """
    Persistent registry of all sessions with SQLite-backed storage.

    Provides session lookup by various keys (peer, channel, account),
    persistence across restarts, and cleanup of expired sessions.
    """

    _schema = """
    CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        state TEXT NOT NULL,
        isolation_mode TEXT NOT NULL,
        peer_id TEXT,
        channel_id TEXT,
        account_id TEXT,
        created_at TEXT NOT NULL,
        activated_at TEXT,
        last_activity_at TEXT,
        last_reset_at TEXT,
        terminated_at TEXT,
        transcript_path TEXT,
        message_count INTEGER DEFAULT 0,
        token_estimate INTEGER DEFAULT 0,
        reset_count INTEGER DEFAULT 0,
        compaction_count INTEGER DEFAULT 0,
        metadata_json TEXT DEFAULT '{}'
    );
    CREATE INDEX IF NOT EXISTS idx_sessions_peer ON sessions(peer_id);
    CREATE INDEX IF NOT EXISTS idx_sessions_channel ON sessions(channel_id);
    CREATE INDEX IF NOT EXISTS idx_sessions_state ON sessions(state);
    CREATE INDEX IF NOT EXISTS idx_sessions_activity ON sessions(last_activity_at);
    """

    def __init__(self, db_path: str) -> None:
        self.db_path = db_path
        self._lock = threading.Lock()
        self._sessions: Dict[str, Session] = {}
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database and create tables if needed."""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        with sqlite3.connect(self.db_path) as conn:
            conn.executescript(self._schema)
            conn.commit()

    def _connect(self) -> sqlite3.Connection:
        """Create a new database connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def register(self, session: Session) -> None:
        """Register a session in the registry and persist it."""
        with self._lock:
            self._sessions[session.session_id] = session
            self._persist_session(session)

    def _persist_session(self, session: Session) -> None:
        """Persist a single session to the database."""
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO sessions (
                    session_id, state, isolation_mode, peer_id, channel_id,
                    account_id, created_at, activated_at, last_activity_at,
                    last_reset_at, terminated_at, transcript_path,
                    message_count, token_estimate, reset_count,
                    compaction_count, metadata_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    session.session_id,
                    session.metadata.state,
                    session.metadata.isolation_mode,
                    session.metadata.peer_id,
                    session.metadata.channel_id,
                    session.metadata.account_id,
                    session.metadata.created_at,
                    session.metadata.activated_at,
                    session.metadata.last_activity_at,
                    session.metadata.last_reset_at,
                    session.metadata.terminated_at,
                    session.metadata.transcript_path,
                    session.metadata.message_count,
                    session.metadata.token_estimate,
                    session.metadata.reset_count,
                    session.metadata.compaction_count,
                    json.dumps(session.metadata.custom_fields),
                ),
            )
            conn.commit()

    def get(self, session_id: str) -> Optional[Session]:
        """Get a session by ID from the in-memory cache."""
        return self._sessions.get(session_id)

    def find_by_peer(self, peer_id: str) -> List[Session]:
        """Find all sessions for a given peer ID."""
        results = []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT session_id FROM sessions WHERE peer_id = ? AND state != ?",
                (peer_id, SessionState.TERMINATED.value),
            ).fetchall()
        for row in rows:
            session = self._sessions.get(row["session_id"])
            if session:
                results.append(session)
        return results

    def find_by_channel(self, channel_id: str) -> List[Session]:
        """Find all sessions for a given channel ID."""
        results = []
        with self._connect() as conn:
            rows = conn.execute(
                "SELECT session_id FROM sessions WHERE channel_id = ? AND state != ?",
                (channel_id, SessionState.TERMINATED.value),
            ).fetchall()
        for row in rows:
            session = self._sessions.get(row["session_id"])
            if session:
                results.append(session)
        return results

    def find_active(self) -> List[Session]:
        """Get all active sessions."""
        return [
            s for s in self._sessions.values() if s.state == SessionState.ACTIVE
        ]

    def load_from_db(self, session_id: str, config: SessionConfig) -> Optional[Session]:
        """
        Load a session from the database and reconstruct it.

        Args:
            session_id: The session ID to load.
            config: Configuration to apply to the reconstructed session.

        Returns:
            The loaded session, or None if not found.
        """
        with self._connect() as conn:
            row = conn.execute(
                "SELECT * FROM sessions WHERE session_id = ?", (session_id,)
            ).fetchone()

        if not row:
            return None

        session = Session(
            session_id=row["session_id"],
            config=config,
            peer_id=row["peer_id"],
            channel_id=row["channel_id"],
            account_id=row["account_id"],
        )

        session.metadata.state = row["state"]
        session.metadata.isolation_mode = row["isolation_mode"]
        session.metadata.created_at = row["created_at"]
        session.metadata.activated_at = row["activated_at"]
        session.metadata.last_activity_at = row["last_activity_at"]
        session.metadata.last_reset_at = row["last_reset_at"]
        session.metadata.terminated_at = row["terminated_at"]
        session.metadata.transcript_path = row["transcript_path"]
        session.metadata.message_count = row["message_count"]
        session.metadata.token_estimate = row["token_estimate"]
        session.metadata.reset_count = row["reset_count"]
        session.metadata.compaction_count = row["compaction_count"]

        try:
            session.metadata.custom_fields = json.loads(row["metadata_json"] or "{}")
        except json.JSONDecodeError:
            session.metadata.custom_fields = {}

        self._sessions[session_id] = session
        return session

    def remove(self, session_id: str) -> None:
        """Remove a session from the registry and database."""
        with self._lock:
            self._sessions.pop(session_id, None)
            with self._connect() as conn:
                conn.execute("DELETE FROM sessions WHERE session_id = ?", (session_id,))
                conn.commit()

    def cleanup_expired(self, ttl_days: int = 90) -> int:
        """
        Remove terminated sessions older than TTL.

        Args:
            ttl_days: Number of days after which to remove expired sessions.

        Returns:
            Number of sessions removed.
        """
        cutoff = (datetime.now(timezone.utc) - timedelta(days=ttl_days)).isoformat()
        removed = 0

        with self._connect() as conn:
            rows = conn.execute(
                "SELECT session_id FROM sessions WHERE state = ? AND terminated_at < ?",
                (SessionState.TERMINATED.value, cutoff),
            ).fetchall()

            for row in rows:
                sid = row["session_id"]
                self._sessions.pop(sid, None)
                conn.execute("DELETE FROM sessions WHERE session_id = ?", (sid,))
                removed += 1

            conn.commit()

        if removed:
            logger.info("Cleaned up %d expired sessions", removed)
        return removed

    def sync_all(self) -> None:
        """Persist all in-memory sessions to the database."""
        with self._lock:
            for session in self._sessions.values():
                self._persist_session(session)

    def count(self) -> int:
        """Return total number of registered sessions."""
        return len(self._sessions)

    def count_by_state(self, state: SessionState) -> int:
        """Return number of sessions in a given state."""
        return sum(1 for s in self._sessions.values() if s.state == state)


class SessionManager:
    """
    Central manager for session lifecycle operations.

    Coordinates session creation, lookup, reset scheduling, and persistence.
    Acts as the single entry point for all session-related operations.

    Usage:
        manager = SessionManager(config)
        session = manager.create_session(peer_id="user123")
        session.activate()
        ...
        manager.check_resets()
    """

    def __init__(
        self,
        config: Optional[SessionConfig] = None,
        registry_db_path: Optional[str] = None,
    ) -> None:
        self.config = config or SessionConfig()
        db_path = registry_db_path or str(Path.cwd() / "data" / "session_registry.db")
        self.registry = SessionRegistry(db_path)
        self._lock = threading.Lock()
        self._on_session_create: List[Callable[[Session], None]] = []
        self._on_session_terminate: List[Callable[[Session], None]] = []

    def create_session(
        self,
        peer_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        account_id: Optional[str] = None,
        session_id: Optional[str] = None,
    ) -> Session:
        """
        Create a new session with the given parameters.

        Args:
            peer_id: Optional peer identifier for isolation.
            channel_id: Optional channel identifier for isolation.
            account_id: Optional account identifier for isolation.
            session_id: Optional explicit session ID (generated if not provided).

        Returns:
            The newly created session.
        """
        sid = session_id or str(uuid.uuid4())[:16]

        session = Session(
            session_id=sid,
            config=self.config,
            peer_id=peer_id,
            channel_id=channel_id,
            account_id=account_id,
        )

        with self._lock:
            self.registry.register(session)
            session.save_metadata()

        for callback in self._on_session_create:
            try:
                callback(session)
            except Exception:
                logger.exception("Error in session create callback")

        logger.info(
            "Session created: %s (mode=%s, peer=%s, channel=%s)",
            sid,
            self.config.isolation_mode.value,
            peer_id,
            channel_id,
        )
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """Get an existing session by ID."""
        session = self.registry.get(session_id)
        if session:
            return session

        return self.registry.load_from_db(session_id, self.config)

    def get_or_create_session(
        self,
        peer_id: Optional[str] = None,
        channel_id: Optional[str] = None,
        account_id: Optional[str] = None,
    ) -> Session:
        """
        Get an existing session for the given scope, or create a new one.

        Uses the isolation mode to determine the lookup key.
        """
        mode = self.config.isolation_mode

        if mode == SessionIsolationMode.SHARED:
            existing = self.registry.find_active()
            if existing:
                return existing[0]
            return self.create_session()

        if mode == SessionIsolationMode.PER_PEER:
            if peer_id:
                sessions = self.registry.find_by_peer(peer_id)
                active = [s for s in sessions if s.is_active]
                if active:
                    return active[0]
            return self.create_session(peer_id=peer_id)

        if mode == SessionIsolationMode.PER_CHANNEL_PEER:
            if channel_id and peer_id:
                sessions = self.registry.find_by_channel(channel_id)
                active = [s for s in sessions if s.is_active and s.metadata.peer_id == peer_id]
                if active:
                    return active[0]
            return self.create_session(peer_id=peer_id, channel_id=channel_id)

        if mode == SessionIsolationMode.PER_ACCOUNT_CHANNEL_PEER:
            if account_id and channel_id and peer_id:
                sessions = self.registry.find_by_channel(channel_id)
                active = [
                    s for s in sessions
                    if s.is_active
                    and s.metadata.peer_id == peer_id
                    and s.metadata.account_id == account_id
                ]
                if active:
                    return active[0]
            return self.create_session(
                peer_id=peer_id, channel_id=channel_id, account_id=account_id
            )

        return self.create_session(peer_id=peer_id, channel_id=channel_id, account_id=account_id)

    def reset_session(self, session_id: str) -> bool:
        """
        Reset a session by ID.

        Returns True if the session was found and reset, False otherwise.
        """
        session = self.get_session(session_id)
        if not session:
            return False
        try:
            session.reset()
            session.save_metadata()
            self.registry._persist_session(session)
            return True
        except RuntimeError:
            return False

    def terminate_session(self, session_id: str) -> bool:
        """
        Terminate a session by ID.

        Returns True if the session was found and terminated, False otherwise.
        """
        session = self.get_session(session_id)
        if not session:
            return False
        session.terminate()
        session.save_metadata()

        for callback in self._on_session_terminate:
            try:
                callback(session)
            except Exception:
                logger.exception("Error in session terminate callback")

        return True

    def check_resets(self) -> Dict[str, int]:
        """
        Check all active sessions for daily and idle resets.

        Returns:
            Dict with counts of resets performed: {"daily": N, "idle": M}
        """
        daily_count = 0
        idle_count = 0

        for session in self.registry.find_active():
            if session.check_daily_reset():
                daily_count += 1
            elif session.check_idle_reset():
                idle_count += 1

        return {"daily": daily_count, "idle": idle_count}

    def sync(self) -> None:
        """Persist all session state to disk."""
        for session in self.registry.find_active():
            session.save_metadata()
        self.registry.sync_all()

    def cleanup(self, ttl_days: Optional[int] = None) -> int:
        """
        Clean up expired sessions.

        Args:
            ttl_days: Override TTL from config.

        Returns:
            Number of sessions removed.
        """
        ttl = ttl_days or self.config.metadata_ttl_days
        return self.registry.cleanup_expired(ttl)

    def on_session_create(self, callback: Callable[[Session], None]) -> None:
        """Register a callback for session creation events."""
        self._on_session_create.append(callback)

    def on_session_terminate(self, callback: Callable[[Session], None]) -> None:
        """Register a callback for session termination events."""
        self._on_session_terminate.append(callback)

    def get_stats(self) -> Dict[str, Any]:
        """Get current session statistics."""
        return {
            "total": self.registry.count(),
            "active": self.registry.count_by_state(SessionState.ACTIVE),
            "paused": self.registry.count_by_state(SessionState.PAUSED),
            "terminated": self.registry.count_by_state(SessionState.TERMINATED),
            "isolation_mode": self.config.isolation_mode.value,
            "daily_reset_hour": self.config.daily_reset_hour,
            "idle_reset_minutes": self.config.idle_reset_minutes,
        }
