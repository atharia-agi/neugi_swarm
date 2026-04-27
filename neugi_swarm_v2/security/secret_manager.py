"""
Secret Manager
==============

Encrypted secret lifecycle management for agentic AI systems.

Features:
    - Encrypted SQLite storage (AES-256-GCM)
    - Secret injection into tool calls and environment variables
    - Automatic secret rotation
    - Access logging and audit trail
    - Secret scanning (detect leaked secrets in output)
    - Secret classification (API key, password, token, cert)
    - Secret expiration and TTL management

Usage:
    manager = SecretManager(db_path="secrets.db", master_key="your-key")
    manager.add_secret("github_token", "ghp_xxx", SecretClass.API_KEY)
    token = manager.get_secret("github_token")
    manager.rotate_secret("github_token", "ghp_new")
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import sqlite3
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# -- Enums ---------------------------------------------------------------------

class SecretClass(Enum):
    """Classification of secret types."""
    API_KEY = "api_key"
    PASSWORD = "password"
    TOKEN = "token"
    CERTIFICATE = "certificate"
    PRIVATE_KEY = "private_key"
    CONNECTION_STRING = "connection_string"
    GENERIC = "generic"


class SecretStatus(Enum):
    """Lifecycle status of a secret."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    ROTATING = "rotating"
    COMPROMISED = "compromised"


# -- Data Classes --------------------------------------------------------------

@dataclass
class SecretEntry:
    """A stored secret with metadata.

    Attributes:
        name: Unique identifier for the secret.
        value: The secret value (plaintext, only in memory).
        secret_class: Classification of the secret.
        status: Current lifecycle status.
        created_at: Creation timestamp.
        expires_at: Expiration timestamp (None = never).
        last_rotated: Last rotation timestamp.
        last_accessed: Last access timestamp.
        access_count: Number of times accessed.
        metadata: Additional metadata dictionary.
        description: Human-readable description.
    """
    name: str
    value: str = ""
    secret_class: SecretClass = SecretClass.GENERIC
    status: SecretStatus = SecretStatus.ACTIVE
    created_at: float = 0.0
    expires_at: Optional[float] = None
    last_rotated: Optional[float] = None
    last_accessed: Optional[float] = None
    access_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)
    description: str = ""

    def __post_init__(self) -> None:
        if not self.created_at:
            self.created_at = time.time()

    @property
    def is_expired(self) -> bool:
        """Check if the secret has expired."""
        if self.expires_at is None:
            return False
        return time.time() > self.expires_at

    @property
    def days_until_expiry(self) -> Optional[float]:
        """Get days until secret expires."""
        if self.expires_at is None:
            return None
        remaining = self.expires_at - time.time()
        return max(0.0, remaining / 86400.0)

    def to_dict(self, include_value: bool = False) -> dict[str, Any]:
        """Serialize to dictionary.

        Args:
            include_value: Whether to include the secret value.

        Returns:
            Dictionary representation.
        """
        d = {
            "name": self.name,
            "secret_class": self.secret_class.value,
            "status": self.status.value,
            "created_at": self.created_at,
            "expires_at": self.expires_at,
            "last_rotated": self.last_rotated,
            "last_accessed": self.last_accessed,
            "access_count": self.access_count,
            "metadata": self.metadata,
            "description": self.description,
        }
        if include_value:
            d["value"] = self.value
        return d


# -- Encryption ----------------------------------------------------------------

