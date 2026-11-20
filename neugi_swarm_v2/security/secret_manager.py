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
from typing import Any

logger = logging.getLogger(__name__)


# -- Enums ---------------------------------------------------------------------

# -- Exceptions ----------------------------------------------------------------


class SecretNotFoundError(Exception):
    """Raised when a requested secret does not exist."""

    pass


class SecretDecryptionError(Exception):
    """Raised when a secret cannot be decrypted."""

    pass


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
    expires_at: float | None = None
    last_rotated: float | None = None
    last_accessed: float | None = None
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
    def days_until_expiry(self) -> float | None:
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
    """AES-256-GCM encryption.

    Requires the `cryptography` package — construction fails loudly when
    it is missing instead of silently falling back to weaker encryption.

    The key is derived with PBKDF2-HMAC-SHA256 from the master key and a
    random per-install salt (16 bytes). The salt is persisted by
    SecretManager in the database `meta` table, so the same install can
    decrypt its secrets after restart while other installs derive a
    different key from the same master key.

    Legacy data: installs created before per-install salts used the fixed
    salt `LEGACY_SALT`; SecretManager migrates those values on first open.
    Values written by the old XOR fallback (used only when `cryptography`
    was absent) remain readable through `_legacy_fallback_decrypt` and can
    be re-encrypted with `SecretManager.migrate_legacy_secrets()`. No new
    value is ever written with the XOR fallback.
    """

    LEGACY_SALT = b"neugi_secret_v2"

    def __init__(self, master_key: str, salt: bytes | None = None) -> None:
        """Initialize with a master key.

        Args:
            master_key: Master encryption key (min 32 chars recommended).
            salt: KDF salt. Random per install when omitted; pass the stored
                salt to decrypt values written by the same install.

        Raises:
            ImportError: If the `cryptography` package is not installed.
        """
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
        except ImportError as e:
            raise ImportError(
                "SecretManager requires the 'cryptography' package for AES-256-GCM. "
                "Install it with: pip install cryptography>=41.0"
            ) from e
        self._aesgcm_cls = AESGCM
        self._master_key = master_key
        self._salt = salt if salt is not None else os.urandom(16)
        self._key_bytes = self._derive_key(master_key, self._salt)
        # Key for reading pre-2.1.4 values (fixed salt + XOR fallback).
        self._legacy_key_bytes = self._derive_key(master_key, self.LEGACY_SALT)

    @property
    def salt(self) -> bytes:
        """The KDF salt in use (persist it to decrypt later)."""
        return self._salt

    @staticmethod
    def _derive_key(key: str, salt: bytes) -> bytes:
        """Derive a 32-byte key from the master key and salt.

        Args:
            key: Master key string.
            salt: Salt for key derivation (must be per-install random for
                new installs; the fixed legacy salt is only for migration).

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
        """Encrypt a plaintext string with AES-256-GCM.

        Args:
            plaintext: Text to encrypt.

        Returns:
            Base64-encoded ciphertext with IV and auth tag.
        """
        iv = os.urandom(12)
        aesgcm = self._aesgcm_cls(self._key_bytes)
        ciphertext = aesgcm.encrypt(iv, plaintext.encode("utf-8"), None)
        return base64.b64encode(iv + ciphertext).decode("ascii")

    def decrypt(self, ciphertext: str) -> str:
        """Decrypt a ciphertext string.

        Tries AES-256-GCM first; values written by the old XOR fallback
        are still readable through the legacy path (read-only migration
        support, never used for new encryption).

        Args:
            ciphertext: Base64-encoded ciphertext.

        Returns:
            Decrypted plaintext.

        Raises:
            ValueError: If decryption fails.
        """
        try:
            return self._aesgcm_decrypt(ciphertext)
        except ValueError:
            pass
        try:
            value = self._legacy_fallback_decrypt(ciphertext)
        except ValueError as e:
            raise ValueError(f"Decryption failed: {e}") from e
        logger.warning(
            "Decrypted a legacy XOR-encrypted value; re-encrypt it with SecretManager.migrate_legacy_secrets()."
        )
        return value

    def _aesgcm_decrypt(self, ciphertext: str) -> str:
        """Decrypt with AES-256-GCM only (no legacy fallback)."""
        raw = base64.b64decode(ciphertext)
        aesgcm = self._aesgcm_cls(self._key_bytes)
        try:
            return aesgcm.decrypt(raw[:12], raw[12:], None).decode("utf-8")
        except Exception as e:
            raise ValueError(f"Decryption failed: {e}") from e

    def _legacy_fallback_decrypt(self, ciphertext: str) -> str:
        """Read-only decrypt for values written by the old XOR fallback.

        Uses the legacy fixed-salt key. Never used for new encryption.
        """
        raw = base64.b64decode(ciphertext)
        iv = raw[:16]
        mac = raw[-32:]
        encrypted = raw[16:-32]

        # Verify integrity
        expected_mac = hmac.new(self._legacy_key_bytes, iv + encrypted, hashlib.sha256).digest()
        if not hmac.compare_digest(mac, expected_mac):
            raise ValueError("Integrity check failed — data may be tampered")

        # Generate keystream
        keystream = b""
        counter = 0
        while len(keystream) < len(encrypted):
            block = hashlib.sha256(self._legacy_key_bytes + iv + counter.to_bytes(4, "big")).digest()
            keystream += block
            counter += 1
        keystream = keystream[: len(encrypted)]

        # XOR decrypt
        decrypted = bytes(a ^ b for a, b in zip(encrypted, keystream, strict=False))
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
        master_key: str | None = None,
        auto_rotate_days: int | None = None,
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
            logger.warning("No master key provided — encrypt/decrypt operations will fail")
        self._auto_rotate_days = auto_rotate_days
        self._value_hashes: dict[str, str] = {}  # name -> hash for scanning
        self._access_log: list[dict[str, Any]] = []
        self._init_db()
        self._encryption = self._init_encryption() if self._master_key else None

    def _init_encryption(self) -> SecretEncryption:
        """Build the encryption object, loading or creating the KDF salt.

        The salt is stored in the `meta` table. A database without a stored
        salt is a legacy install: its values were derived with the fixed
        salt, so they are re-encrypted under a fresh random salt on first
        open (see `_reencrypt_all`).
        """
        assert self._master_key
        with self._get_conn() as conn:
            row = conn.execute("SELECT value FROM meta WHERE key = 'kdf_salt'").fetchone()
        if row is not None:
            return SecretEncryption(self._master_key, salt=base64.b64decode(row["value"]))

        legacy = SecretEncryption(self._master_key, salt=SecretEncryption.LEGACY_SALT)
        new_salt = os.urandom(16)
        new_enc = SecretEncryption(self._master_key, salt=new_salt)
        with self._get_conn() as conn:
            conn.execute(
                "INSERT INTO meta (key, value) VALUES ('kdf_salt', ?)",
                (base64.b64encode(new_salt).decode("ascii"),),
            )
        self._reencrypt_all(legacy, new_enc)
        return new_enc

    def _reencrypt_all(self, old_enc: SecretEncryption, new_enc: SecretEncryption) -> dict[str, int]:
        """Re-encrypt every stored secret from `old_enc` to `new_enc`.

        Values that cannot be decrypted with the old key are left untouched
        and counted as skipped (never deleted).
        """
        with self._get_conn() as conn:
            rows = conn.execute("SELECT name, value_encrypted FROM secrets").fetchall()
        migrated = 0
        skipped = 0
        for row in rows:
            try:
                plaintext = old_enc.decrypt(row["value_encrypted"])
            except ValueError as e:
                logger.warning("Skipping secret '%s' during salt migration: %s", row["name"], e)
                skipped += 1
                continue
            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE secrets SET value_encrypted = ?, value_hash = ? WHERE name = ?",
                    (new_enc.encrypt(plaintext), new_enc.hash_value(plaintext), row["name"]),
                )
            migrated += 1
        if migrated:
            logger.info("Migrated %d secrets to the new KDF salt (%d skipped)", migrated, skipped)
        return {"migrated": migrated, "skipped": skipped}

    def migrate_legacy_secrets(self) -> dict[str, int]:
        """Re-encrypt secrets still stored with the legacy XOR fallback.

        Safe to run repeatedly; no-op when nothing is legacy. Corrupt
        values are left untouched (get() will report them).
        """
        if not self._encryption:
            raise SecretDecryptionError("No master key configured")
        with self._get_conn() as conn:
            rows = conn.execute("SELECT name, value_encrypted FROM secrets").fetchall()
        migrated = 0
        for row in rows:
            try:
                self._encryption._aesgcm_decrypt(row["value_encrypted"])
                continue  # already AES-GCM
            except ValueError:
                pass
            try:
                plaintext = self._encryption.decrypt(row["value_encrypted"])
            except ValueError:
                continue
            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE secrets SET value_encrypted = ? WHERE name = ?",
                    (self._encryption.encrypt(plaintext), row["name"]),
                )
            migrated += 1
        if migrated:
            logger.info("Migrated %d legacy XOR secrets to AES-GCM", migrated)
        return {"migrated": migrated}

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

                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
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
        expires_in_days: int | None = None,
        metadata: dict[str, Any] | None = None,
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
        value_hash = (
            self._encryption.hash_value(value) if self._encryption else hashlib.sha256(value.encode()).hexdigest()
        )

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
                        name,
                        encrypted,
                        value_hash,
                        secret_class.value,
                        SecretStatus.ACTIVE.value,
                        now,
                        expires_at,
                        now,
                        json.dumps(entry.metadata),
                        description,
                    ),
                )
            except sqlite3.IntegrityError as e:
                raise ValueError(f"Secret '{name}' already exists") from e

        self._value_hashes[name] = value_hash
        self._log_access(name, "add")

        return entry

    def get_secret(self, name: str) -> SecretEntry | None:
        """Retrieve a secret by name.

        Args:
            name: Secret identifier.

        Returns:
            SecretEntry with decrypted value, or None if not found.
        """
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM secrets WHERE name = ?", (name,)).fetchone()

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

    def get(self, name: str) -> str:
        """Retrieve a decrypted secret value by name.

        Convenience method that returns the plaintext value directly.
        Never returns None or empty string — always raises on failure.

        Args:
            name: The secret identifier.

        Returns:
            The decrypted plaintext value.

        Raises:
            SecretNotFoundError: If no secret with this name exists.
            SecretDecryptionError: If decryption fails.
        """
        with self._get_conn() as conn:
            row = conn.execute("SELECT * FROM secrets WHERE name = ?", (name,)).fetchone()

        if row is None:
            raise SecretNotFoundError(f"Secret '{name}' not found")

        # Check status
        status = SecretStatus(row["status"])
        if status in (SecretStatus.REVOKED, SecretStatus.COMPROMISED):
            logger.warning("Attempted access to %s secret: %s", status.value, name)
            self._log_access(name, f"access_denied_{status.value}")
            raise SecretNotFoundError(f"Secret '{name}' is {status.value} and cannot be accessed")

        # Decrypt value
        try:
            value = self._decrypt_value(row["value_encrypted"])
        except (ValueError, Exception) as e:
            logger.error("Failed to decrypt secret '%s': %s", name, e)
            raise SecretDecryptionError(f"Failed to decrypt secret '{name}': {e}") from e

        if not value:
            raise SecretDecryptionError(f"Secret '{name}' decrypted to empty value")

        # Update access metadata
        now = time.time()
        with self._get_conn() as conn:
            conn.execute(
                "UPDATE secrets SET last_accessed = ?, access_count = access_count + 1 WHERE name = ?",
                (now, name),
            )

        self._log_access(name, "get")
        return value

    def update_secret(
        self,
        name: str,
        value: str | None = None,
        secret_class: SecretClass | None = None,
        status: SecretStatus | None = None,
        expires_at: float | None = None,
        metadata: dict[str, Any] | None = None,
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
            value_hash = (
                self._encryption.hash_value(value) if self._encryption else hashlib.sha256(value.encode()).hexdigest()
            )
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
                f"UPDATE secrets SET {', '.join(updates)} WHERE name = ?",  # nosec B608
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
            row = conn.execute("SELECT status FROM secrets WHERE name = ?", (name,)).fetchone()

        if row is None:
            return False

        if row["status"] == SecretStatus.COMPROMISED.value:
            logger.warning("Cannot rotate compromised secret: %s", name)
            return False

        encrypted = self._encrypt_value(new_value)
        value_hash = (
            self._encryption.hash_value(new_value)
            if self._encryption
            else hashlib.sha256(new_value.encode()).hexdigest()
        )
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
        status: SecretStatus | None = None,
        secret_class: SecretClass | None = None,
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
            entries.append(
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
            )

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

    def inject_into_env(self, name: str, env_var: str | None = None) -> bool:
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
        for name, _stored_hash in self._value_hashes.items():
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

                leaks.append(
                    {
                        "name": name,
                        "secret_class": row["secret_class"],
                        "match_context": f"...{context}...",
                    }
                )

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

        Raises:
            SecretDecryptionError: If no encryption key is configured.
        """
        if self._encryption:
            return self._encryption.encrypt(value)
        raise SecretDecryptionError(
            "No master key configured — cannot encrypt secrets. "
            "Set NEUGI_MASTER_KEY environment variable or pass master_key to SecretManager."
        )

    def _decrypt_value(self, encrypted: str) -> str:
        """Decrypt a secret value.

        Args:
            encrypted: Encrypted string.

        Returns:
            Plaintext value.

        Raises:
            SecretDecryptionError: If no encryption key is configured or decryption fails.
        """
        if self._encryption:
            return self._encryption.decrypt(encrypted)
        raise SecretDecryptionError(
            "No master key configured — cannot decrypt secrets. "
            "Set NEUGI_MASTER_KEY environment variable or pass master_key to SecretManager."
        )

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
        name: str | None = None,
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
            active = conn.execute("SELECT COUNT(*) FROM secrets WHERE status = 'active'").fetchone()[0]
            expired = conn.execute("SELECT COUNT(*) FROM secrets WHERE status = 'expired'").fetchone()[0]
            revoked = conn.execute("SELECT COUNT(*) FROM secrets WHERE status = 'revoked'").fetchone()[0]
            compromised = conn.execute("SELECT COUNT(*) FROM secrets WHERE status = 'compromised'").fetchone()[0]

            by_class: dict[str, int] = {}
            for row in conn.execute("SELECT secret_class, COUNT(*) as cnt FROM secrets GROUP BY secret_class"):
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
