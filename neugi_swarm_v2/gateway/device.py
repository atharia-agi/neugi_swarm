"""
NEUGI v2 Device Management
===========================

Handles device registration, identity, trust levels, capabilities negotiation,
session tracking, and revocation.

Devices are the primary identity unit — each connecting client registers as
a device and receives a token for subsequent connections.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# -- Enums -------------------------------------------------------------------

class DeviceTrustLevel(str, Enum):
    """Device trust level determines access and auto-approval behavior."""
    TRUSTED = "trusted"
    PENDING = "pending"
    BLOCKED = "blocked"


class DeviceState(str, Enum):
    """Current operational state of a device."""
    ONLINE = "online"
    OFFLINE = "offline"
    SUSPECTED = "suspected"


# -- Data Classes ------------------------------------------------------------

@dataclass
class DeviceCapabilities:
    """Negotiated capabilities for a device.

    Attributes:
        supports_websocket: Device supports WebSocket connections.
        supports_rest: Device supports REST API calls.
        supports_streaming: Device supports streaming responses.
        max_message_size: Maximum message size in bytes the device can handle.
        supported_protocols: List of protocol versions the device understands.
        platform: Device platform (e.g., 'desktop', 'mobile', 'server').
        version: Client software version.
    """
    supports_websocket: bool = True
    supports_rest: bool = True
    supports_streaming: bool = False
    max_message_size: int = 1_048_576  # 1MB default
    supported_protocols: list[str] = field(default_factory=lambda: ["v2.0"])
    platform: str = "unknown"
    version: str = "0.0.0"

    def to_dict(self) -> dict[str, Any]:
        """Serialize capabilities to a dictionary."""
        return {
            "supports_websocket": self.supports_websocket,
            "supports_rest": self.supports_rest,
            "supports_streaming": self.supports_streaming,
            "max_message_size": self.max_message_size,
            "supported_protocols": self.supported_protocols,
            "platform": self.platform,
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DeviceCapabilities:
        """Deserialize capabilities from a dictionary."""
        return cls(
            supports_websocket=data.get("supports_websocket", True),
            supports_rest=data.get("supports_rest", True),
            supports_streaming=data.get("supports_streaming", False),
            max_message_size=data.get("max_message_size", 1_048_576),
            supported_protocols=data.get("supported_protocols", ["v2.0"]),
            platform=data.get("platform", "unknown"),
            version=data.get("version", "0.0.0"),
        )


@dataclass
class Device:
    """Represents a registered device.

    Attributes:
        device_id: Unique device identifier (UUID).
        device_name: Human-readable device name.
        trust_level: Current trust level.
        state: Current operational state.
        capabilities: Negotiated device capabilities.
        token_hash: SHA-256 hash of the device token (never store plaintext).
        created_at: Unix timestamp of registration.
        last_seen_at: Unix timestamp of last connection.
        metadata: Arbitrary device metadata.
    """
    device_id: str
    device_name: str
    trust_level: DeviceTrustLevel = DeviceTrustLevel.PENDING
    state: DeviceState = DeviceState.OFFLINE
    capabilities: DeviceCapabilities = field(default_factory=DeviceCapabilities)
    token_hash: str = ""
    created_at: float = 0.0
    last_seen_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize device to a dictionary (excludes token_hash)."""
        return {
            "device_id": self.device_id,
            "device_name": self.device_name,
            "trust_level": self.trust_level.value,
            "state": self.state.value,
            "capabilities": self.capabilities.to_dict(),
            "created_at": self.created_at,
            "last_seen_at": self.last_seen_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Device:
        """Deserialize device from a dictionary."""
        caps = DeviceCapabilities.from_dict(data.get("capabilities", {}))
        return cls(
            device_id=data["device_id"],
            device_name=data["device_name"],
            trust_level=DeviceTrustLevel(data.get("trust_level", "pending")),
            state=DeviceState(data.get("state", "offline")),
            capabilities=caps,
            token_hash=data.get("token_hash", ""),
            created_at=data.get("created_at", 0.0),
            last_seen_at=data.get("last_seen_at", 0.0),
            metadata=data.get("metadata", {}),
        )


@dataclass
class DeviceSession:
    """Active session for a connected device.

    Attributes:
        session_id: Unique session identifier.
        device_id: Associated device ID.
        connected_at: Unix timestamp of connection.
        last_activity: Unix timestamp of last activity.
        remote_addr: Remote address of the connection.
        is_loopback: Whether connection is from loopback.
        message_count: Number of messages exchanged in this session.
    """
    session_id: str
    device_id: str
    connected_at: float = 0.0
    last_activity: float = 0.0
    remote_addr: str = ""
    is_loopback: bool = False
    message_count: int = 0

    def touch(self) -> None:
        """Update last activity timestamp."""
        self.last_activity = time.time()


# -- Exceptions --------------------------------------------------------------

class DeviceError(Exception):
    """Base exception for device management errors."""

    def __init__(self, message: str, device_id: str | None = None) -> None:
        self.device_id = device_id
        super().__init__(message)


class DeviceNotFoundError(DeviceError):
    """Raised when a device is not found."""
    pass


class DeviceBlockedError(DeviceError):
    """Raised when a blocked device attempts to connect."""
    pass


class DeviceTokenError(DeviceError):
    """Raised when device token validation fails."""
    pass


class DeviceAlreadyRegisteredError(DeviceError):
    """Raised when attempting to register a duplicate device name."""
    pass


# -- Device Manager ----------------------------------------------------------

class DeviceManager:
    """Manages device registration, authentication, and lifecycle.

    Provides device-based identity with signed challenge nonces for pairing,
    trust level management, session tracking, and device revocation.

    All operations are thread-safe via a reentrant lock.

    Attributes:
        db_path: Path to the SQLite database file.
        server_id: Unique server identity for challenge signing.
        _lock: Reentrant lock for thread safety.
        _active_sessions: In-memory map of session_id -> DeviceSession.
    """

    def __init__(self, db_path: str | Path, server_id: str | None = None) -> None:
        """Initialize the device manager.

        Args:
            db_path: Path to SQLite database for device persistence.
            server_id: Unique server identity. Auto-generated if None.
        """
        self.db_path = str(db_path)
        self.server_id = server_id or str(uuid.uuid4())
        self._lock = threading.RLock()
        self._active_sessions: dict[str, DeviceSession] = {}
        self._init_db()
        logger.info("DeviceManager initialized with server_id=%s", self.server_id[:8])

    def _init_db(self) -> None:
        """Initialize the SQLite database schema."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS devices (
                    device_id TEXT PRIMARY KEY,
                    device_name TEXT UNIQUE NOT NULL,
                    trust_level TEXT NOT NULL DEFAULT 'pending',
                    state TEXT NOT NULL DEFAULT 'offline',
                    token_hash TEXT NOT NULL DEFAULT '',
                    capabilities TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    last_seen_at REAL NOT NULL DEFAULT 0,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS device_sessions (
                    session_id TEXT PRIMARY KEY,
                    device_id TEXT NOT NULL REFERENCES devices(device_id),
                    connected_at REAL NOT NULL,
                    last_activity REAL NOT NULL,
                    remote_addr TEXT NOT NULL DEFAULT '',
                    is_loopback INTEGER NOT NULL DEFAULT 0,
                    message_count INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_sessions_device
                    ON device_sessions(device_id);

                CREATE TABLE IF NOT EXISTS challenge_nonces (
                    nonce TEXT PRIMARY KEY,
                    device_id TEXT,
                    expires_at REAL NOT NULL,
                    used INTEGER NOT NULL DEFAULT 0
                );
            """)

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # -- Registration & Pairing ----------------------------------------------

    def register_device(
        self,
        device_name: str,
        capabilities: DeviceCapabilities | None = None,
        trust_level: DeviceTrustLevel = DeviceTrustLevel.PENDING,
        metadata: dict[str, Any] | None = None,
    ) -> tuple[Device, str]:
        """Register a new device and return the device plus its plaintext token.

        The token is returned ONLY at registration time. It is hashed and
        never stored in plaintext.

        Args:
            device_name: Human-readable name for the device.
            capabilities: Device capabilities to negotiate.
            trust_level: Initial trust level (default: pending).
            metadata: Optional metadata to attach.

        Returns:
            Tuple of (Device, plaintext_token).

        Raises:
            DeviceAlreadyRegisteredError: If device_name already exists.
        """
        capabilities = capabilities or DeviceCapabilities()
        metadata = metadata or {}

        device_id = str(uuid.uuid4())
        token = secrets.token_hex(32)
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        now = time.time()

        with self._lock:
            with self._get_conn() as conn:
                try:
                    conn.execute(
                        """INSERT INTO devices
                           (device_id, device_name, trust_level, state, token_hash,
                            capabilities, created_at, last_seen_at, metadata)
                           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                        (
                            device_id, device_name, trust_level.value,
                            DeviceState.OFFLINE.value, token_hash,
                            json.dumps(capabilities.to_dict()),
                            now, now, json.dumps(metadata),
                        ),
                    )
                except sqlite3.IntegrityError as e:
                    if "UNIQUE" in str(e):
                        raise DeviceAlreadyRegisteredError(
                            f"Device name '{device_name}' already registered",
                            device_name,
                        )
                    raise

        device = Device(
            device_id=device_id,
            device_name=device_name,
            trust_level=trust_level,
            state=DeviceState.OFFLINE,
            capabilities=capabilities,
            token_hash=token_hash,
            created_at=now,
            last_seen_at=now,
            metadata=metadata,
        )

        logger.info("Device registered: %s (%s)", device_name, device_id[:8])
        return device, token

    def generate_challenge_nonce(self, device_id: str | None = None, ttl_seconds: float = 300.0) -> str:
        """Generate a signed challenge nonce for device pairing.

        Args:
            device_id: Optional device ID to bind the nonce to.
            ttl_seconds: Time-to-live for the nonce in seconds.

        Returns:
            The challenge nonce string.
        """
        nonce = secrets.token_hex(16)
        expires_at = time.time() + ttl_seconds

        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO challenge_nonces (nonce, device_id, expires_at) VALUES (?, ?, ?)",
                    (nonce, device_id, expires_at),
                )

        return nonce

    def verify_challenge(self, nonce: str, signature: str, device_id: str | None = None) -> bool:
        """Verify a signed challenge nonce.

        The signature should be HMAC-SHA256(nonce, server_id).

        Args:
            nonce: The challenge nonce to verify.
            signature: HMAC signature to verify against.
            device_id: Optional device ID the nonce was bound to.

        Returns:
            True if the challenge is valid and unused.
        """
        with self._lock:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM challenge_nonces WHERE nonce = ? AND used = 0",
                    (nonce,),
                ).fetchone()

                if row is None:
                    return False

                if time.time() > row["expires_at"]:
                    return False

                if device_id and row["device_id"] and row["device_id"] != device_id:
                    return False

                expected = hmac.new(
                    self.server_id.encode(), nonce.encode(), hashlib.sha256
                ).hexdigest()

                if not hmac.compare_digest(signature, expected):
                    return False

                conn.execute(
                    "UPDATE challenge_nonces SET used = 1 WHERE nonce = ?",
                    (nonce,),
                )

                return True

    # -- Authentication ------------------------------------------------------

    def authenticate(self, device_id: str, token: str) -> Device:
        """Authenticate a device by ID and token.

        Args:
            device_id: The device identifier.
            token: The plaintext device token.

        Returns:
            The authenticated Device object.

        Raises:
            DeviceNotFoundError: If device_id does not exist.
            DeviceTokenError: If token does not match.
            DeviceBlockedError: If device is blocked.
        """
        token_hash = hashlib.sha256(token.encode()).hexdigest()

        with self._lock:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM devices WHERE device_id = ?",
                    (device_id,),
                ).fetchone()

                if row is None:
                    raise DeviceNotFoundError(
                        f"Device '{device_id}' not found", device_id
                    )

                if not hmac.compare_digest(row["token_hash"], token_hash):
                    raise DeviceTokenError(
                        f"Invalid token for device '{device_id}'", device_id
                    )

                if row["trust_level"] == DeviceTrustLevel.BLOCKED.value:
                    raise DeviceBlockedError(
                        f"Device '{device_id}' is blocked", device_id
                    )

                device = self._row_to_device(row)
                return device

    # -- Session Management --------------------------------------------------

    def create_session(
        self,
        device_id: str,
        remote_addr: str = "",
    ) -> DeviceSession:
        """Create a new active session for a device.

        Args:
            device_id: The device to create a session for.
            remote_addr: Remote address of the connection.

        Returns:
            The created DeviceSession.

        Raises:
            DeviceNotFoundError: If device_id does not exist.
        """
        is_loopback = remote_addr in ("127.0.0.1", "::1", "localhost", "")
        session_id = str(uuid.uuid4())
        now = time.time()

        session = DeviceSession(
            session_id=session_id,
            device_id=device_id,
            connected_at=now,
            last_activity=now,
            remote_addr=remote_addr,
            is_loopback=is_loopback,
        )

        with self._lock:
            with self._get_conn() as conn:
                device = conn.execute(
                    "SELECT * FROM devices WHERE device_id = ?",
                    (device_id,),
                ).fetchone()

                if device is None:
                    raise DeviceNotFoundError(
                        f"Device '{device_id}' not found", device_id
                    )

                conn.execute(
                    """INSERT INTO device_sessions
                       (session_id, device_id, connected_at, last_activity,
                        remote_addr, is_loopback)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (
                        session_id, device_id, now, now,
                        remote_addr, int(is_loopback),
                    ),
                )

                conn.execute(
                    "UPDATE devices SET state = ?, last_seen_at = ? WHERE device_id = ?",
                    (DeviceState.ONLINE.value, now, device_id),
                )

            self._active_sessions[session_id] = session

        logger.debug(
            "Session created: %s for device %s (loopback=%s)",
            session_id[:8], device_id[:8], is_loopback,
        )
        return session

    def close_session(self, session_id: str) -> None:
        """Close an active session.

        Args:
            session_id: The session to close.
        """
        with self._lock:
            session = self._active_sessions.pop(session_id, None)
            if session is None:
                return

            with self._get_conn() as conn:
                conn.execute(
                    "DELETE FROM device_sessions WHERE session_id = ?",
                    (session_id,),
                )

                remaining = conn.execute(
                    "SELECT COUNT(*) as cnt FROM device_sessions WHERE device_id = ?",
                    (session.device_id,),
                ).fetchone()["cnt"]

                if remaining == 0:
                    conn.execute(
                        "UPDATE devices SET state = ? WHERE device_id = ?",
                        (DeviceState.OFFLINE.value, session.device_id),
                    )

        logger.debug("Session closed: %s", session_id[:8])

    def touch_session(self, session_id: str) -> None:
        """Update last activity timestamp for a session.

        Args:
            session_id: The session to touch.
        """
        with self._lock:
            session = self._active_sessions.get(session_id)
            if session is None:
                return

            session.touch()
            session.message_count += 1

            with self._get_conn() as conn:
                conn.execute(
                    """UPDATE device_sessions
                       SET last_activity = ?, message_count = ?
                       WHERE session_id = ?""",
                    (session.last_activity, session.message_count, session_id),
                )

    def get_session(self, session_id: str) -> DeviceSession | None:
        """Get an active session by ID.

        Args:
            session_id: The session ID to look up.

        Returns:
            The DeviceSession or None if not found.
        """
        return self._active_sessions.get(session_id)

    def get_device_sessions(self, device_id: str) -> list[DeviceSession]:
        """Get all active sessions for a device.

        Args:
            device_id: The device to query sessions for.

        Returns:
            List of active DeviceSession objects.
        """
        with self._lock:
            return [
                s for s in self._active_sessions.values()
                if s.device_id == device_id
            ]

    # -- Device CRUD ---------------------------------------------------------

    def get_device(self, device_id: str) -> Device:
        """Get a device by ID.

        Args:
            device_id: The device identifier.

        Returns:
            The Device object.

        Raises:
            DeviceNotFoundError: If not found.
        """
        with self._lock:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM devices WHERE device_id = ?",
                    (device_id,),
                ).fetchone()

                if row is None:
                    raise DeviceNotFoundError(
                        f"Device '{device_id}' not found", device_id
                    )

                return self._row_to_device(row)

    def list_devices(
        self,
        trust_level: DeviceTrustLevel | None = None,
        state: DeviceState | None = None,
    ) -> list[Device]:
        """List devices with optional filtering.

        Args:
            trust_level: Filter by trust level.
            state: Filter by operational state.

        Returns:
            List of matching Device objects.
        """
        query = "SELECT * FROM devices WHERE 1=1"
        params: list[Any] = []

        if trust_level:
            query += " AND trust_level = ?"
            params.append(trust_level.value)
        if state:
            query += " AND state = ?"
            params.append(state.value)

        with self._lock:
            with self._get_conn() as conn:
                rows = conn.execute(query, params).fetchall()
                return [self._row_to_device(row) for row in rows]

    def update_trust_level(
        self,
        device_id: str,
        trust_level: DeviceTrustLevel,
    ) -> Device:
        """Update a device's trust level.

        Args:
            device_id: The device to update.
            trust_level: New trust level.

        Returns:
            The updated Device.

        Raises:
            DeviceNotFoundError: If not found.
        """
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE devices SET trust_level = ? WHERE device_id = ?",
                    (trust_level.value, device_id),
                )

            return self.get_device(device_id)

    def revoke_device(self, device_id: str) -> None:
        """Revoke a device — close all sessions and block it.

        Args:
            device_id: The device to revoke.

        Raises:
            DeviceNotFoundError: If not found.
        """
        with self._lock:
            sessions = self.get_device_sessions(device_id)
            for session in sessions:
                self.close_session(session.session_id)

            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE devices SET trust_level = ?, state = ? WHERE device_id = ?",
                    (DeviceTrustLevel.BLOCKED.value, DeviceState.OFFLINE.value, device_id),
                )

            logger.info("Device revoked: %s", device_id[:8])

    def delete_device(self, device_id: str) -> None:
        """Permanently delete a device and all its data.

        Args:
            device_id: The device to delete.

        Raises:
            DeviceNotFoundError: If not found.
        """
        with self._lock:
            sessions = self.get_device_sessions(device_id)
            for session in sessions:
                self.close_session(session.session_id)

            with self._get_conn() as conn:
                result = conn.execute(
                    "DELETE FROM devices WHERE device_id = ?",
                    (device_id,),
                )
                if result.rowcount == 0:
                    raise DeviceNotFoundError(
                        f"Device '{device_id}' not found", device_id
                    )

                conn.execute(
                    "DELETE FROM device_sessions WHERE device_id = ?",
                    (device_id,),
                )

            logger.info("Device deleted: %s", device_id[:8])

    # -- Utility -------------------------------------------------------------

    def is_loopback_session(self, session_id: str) -> bool:
        """Check if a session is from loopback.

        Args:
            session_id: The session to check.

        Returns:
            True if the session is from a loopback address.
        """
        session = self._active_sessions.get(session_id)
        return session.is_loopback if session else False

    def get_active_session_count(self) -> int:
        """Get the number of active sessions.

        Returns:
            Count of currently active sessions.
        """
        return len(self._active_sessions)

    def cleanup_expired_sessions(self, timeout_seconds: float = 3600.0) -> int:
        """Close sessions that have been idle beyond the timeout.

        Args:
            timeout_seconds: Seconds of idle before a session is expired.

        Returns:
            Number of sessions cleaned up.
        """
        now = time.time()
        expired: list[str] = []

        with self._lock:
            for sid, session in self._active_sessions.items():
                if now - session.last_activity > timeout_seconds:
                    expired.append(sid)

            for sid in expired:
                self.close_session(sid)

        if expired:
            logger.info("Cleaned up %d expired sessions", len(expired))

        return len(expired)

    def close(self) -> None:
        """Close all active sessions and shut down the device manager."""
        with self._lock:
            session_ids = list(self._active_sessions.keys())

        for sid in session_ids:
            self.close_session(sid)

        logger.info("DeviceManager shut down")

    # -- Internal ------------------------------------------------------------

    def _row_to_device(self, row: sqlite3.Row) -> Device:
        """Convert a database row to a Device object."""
        return Device(
            device_id=row["device_id"],
            device_name=row["device_name"],
            trust_level=DeviceTrustLevel(row["trust_level"]),
            state=DeviceState(row["state"]),
            capabilities=DeviceCapabilities.from_dict(
                json.loads(row["capabilities"])
            ),
            token_hash=row["token_hash"],
            created_at=row["created_at"],
            last_seen_at=row["last_seen_at"],
            metadata=json.loads(row["metadata"]),
        )