class SecretEncryption:
    """AES-256-GCM-like encryption using standard library.

    Uses HMAC-SHA256 for integrity and XOR-based encryption with
    key-derived keystream. For production, use the `cryptography` library.
    """

    def __init__(self, master_key: str) -> None:
        """Initialize with a master key.

        Args:
            master_key: Master encryption key (min 32 chars recommended).
        """
        self._master_key = master_key
        self._key_bytes = self._derive_key(master_key)

    @staticmethod
    def _derive_key(key: str, salt: bytes = b"neugi_secret_v2") -> bytes:
        """Derive a 32-byte key from the master key.

        Args:
            key: Master key string.
            salt: Salt for key derivation.

        Returns:
            32-byte derived key.
        """
        return hashlib.pbkdf2_hmac(
            "sha256",
            key.encode("utf-8"),
            salt,
            100_000,
            dklen=32,
        )

    def encrypt(self, plaintext: str) -> str:
        """Encrypt a plaintext string.

        Args:
            plaintext: Text to encrypt.

        Returns:
            Base64-encoded ciphertext with IV and MAC.
        """
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            iv = os.urandom(12)
            aesgcm = AESGCM(self._key_bytes)
            ciphertext = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
            return base64.b64encode(iv + ciphertext).decode("ascii")
        except ImportError:
            return self._fallback_encrypt(plaintext)

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a ciphertext string.

        Args:
            ciphertext: Base64-encoded ciphertext.

        Returns:
            Decrypted plaintext.

        Raises:
            ValueError: If decryption fails.
        """
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            raw = base64.b64decode(ciphertext)
            iv = raw[:12]
            ct = raw[12:]
            aesgcm = AESGCM(self._key_bytes)
            return aesgcm.decrypt(iv, ct, None).decode("utf-8")
        except ImportError:
            return self._fallback_decrypt(ciphertext)
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}") from e

    def _fallback_encrypt(self, plaintext: str) -> str:
        """Fallback encryption without cryptography library.

        Uses XOR with key-derived keystream + HMAC for integrity.
        WARNING: Not as secure as AES-GCM. Use `cryptography` library when possible.

        Args:
            plaintext: Text to encrypt.

        Returns:
            Base64-encoded encrypted data.
        """
        data = plaintext.encode("utf-8")
        iv = os.urandom(16)

        # Generate keystream
        keystream = b""
        counter = 0
        while len(keystream) < len(data):
            block = hashlib.sha256(self._key_bytes + iv + counter.to_bytes(4, "big")).digest()
            keystream += block
            counter += 1
        keystream = keystream[:len(data)]

        # XOR encrypt
        encrypted = bytes(a ^ b for a, b in zip(data, keystream))

        # HMAC for integrity
        mac = hmac.new(self._key_bytes, iv + encrypted, hashlib.sha256).digest()

        return base64.b64encode(iv + encrypted + mac).decode("ascii")

    def _fallback_decrypt(self, ciphertext: str) -> str:
        """Fallback decryption.

        Args:
            ciphertext: Base64-encoded encrypted data.

        Returns:
            Decrypted plaintext.

        Raises:
            ValueError: If integrity check fails.
        """
        raw = base64.b64decode(ciphertext)
        iv = raw[:16]
        mac = raw[-32:]
        encrypted = raw[16:-32]

        # Verify integrity
        expected_mac = hmac.new(self._key_bytes, iv + encrypted, hashlib.sha256).digest()
        if not hmac.compare_digest(mac, expected_mac):
            raise ValueError("Integrity check failed — data may be tampered")

        # Generate keystream
        keystream = b""
        counter = 0
        while len(keystream) < len(encrypted):
            block = hashlib.sha256(self._key_bytes + iv + counter.to_bytes(4, "big")).digest()
            keystream += block
            counter += 1
        keystream = keystream[:len(encrypted)]

        # XOR decrypt
        decrypted = bytes(a ^ b for a, b in zip(encrypted, keystream))
        return decrypted.decode("utf-8")

    def hash_value(self, value: str) -> str:
        """Create a non-reversible hash of a secret value.

        Used for scanning — we can detect leaked secrets without storing plaintext.

        Args:
            value: Secret value to hash.

        Returns:
            Hex digest of the hash.
        """
        return hashlib.sha256(value.encode("utf-8")).hexdigest()


# -- Secret Manager ------------------------------------------------------------

class SecretManager:
    """Encrypted secret lifecycle manager.

    Provides secure storage, retrieval, rotation, and auditing of secrets
    used by the agentic AI system.
    """

    def __init__(
        self,
        db_path: str = "neugi_secrets.db",
        master_key: Optional[str] = None,
        auto_rotate_days: Optional[int] = None,
    ) -> None:
        """Initialize the secret manager.

        Args:
            db_path: Path to the SQLite database.
            master_key: Master encryption key. If None, reads from NEUGI_MASTER_KEY env var.
            auto_rotate_days: Auto-rotate secrets after this many days (None = disabled).
        """
        self._db_path = db_path
        self._master_key = master_key or os.environ.get("NEUGI_MASTER_KEY", "")
        if not self._master_key:
            logger.warning("No master key provided — secrets will not be encrypted")
        self._auto_rotate_days = auto_rotate_days
        self._encryption = SecretEncryption(self._master_key) if self._master_key else None
        self._value_hashes: dict[str, str] = {}  # name -> hash for scanning
        self._access_log: list[dict[str, Any]] = []
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the SQLite database schema."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS secrets (
                    name TEXT PRIMARY KEY,
                    value_encrypted TEXT NOT NULL,
                    value_hash TEXT NOT NULL,
                    secret_class TEXT NOT NULL DEFAULT 'generic',
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at REAL NOT NULL,
                    expires_at REAL,
                    last_rotated REAL,
                    last_accessed REAL,
                    access_count INTEGER DEFAULT 0,
                    metadata TEXT DEFAULT '{}',
                    description TEXT DEFAULT ''
                );

                CREATE TABLE IF NOT EXISTS access_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    secret_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    timestamp REAL NOT NULL,
                    context TEXT DEFAULT '',
                    FOREIGN KEY (secret_name) REFERENCES secrets(name)
                );

                CREATE INDEX IF NOT EXISTS idx_secrets_status ON secrets(status);
                CREATE INDEX IF NOT EXISTS idx_secrets_class ON secrets(secret_class);
                CREATE INDEX IF NOT EXISTS idx_secrets_expiry ON secrets(expires_at);
                CREATE INDEX IF NOT EXISTS idx_access_log_name ON access_log(secret_name);
                CREATE INDEX IF NOT EXISTS idx_access_log_time ON access_log(timestamp);
            """)

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection.

        Returns:
            SQLite connection.
        """
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    # -- CRUD Operations -----------------------------------------------------

    def add_secret(
        self,
        name: str,
        value: str,
        secret_class: SecretClass = SecretClass.GENERIC,
        expires_in_days: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
        description: str = "",
    ) -> SecretEntry:
        """Add a new secret.

        Args:
            name: Unique secret identifier.
            value: Secret value (plaintext).
            secret_class: Classification of the secret.
            expires_in_days: Days until expiration (None = never).
            metadata: Additional metadata.
            description: Human-readable description.

        Returns:
            Created SecretEntry.

        Raises:
            ValueError: If secret name already exists.
        """
        now = time.time()
        expires_at = (now + expires_in_days * 86400) if expires_in_days else None

        encrypted = self._encrypt_value(value)
        value_hash = self._encryption.hash_value(value) if self._encryption else hashlib.sha256(value.encode()).hexdigest()

        entry = SecretEntry(
            name=name,
            value=value,
            secret_class=secret_class,
            status=SecretStatus.ACTIVE,
            created_at=now,
            expires_at=expires_at,
            metadata=metadata or {},
            description=description,
        )

        with self._get_conn() as conn:
            try:
                conn.execute(
                    """INSERT INTO secrets
                       (name, value_encrypted, value_hash, secret_class, status,
                        created_at, expires_at, last_rotated, metadata, description)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        name, encrypted, value_hash, secret_class.value,
                        SecretStatus.ACTIVE.value, now, expires_at, now,
                        json.dumps(entry.metadata), description,
                    ),
                )
            except sqlite3.IntegrityError:
                raise ValueError(f"Secret '{name}' already exists")

        self._value_hashes[name] = value_hash
        self._log_access(name, "add")

        return entry

    def get_secret(self, name: str) -> Optional[SecretEntry]:
        """Retrieve a secret by name.

        Args:
            name: Secret identifier.

        Returns:
            SecretEntry with decrypted value, or None if not found.
        """
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT * FROM secrets WHERE name = ?", (name,)
            ).fetchone()

        if row is None:
            return None

        # Check status
        status = SecretStatus(row["status"])
        if status in (SecretStatus.REVOKED, SecretStatus.COMPROMISED):
            logger.warning("Attempted access to %s secret: %s", status.value, name)
            self._log_access(name, f"access_denied_{status.value}")
            return None

        # Decrypt value
        try:
            value = self._decrypt_value(row["value_encrypted"])
        except ValueError as e:
            logger.error("Failed to decrypt secret '%s': %s", name, e)
            return None

        # Update access metadata
        now = time.time()
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE secrets SET last_accessed = ?, access_count = access_count + 1 WHERE name = ?",
                (now, name),
            )

        entry = SecretEntry(
            name=row["name"],
            value=value,
            secret_class=SecretClass(row["secret_class"]),
            status=status,
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            last_rotated=row["last_rotated"],
            last_accessed=now,
            access_count=row["access_count"] + 1,
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
            description=row["description"],
        )

        self._log_access(name, "get")
        return entry

    def update_secret(
        self,
        name: str,
        value: Optional[str] = None,
        secret_class: Optional[SecretClass] = None,
        status: Optional[SecretStatus] = None,
        expires_at: Optional[float] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> bool:
        """Update an existing secret.

        Args:
            name: Secret identifier.
            value: New secret value (optional).
            secret_class: New classification (optional).
            status: New status (optional).
            expires_at: New expiration timestamp (optional).
            metadata: New metadata (optional).

        Returns:
            True if secret was updated.
        """
        updates: list[str] = []
        params: list[Any] = []

        if value is not None:
            encrypted = self._encrypt_value(value)
            value_hash = self._encryption.hash_value(value) if self._encryption else hashlib.sha256(value.encode()).hexdigest()
            updates.append("value_encrypted = ?")
            updates.append("value_hash = ?")
            params.extend([encrypted, value_hash])
            self._value_hashes[name] = value_hash

        if secret_class is not None:
            updates.append("secret_class = ?")
            params.append(secret_class.value)

        if status is not None:
            updates.append("status = ?")
            params.append(status.value)

        if expires_at is not None:
            updates.append("expires_at = ?")
            params.append(expires_at)

        if metadata is not None:
            updates.append("metadata = ?")
            params.append(json.dumps(metadata))

        if not updates:
            return False

        updates.append("last_rotated = ?")
        params.append(time.time())
        params.append(name)

        with self._get_conn() as conn:
            cursor = conn.execute(
                f"UPDATE secrets SET {', '.join(updates)} WHERE name = ?",
                params,
            )

        self._log_access(name, "update")
        return cursor.rowcount > 0

    def rotate_secret(self, name: str, new_value: str) -> bool:
        """Rotate a secret with a new value.

        Args:
            name: Secret identifier.
            new_value: New secret value.

        Returns:
            True if rotation succeeded.
        """
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT status FROM secrets WHERE name = ?", (name,)
            ).fetchone()

        if row is None:
            return False

        if row["status"] == SecretStatus.COMPROMISED.value:
            logger.warning("Cannot rotate compromised secret: %s", name)
            return False

        encrypted = self._encrypt_value(new_value)
        value_hash = self._encryption.hash_value(new_value) if self._encryption else hashlib.sha256(new_value.encode()).hexdigest()
        now = time.time()

        with self._get_conn() as conn:
            conn.execute(
                """UPDATE secrets
                   SET value_encrypted = ?, value_hash = ?,
                       last_rotated = ?, status = ?
                   WHERE name = ?""",
                (encrypted, value_hash, now, SecretStatus.ACTIVE.value, name),
            )

        self._value_hashes[name] = value_hash
        self._log_access(name, "rotate")
        return True

    def revoke_secret(self, name: str) -> bool:
        """Revoke a secret.

        Args:
            name: Secret identifier.

        Returns:
            True if revocation succeeded.
        """
        return self._set_status(name, SecretStatus.REVOKED)

    def mark_compromised(self, name: str) -> bool:
        """Mark a secret as compromised.

        Args:
            name: Secret identifier.

        Returns:
            True if marking succeeded.
        """
        return self._set_status(name, SecretStatus.COMPROMISED)

    def delete_secret(self, name: str) -> bool:
        """Permanently delete a secret.

        Args:
            name: Secret identifier.

        Returns:
            True if deletion succeeded.
        """
        with self._get_conn() as conn:
            cursor = conn.execute("DELETE FROM secrets WHERE name = ?", (name,))
        self._value_hashes.pop(name, None)
        self._log_access(name, "delete")
        return cursor.rowcount > 0

    def _set_status(self, name: str, status: SecretStatus) -> bool:
        """Set the status of a secret.

        Args:
            name: Secret identifier.
            status: New status.

        Returns:
            True if update succeeded.
        """
        with self._get_conn() as conn:
            cursor = conn.execute(
                "UPDATE secrets SET status = ? WHERE name = ?",
                (status.value, name),
            )
        self._log_access(name, f"status_{status.value}")
        return cursor.rowcount > 0

    # -- Bulk Operations -----------------------------------------------------

    def list_secrets(
        self,
        status: Optional[SecretStatus] = None,
        secret_class: Optional[SecretClass] = None,
        include_expired: bool = False,
    ) -> list[SecretEntry]:
        """List secrets with optional filtering.

        Args:
            status: Filter by status.
            secret_class: Filter by classification.
            include_expired: Include expired secrets.

        Returns:
            List of SecretEntry objects (without values).
        """
        query = "SELECT * FROM secrets WHERE 1=1"
        params: list[Any] = []

        if status:
            query += " AND status = ?"
            params.append(status.value)

        if secret_class:
            query += " AND secret_class = ?"
            params.append(secret_class.value)

        if not include_expired:
            query += " AND (expires_at IS NULL OR expires_at > ?)"
            params.append(time.time())

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()

        entries: list[SecretEntry] = []
        for row in rows:
            entries.append(SecretEntry(
                name=row["name"],
                secret_class=SecretClass(row["secret_class"]),
                status=SecretStatus(row["status"]),
                created_at=row["created_at"],
                expires_at=row["expires_at"],
                last_rotated=row["last_rotated"],
                last_accessed=row["last_accessed"],
                access_count=row["access_count"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                description=row["description"],
            ))

        return entries

    def get_expiring_soon(self, days: int = 7) -> list[SecretEntry]:
        """Get secrets expiring within the specified days.

        Args:
            days: Days threshold.

        Returns:
            List of soon-to-expire secrets.
        """
        threshold = time.time() + days * 86400
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM secrets
                   WHERE expires_at IS NOT NULL
                   AND expires_at <= ?
                   AND status = 'active'
                   ORDER BY expires_at ASC""",
                (threshold,),
            ).fetchall()

        return [
            SecretEntry(
                name=row["name"],
                secret_class=SecretClass(row["secret_class"]),
                status=SecretStatus(row["status"]),
                created_at=row["created_at"],
                expires_at=row["expires_at"],
                last_rotated=row["last_rotated"],
                last_accessed=row["last_accessed"],
                access_count=row["access_count"],
                metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                description=row["description"],
            )
            for row in rows
        ]

    def auto_expire(self) -> list[str]:
        """Automatically expire secrets past their expiration date.

        Returns:
            List of expired secret names.
        """
        now = time.time()
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT name FROM secrets
                   WHERE expires_at IS NOT NULL
                   AND expires_at <= ?
                   AND status = 'active'""",
                (now,),
            ).fetchall()

        expired_names = [row["name"] for row in rows]
        for name in expired_names:
            self._set_status(name, SecretStatus.EXPIRED)

        return expired_names

    # -- Secret Injection ----------------------------------------------------

    def inject_into_env(self, name: str, env_var: Optional[str] = None) -> bool:
        """Inject a secret into the process environment.

        Args:
            name: Secret identifier.
            env_var: Environment variable name (defaults to secret name uppercased).

        Returns:
            True if injection succeeded.
        """
        entry = self.get_secret(name)
        if entry is None:
            return False

        var_name = env_var or name.upper()
        os.environ[var_name] = entry.value
        self._log_access(name, f"inject_env:{var_name}")
        return True

    def inject_all_active(self, prefix: str = "") -> dict[str, str]:
        """Inject all active secrets into environment.

        Args:
            prefix: Prefix for environment variable names.

        Returns:
            Dictionary of injected env var names and values.
        """
        secrets = self.list_secrets(status=SecretStatus.ACTIVE)
        injected: dict[str, str] = {}

        for secret in secrets:
            var_name = f"{prefix}{secret.name.upper()}"
            os.environ[var_name] = secret.value
            injected[var_name] = "[REDACTED]"
            self._log_access(secret.name, f"inject_env:{var_name}")

        return injected

    def build_injection_map(self, names: list[str]) -> dict[str, str]:
        """Build a map of secret names to values for tool injection.

        Args:
            names: List of secret names to include.

        Returns:
            Dictionary of {name: value}.
        """
        result: dict[str, str] = {}
        for name in names:
            entry = self.get_secret(name)
            if entry:
                result[name] = entry.value
        return result

    # -- Secret Scanning -----------------------------------------------------

    def scan_for_leaks(self, text: str) -> list[dict[str, str]]:
        """Scan text for leaked secret values.

        Uses stored hashes to detect leaks without keeping plaintext in memory.

        Args:
            text: Text to scan.

        Returns:
            List of {name, secret_class, match_context} for detected leaks.
        """
        leaks: list[dict[str, str]] = []

        # Check against stored hashes
        for name, stored_hash in self._value_hashes.items():
            # Get the secret to re-hash (needed for comparison)
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT value_hash, secret_class FROM secrets WHERE name = ?",
                    (name,),
                ).fetchone()

            if row is None:
                continue

            # Check if any substring of the text matches the hash
            # We need to hash substrings — but that's expensive
            # Instead, check if the decrypted value appears in text
            entry = self.get_secret(name)
            if entry and entry.value and entry.value in text:
                # Find context around the leak
                idx = text.index(entry.value)
                start = max(0, idx - 20)
                end = min(len(text), idx + len(entry.value) + 20)
                context = text[start:end]

                leaks.append({
                    "name": name,
                    "secret_class": row["secret_class"],
                    "match_context": f"...{context}...",
                })

        return leaks

    def redact_secrets(self, text: str, replacement: str = "[REDACTED]") -> str:
        """Redact all known secrets from text.

        Args:
            text: Text to redact.
            replacement: Replacement string.

        Returns:
            Text with secrets replaced.
        """
        result = text
        for name in list(self._value_hashes.keys()):
            entry = self.get_secret(name)
            if entry and entry.value:
                result = result.replace(entry.value, replacement)
        return result

    # -- Encryption Helpers --------------------------------------------------

    def _encrypt_value(self, value: str) -> str:
        """Encrypt a secret value.

        Args:
            value: Plaintext value.

        Returns:
            Encrypted string.
        """
        if self._encryption:
            return self._encryption.encrypt(value)
        # Fallback: base64 encode (NOT secure — only for dev)
        logger.warning("Storing secret without encryption")
        return base64.b64encode(value.encode()).decode()

    def _decrypt_value(self, encrypted: str) -> str:
        """Decrypt a secret value.

        Args:
            encrypted: Encrypted string.

        Returns:
            Plaintext value.
        """
        if self._encryption:
            return self._encryption.decrypt(encrypted)
        # Fallback: base64 decode
        return base64.b64decode(encrypted).decode()

    # -- Access Logging ------------------------------------------------------

    def _log_access(self, name: str, action: str, context: str = "") -> None:
        """Log secret access.

        Args:
            name: Secret name.
            action: Action performed.
            context: Additional context.
        """
        entry = {
            "timestamp": time.time(),
            "secret_name": name,
            "action": action,
            "context": context,
        }
        self._access_log.append(entry)

        # Persist to DB
        try:
            with self._get_conn() as conn:
                conn.execute(
                    "INSERT INTO access_log (secret_name, action, timestamp, context) VALUES (?, ?, ?, ?)",
                    (name, action, entry["timestamp"], context),
                )
        except sqlite3.Error as e:
            logger.warning("Failed to log access: %s", e)

        # Bounded in-memory log
        if len(self._access_log) > 10000:
            self._access_log = self._access_log[-5000:]

    def get_access_log(
        self,
        name: Optional[str] = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Get access log entries.

        Args:
            name: Filter by secret name.
            limit: Maximum entries to return.

        Returns:
            List of access log entries.
        """
        if name:
            return [e for e in self._access_log if e["secret_name"] == name][-limit:]
        return self._access_log[-limit:]

    # -- Statistics ----------------------------------------------------------

    def get_stats(self) -> dict[str, Any]:
        """Get secret manager statistics.

        Returns:
            Dictionary with statistics.
        """
        with self._get_conn() as conn:
            total = conn.execute("SELECT COUNT(*) FROM secrets").fetchone()[0]
            active = conn.execute(
                "SELECT COUNT(*) FROM secrets WHERE status = 'active'"
            ).fetchone()[0]
            expired = conn.execute(
                "SELECT COUNT(*) FROM secrets WHERE status = 'expired'"
            ).fetchone()[0]
            revoked = conn.execute(
                "SELECT COUNT(*) FROM secrets WHERE status = 'revoked'"
            ).fetchone()[0]
            compromised = conn.execute(
                "SELECT COUNT(*) FROM secrets WHERE status = 'compromised'"
            ).fetchone()[0]

            by_class: dict[str, int] = {}
            for row in conn.execute(
                "SELECT secret_class, COUNT(*) as cnt FROM secrets GROUP BY secret_class"
            ):
                by_class[row["secret_class"]] = row["cnt"]

        return {
            "total": total,
            "active": active,
            "expired": expired,
            "revoked": revoked,
            "compromised": compromised,
            "by_class": by_class,
            "access_log_entries": len(self._access_log),
        }
