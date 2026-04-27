"""
NEUGI v2 Audit Logging System
==============================

Immutable audit logging with SQLite append-only storage for comprehensive
traceability of all agent actions, tool calls, and decisions.

Features:
    - Immutable audit log (append-only SQLite)
    - Tool call tracing (who called what, when, with what args, result)
    - Decision logging (why an action was taken)
    - Session audit (full conversation replay)
    - Compliance reports
    - Log export (JSON, CSV)
    - Log retention policies

Usage:
    from neugi_swarm_v2.governance.audit import AuditLogger, AuditEventType

    logger = AuditLogger(db_path="governance.db")

    # Log events
    logger.log_event(
        event_type=AuditEventType.TOOL_CALL,
        agent_id="aurora",
        action="execute_code",
        details={"code": "print('hello')"},
        result={"output": "hello", "exit_code": 0},
    )

    # Log decisions
    logger.log_decision(
        agent_id="aurora",
        decision="approve_budget",
        reasoning="Within allocated budget for this task",
        alternatives_considered=["deny", "request_more_info"],
    )

    # Export logs
    logger.export_logs(format="json", output_path="audit_export.json")
"""

from __future__ import annotations

import csv
import io
import json
import logging
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# -- Enums -------------------------------------------------------------------

class AuditEventType(str, Enum):
    """Types of audit events."""
    TOOL_CALL = "tool_call"
    TOOL_RESULT = "tool_result"
    DECISION = "decision"
    SESSION_START = "session_start"
    SESSION_END = "session_end"
    MESSAGE = "message"
    BUDGET_CHANGE = "budget_change"
    APPROVAL_REQUEST = "approval_request"
    APPROVAL_DECISION = "approval_decision"
    POLICY_VIOLATION = "policy_violation"
    SYSTEM_EVENT = "system_event"
    ERROR = "error"
    CONFIG_CHANGE = "config_change"
    AGENT_STATE_CHANGE = "agent_state_change"


class AuditExportFormat(str, Enum):
    """Export format options."""
    JSON = "json"
    CSV = "csv"


# -- Data Classes ------------------------------------------------------------

@dataclass
class AuditEntry:
    """A single audit log entry.

    Attributes:
        entry_id: Unique entry identifier.
        timestamp: When the event occurred.
        event_type: Type of event.
        agent_id: Agent that triggered the event.
        session_id: Session context.
        action: Action being performed.
        details: Event-specific details.
        result: Action result (if any).
        metadata: Additional context.
        hash: Cryptographic hash for integrity verification.
    """

    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    event_type: AuditEventType = AuditEventType.SYSTEM_EVENT
    agent_id: str = ""
    session_id: str = ""
    action: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    metadata: dict[str, Any] = field(default_factory=dict)
    hash: str = ""


@dataclass
class ToolCallRecord:
    """Record of a tool call.

    Attributes:
        entry_id: Associated audit entry.
        agent_id: Agent that made the call.
        tool_name: Name of the tool called.
        arguments: Tool arguments.
        result: Tool result.
        duration_ms: Execution time in milliseconds.
        timestamp: When the call was made.
        status: Call status ('success', 'error', 'timeout').
    """

    entry_id: str
    agent_id: str
    tool_name: str
    arguments: dict[str, Any]
    result: Any
    duration_ms: float
    timestamp: datetime
    status: str = "success"


@dataclass
class DecisionRecord:
    """Record of a decision made by an agent.

    Attributes:
        entry_id: Associated audit entry.
        agent_id: Agent that made the decision.
        decision: The decision made.
        reasoning: Explanation for the decision.
        alternatives_considered: Other options that were considered.
        confidence: Confidence level (0.0-1.0).
        timestamp: When the decision was made.
    """

    entry_id: str
    agent_id: str
    decision: str
    reasoning: str
    alternatives_considered: list[str] = field(default_factory=list)
    confidence: float = 1.0
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class SessionAudit:
    """Complete audit trail for a session.

    Attributes:
        session_id: Session identifier.
        agent_id: Primary agent.
        start_time: Session start time.
        end_time: Session end time.
        entries: All audit entries for the session.
        tool_calls: All tool calls made.
        decisions: All decisions made.
        total_duration: Session duration.
    """

    session_id: str
    agent_id: str = ""
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    entries: list[AuditEntry] = field(default_factory=list)
    tool_calls: list[ToolCallRecord] = field(default_factory=list)
    decisions: list[DecisionRecord] = field(default_factory=list)
    total_duration: Optional[timedelta] = None


@dataclass
class AuditReport:
    """Comprehensive audit report.

    Attributes:
        generated_at: Report generation time.
        period_start: Start of reporting period.
        period_end: End of reporting period.
        total_entries: Total entries in period.
        entries_by_type: Count of entries by type.
        entries_by_agent: Count of entries by agent.
        errors: List of error entries.
        policy_violations: List of policy violations.
        summary: Human-readable summary.
    """

    generated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    total_entries: int = 0
    entries_by_type: dict[str, int] = field(default_factory=dict)
    entries_by_agent: dict[str, int] = field(default_factory=dict)
    errors: list[AuditEntry] = field(default_factory=list)
    policy_violations: list[AuditEntry] = field(default_factory=list)
    summary: str = ""


@dataclass
class RetentionPolicy:
    """Log retention policy.

    Attributes:
        name: Policy name.
        retention_days: Days to retain logs.
        event_types: Event types this policy applies to (empty = all).
        auto_delete: Whether to automatically delete old entries.
        archive_before_delete: Whether to archive before deletion.
    """

    name: str = "default"
    retention_days: int = 90
    event_types: list[str] = field(default_factory=list)
    auto_delete: bool = True
    archive_before_delete: bool = False


@dataclass
class AuditError(Exception):
    """Raised when an audit operation fails.

    Attributes:
        message: Human-readable error message.
    """

    message: str = ""


# -- Audit Logger ------------------------------------------------------------

class AuditLogger:
    """Immutable audit logger with append-only SQLite storage.

    Provides comprehensive logging of all agent actions, tool calls,
    decisions, and system events with integrity verification.

    Args:
        db_path: Path to SQLite database.
        enable_hashing: Enable cryptographic hashing for integrity.
        retention_policy: Default retention policy.

    Attributes:
        db_path: Database file path.
        enable_hashing: Whether to compute entry hashes.
        retention_policy: Active retention policy.
        _lock: Thread safety lock.
    """

    def __init__(
        self,
        db_path: str = "governance.db",
        enable_hashing: bool = True,
        retention_policy: Optional[RetentionPolicy] = None,
    ) -> None:
        self.db_path = db_path
        self.enable_hashing = enable_hashing
        self.retention_policy = retention_policy or RetentionPolicy()
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection with WAL mode.

        Returns:
            SQLite connection with foreign keys enabled.
        """
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        """Initialize database schema with append-only constraints."""
        with self._get_conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS audit_log (
                    entry_id TEXT PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    agent_id TEXT NOT NULL DEFAULT '',
                    session_id TEXT NOT NULL DEFAULT '',
                    action TEXT NOT NULL DEFAULT '',
                    details_json TEXT,
                    result_json TEXT,
                    metadata_json TEXT,
                    hash TEXT,
                    prev_hash TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_audit_timestamp
                    ON audit_log(timestamp);
                CREATE INDEX IF NOT EXISTS idx_audit_agent
                    ON audit_log(agent_id);
                CREATE INDEX IF NOT EXISTS idx_audit_session
                    ON audit_log(session_id);
                CREATE INDEX IF NOT EXISTS idx_audit_type
                    ON audit_log(event_type);

                CREATE TABLE IF NOT EXISTS retention_policies (
                    name TEXT PRIMARY KEY,
                    retention_days INTEGER NOT NULL DEFAULT 90,
                    event_types_json TEXT,
                    auto_delete INTEGER NOT NULL DEFAULT 1,
                    archive_before_delete INTEGER NOT NULL DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS audit_archive (
                    archive_id TEXT PRIMARY KEY,
                    original_entry_id TEXT NOT NULL,
                    archived_at TEXT NOT NULL,
                    entry_json TEXT NOT NULL
                );
            """)

            self._save_retention_policy(conn, self.retention_policy)

    def _compute_hash(self, entry: AuditEntry, prev_hash: str = "") -> str:
        """Compute cryptographic hash for an entry.

        Creates a chain of hashes where each entry includes the previous
        entry's hash, making tampering detectable.

        Args:
            entry: Entry to hash.
            prev_hash: Hash of the previous entry.

        Returns:
            Hex digest of the entry hash.
        """
        import hashlib

        data = json.dumps({
            "entry_id": entry.entry_id,
            "timestamp": entry.timestamp.isoformat(),
            "event_type": entry.event_type.value,
            "agent_id": entry.agent_id,
            "session_id": entry.session_id,
            "action": entry.action,
            "details": entry.details,
            "result": entry.result,
            "prev_hash": prev_hash,
        }, sort_keys=True)

        return hashlib.sha256(data.encode()).hexdigest()

    def _get_last_hash(self) -> str:
        """Get the hash of the most recent entry.

        Returns:
            Hash string, or empty string if no entries.
        """
        with self._get_conn() as conn:
            row = conn.execute(
                "SELECT hash FROM audit_log ORDER BY timestamp DESC LIMIT 1",
            ).fetchone()
            return row["hash"] if row else ""

    def log_event(
        self,
        event_type: AuditEventType,
        agent_id: str = "",
        session_id: str = "",
        action: str = "",
        details: Optional[dict[str, Any]] = None,
        result: Optional[dict[str, Any]] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log an audit event.

        Args:
            event_type: Type of event.
            agent_id: Agent that triggered the event.
            session_id: Session context.
            action: Action being performed.
            details: Event-specific details.
            result: Action result.
            metadata: Additional context.

        Returns:
            The created AuditEntry.
        """
        entry = AuditEntry(
            event_type=event_type,
            agent_id=agent_id,
            session_id=session_id,
            action=action,
            details=details or {},
            result=result or {},
            metadata=metadata or {},
        )

        if self.enable_hashing:
            prev_hash = self._get_last_hash()
            entry.hash = self._compute_hash(entry, prev_hash)

        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    INSERT INTO audit_log
                    (entry_id, timestamp, event_type, agent_id, session_id,
                     action, details_json, result_json, metadata_json, hash, prev_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        entry.entry_id,
                        entry.timestamp.isoformat(),
                        entry.event_type.value,
                        entry.agent_id,
                        entry.session_id,
                        entry.action,
                        json.dumps(entry.details),
                        json.dumps(entry.result),
                        json.dumps(entry.metadata),
                        entry.hash,
                        self._get_last_hash() if self.enable_hashing else "",
                    ),
                )

        logger.debug(
            "Audit logged: %s by %s (%s)",
            event_type.value, agent_id, action,
        )
        return entry

    def log_tool_call(
        self,
        agent_id: str,
        tool_name: str,
        arguments: dict[str, Any],
        result: Any = None,
        duration_ms: float = 0.0,
        status: str = "success",
        session_id: str = "",
    ) -> tuple[AuditEntry, ToolCallRecord]:
        """Log a tool call event.

        Args:
            agent_id: Agent that made the call.
            tool_name: Name of the tool.
            arguments: Tool arguments.
            result: Tool result.
            duration_ms: Execution time.
            status: Call status.
            session_id: Session context.

        Returns:
            Tuple of (AuditEntry, ToolCallRecord).
        """
        entry = self.log_event(
            event_type=AuditEventType.TOOL_CALL,
            agent_id=agent_id,
            session_id=session_id,
            action=tool_name,
            details={"arguments": arguments},
            result={"result": result, "status": status, "duration_ms": duration_ms},
        )

        record = ToolCallRecord(
            entry_id=entry.entry_id,
            agent_id=agent_id,
            tool_name=tool_name,
            arguments=arguments,
            result=result,
            duration_ms=duration_ms,
            timestamp=entry.timestamp,
            status=status,
        )

        return entry, record

    def log_decision(
        self,
        agent_id: str,
        decision: str,
        reasoning: str,
        alternatives_considered: Optional[list[str]] = None,
        confidence: float = 1.0,
        session_id: str = "",
        metadata: Optional[dict[str, Any]] = None,
    ) -> tuple[AuditEntry, DecisionRecord]:
        """Log a decision made by an agent.

        Args:
            agent_id: Agent that made the decision.
            decision: The decision made.
            reasoning: Explanation for the decision.
            alternatives_considered: Other options considered.
            confidence: Confidence level.
            session_id: Session context.
            metadata: Additional context.

        Returns:
            Tuple of (AuditEntry, DecisionRecord).
        """
        entry = self.log_event(
            event_type=AuditEventType.DECISION,
            agent_id=agent_id,
            session_id=session_id,
            action=decision,
            details={
                "reasoning": reasoning,
                "alternatives": alternatives_considered or [],
                "confidence": confidence,
            },
            metadata=metadata or {},
        )

        record = DecisionRecord(
            entry_id=entry.entry_id,
            agent_id=agent_id,
            decision=decision,
            reasoning=reasoning,
            alternatives_considered=alternatives_considered or [],
            confidence=confidence,
            timestamp=entry.timestamp,
        )

        return entry, record

    def log_session_start(
        self,
        session_id: str,
        agent_id: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log a session start event.

        Args:
            session_id: Session identifier.
            agent_id: Primary agent.
            metadata: Additional context.

        Returns:
            AuditEntry for the session start.
        """
        return self.log_event(
            event_type=AuditEventType.SESSION_START,
            agent_id=agent_id,
            session_id=session_id,
            action="session_start",
            metadata=metadata or {},
        )

    def log_session_end(
        self,
        session_id: str,
        agent_id: str,
        metadata: Optional[dict[str, Any]] = None,
    ) -> AuditEntry:
        """Log a session end event.

        Args:
            session_id: Session identifier.
            agent_id: Primary agent.
            metadata: Additional context.

        Returns:
            AuditEntry for the session end.
        """
        return self.log_event(
            event_type=AuditEventType.SESSION_END,
            agent_id=agent_id,
            session_id=session_id,
            action="session_end",
            metadata=metadata or {},
        )

    def get_entries(
        self,
        event_type: Optional[AuditEventType] = None,
        agent_id: Optional[str] = None,
        session_id: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        limit: int = 1000,
        offset: int = 0,
    ) -> list[AuditEntry]:
        """Query audit log entries.

        Args:
            event_type: Filter by event type.
            agent_id: Filter by agent.
            session_id: Filter by session.
            since: Start time filter.
            until: End time filter.
            limit: Maximum entries to return.
            offset: Pagination offset.

        Returns:
            List of matching AuditEntry objects.
        """
        query = "SELECT * FROM audit_log WHERE 1=1"
        params: list[Any] = []

        if event_type:
            query += " AND event_type = ?"
            params.append(event_type.value)
        if agent_id:
            query += " AND agent_id = ?"
            params.append(agent_id)
        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if since:
            query += " AND timestamp >= ?"
            params.append(since.isoformat())
        if until:
            query += " AND timestamp <= ?"
            params.append(until.isoformat())

        query += " ORDER BY timestamp ASC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self._get_conn() as conn:
            rows = conn.execute(query, params).fetchall()

        return [
            AuditEntry(
                entry_id=row["entry_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                event_type=AuditEventType(row["event_type"]),
                agent_id=row["agent_id"],
                session_id=row["session_id"],
                action=row["action"],
                details=json.loads(row["details_json"]) if row["details_json"] else {},
                result=json.loads(row["result_json"]) if row["result_json"] else {},
                metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
                hash=row["hash"] or "",
            )
            for row in rows
        ]

    def get_session_audit(self, session_id: str) -> SessionAudit:
        """Get complete audit trail for a session.

        Args:
            session_id: Session identifier.

        Returns:
            SessionAudit with full session history.
        """
        entries = self.get_entries(session_id=session_id, limit=100_000)

        tool_calls = []
        decisions = []
        start_time = None
        end_time = None
        agent_id = ""

        for entry in entries:
            if entry.event_type == AuditEventType.SESSION_START:
                start_time = entry.timestamp
                agent_id = entry.agent_id
            elif entry.event_type == AuditEventType.SESSION_END:
                end_time = entry.timestamp
            elif entry.event_type == AuditEventType.TOOL_CALL:
                tool_calls.append(ToolCallRecord(
                    entry_id=entry.entry_id,
                    agent_id=entry.agent_id,
                    tool_name=entry.action,
                    arguments=entry.details.get("arguments", {}),
                    result=entry.result.get("result"),
                    duration_ms=entry.result.get("duration_ms", 0),
                    timestamp=entry.timestamp,
                    status=entry.result.get("status", "unknown"),
                ))
            elif entry.event_type == AuditEventType.DECISION:
                decisions.append(DecisionRecord(
                    entry_id=entry.entry_id,
                    agent_id=entry.agent_id,
                    decision=entry.action,
                    reasoning=entry.details.get("reasoning", ""),
                    alternatives_considered=entry.details.get("alternatives", []),
                    confidence=entry.details.get("confidence", 1.0),
                    timestamp=entry.timestamp,
                ))

        total_duration = None
        if start_time and end_time:
            total_duration = end_time - start_time

        return SessionAudit(
            session_id=session_id,
            agent_id=agent_id,
            start_time=start_time,
            end_time=end_time,
            entries=entries,
            tool_calls=tool_calls,
            decisions=decisions,
            total_duration=total_duration,
        )

    def verify_integrity(self) -> tuple[bool, list[str]]:
        """Verify the integrity of the audit log hash chain.

        Returns:
            Tuple of (is_valid, list of issues found).
        """
        issues = []

        with self._get_conn() as conn:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY timestamp ASC",
            ).fetchall()

        if not rows:
            return True, []

        prev_hash = ""
        for row in rows:
            entry = AuditEntry(
                entry_id=row["entry_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                event_type=AuditEventType(row["event_type"]),
                agent_id=row["agent_id"],
                session_id=row["session_id"],
                action=row["action"],
                details=json.loads(row["details_json"]) if row["details_json"] else {},
                result=json.loads(row["result_json"]) if row["result_json"] else {},
                metadata=json.loads(row["metadata_json"]) if row["metadata_json"] else {},
            )

            expected_hash = self._compute_hash(entry, prev_hash)

            if row["hash"] and row["hash"] != expected_hash:
                issues.append(
                    f"Hash mismatch at entry {row['entry_id']}: "
                    f"expected {expected_hash[:16]}..., got {row['hash'][:16]}..."
                )

            if row["prev_hash"] and row["prev_hash"] != prev_hash:
                issues.append(
                    f"Prev hash mismatch at entry {row['entry_id']}: "
                    f"expected {prev_hash[:16]}..., got {row['prev_hash'][:16]}..."
                )

            prev_hash = row["hash"]

        return len(issues) == 0, issues

    def generate_report(
        self,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
    ) -> AuditReport:
        """Generate a compliance report.

        Args:
            since: Start of reporting period.
            until: End of reporting period.

        Returns:
            AuditReport with summary statistics.
        """
        entries = self.get_entries(since=since, until=until, limit=100_000)

        entries_by_type: dict[str, int] = {}
        entries_by_agent: dict[str, int] = {}
        errors = []
        violations = []

        for entry in entries:
            type_key = entry.event_type.value
            entries_by_type[type_key] = entries_by_type.get(type_key, 0) + 1

            if entry.agent_id:
                entries_by_agent[entry.agent_id] = (
                    entries_by_agent.get(entry.agent_id, 0) + 1
                )

            if entry.event_type == AuditEventType.ERROR:
                errors.append(entry)
            elif entry.event_type == AuditEventType.POLICY_VIOLATION:
                violations.append(entry)

        report = AuditReport(
            period_start=since,
            period_end=until,
            total_entries=len(entries),
            entries_by_type=entries_by_type,
            entries_by_agent=entries_by_agent,
            errors=errors,
            policy_violations=violations,
            summary=(
                f"Audit report: {len(entries)} entries, "
                f"{len(errors)} errors, {len(violations)} policy violations"
            ),
        )

        return report

    def export_logs(
        self,
        format: AuditExportFormat = AuditExportFormat.JSON,
        output_path: Optional[str] = None,
        since: Optional[datetime] = None,
        until: Optional[datetime] = None,
        event_type: Optional[AuditEventType] = None,
    ) -> str:
        """Export audit logs to a file.

        Args:
            format: Export format (JSON or CSV).
            output_path: Output file path. Auto-generated if None.
            since: Start time filter.
            until: End time filter.
            event_type: Filter by event type.

        Returns:
            Path to the exported file.
        """
        entries = self.get_entries(
            event_type=event_type,
            since=since,
            until=until,
            limit=1_000_000,
        )

        if output_path is None:
            timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            ext = "json" if format == AuditExportFormat.JSON else "csv"
            output_path = f"audit_export_{timestamp}.{ext}"

        if format == AuditExportFormat.JSON:
            self._export_json(entries, output_path)
        else:
            self._export_csv(entries, output_path)

        logger.info("Exported %d entries to %s", len(entries), output_path)
        return output_path

    def _export_json(self, entries: list[AuditEntry], path: str) -> None:
        """Export entries as JSON.

        Args:
            entries: Entries to export.
            path: Output file path.
        """
        data = [
            {
                "entry_id": e.entry_id,
                "timestamp": e.timestamp.isoformat(),
                "event_type": e.event_type.value,
                "agent_id": e.agent_id,
                "session_id": e.session_id,
                "action": e.action,
                "details": e.details,
                "result": e.result,
                "metadata": e.metadata,
                "hash": e.hash,
            }
            for e in entries
        ]

        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    def _export_csv(self, entries: list[AuditEntry], path: str) -> None:
        """Export entries as CSV.

        Args:
            entries: Entries to export.
            path: Output file path.
        """
        with open(path, "w", encoding="utf-8", newline="") as f:
            writer = csv.writer(f)
            writer.writerow([
                "entry_id", "timestamp", "event_type", "agent_id",
                "session_id", "action", "details", "result", "hash",
            ])

            for entry in entries:
                writer.writerow([
                    entry.entry_id,
                    entry.timestamp.isoformat(),
                    entry.event_type.value,
                    entry.agent_id,
                    entry.session_id,
                    entry.action,
                    json.dumps(entry.details),
                    json.dumps(entry.result),
                    entry.hash,
                ])

    def set_retention_policy(self, policy: RetentionPolicy) -> None:
        """Set the active retention policy.

        Args:
            policy: Policy to set.
        """
        with self._lock:
            with self._get_conn() as conn:
                self._save_retention_policy(conn, policy)
            self.retention_policy = policy
            logger.info("Retention policy set: %s (%d days)", policy.name, policy.retention_days)

    def _save_retention_policy(
        self,
        conn: sqlite3.Connection,
        policy: RetentionPolicy,
    ) -> None:
        """Save a retention policy to the database.

        Args:
            conn: Database connection.
            policy: Policy to save.
        """
        conn.execute(
            """
            INSERT OR REPLACE INTO retention_policies
            (name, retention_days, event_types_json, auto_delete, archive_before_delete)
            VALUES (?, ?, ?, ?, ?)
            """,
            (
                policy.name,
                policy.retention_days,
                json.dumps(policy.event_types),
                1 if policy.auto_delete else 0,
                1 if policy.archive_before_delete else 0,
            ),
        )

    def enforce_retention(self) -> int:
        """Enforce the retention policy by deleting old entries.

        Returns:
            Number of entries deleted.
        """
        if not self.retention_policy.auto_delete:
            return 0

        cutoff = datetime.now(timezone.utc) - timedelta(
            days=self.retention_policy.retention_days,
        )

        deleted = 0

        with self._lock:
            with self._get_conn() as conn:
                if self.retention_policy.event_types:
                    placeholders = ",".join(
                        "?" for _ in self.retention_policy.event_types
                    )
                    query = (
                        f"SELECT * FROM audit_log "
                        f"WHERE timestamp < ? AND event_type IN ({placeholders})"
                    )
                    params = [cutoff.isoformat()] + list(self.retention_policy.event_types)
                else:
                    query = "SELECT * FROM audit_log WHERE timestamp < ?"
                    params = [cutoff.isoformat()]

                rows = conn.execute(query, params).fetchall()

                if self.retention_policy.archive_before_delete and rows:
                    self._archive_entries(conn, rows)

                if self.retention_policy.event_types:
                    delete_query = (
                        f"DELETE FROM audit_log "
                        f"WHERE timestamp < ? AND event_type IN ({placeholders})"
                    )
                else:
                    delete_query = "DELETE FROM audit_log WHERE timestamp < ?"

                cursor = conn.execute(delete_query, params)
                deleted = cursor.rowcount

        if deleted > 0:
            logger.info("Retention enforced: %d entries deleted", deleted)

        return deleted

    def _archive_entries(
        self,
        conn: sqlite3.Connection,
        entries: list[sqlite3.Row],
    ) -> None:
        """Archive entries before deletion.

        Args:
            conn: Database connection.
            entries: Entries to archive.
        """
        for row in entries:
            entry_data = {
                "entry_id": row["entry_id"],
                "timestamp": row["timestamp"],
                "event_type": row["event_type"],
                "agent_id": row["agent_id"],
                "session_id": row["session_id"],
                "action": row["action"],
                "details_json": row["details_json"],
                "result_json": row["result_json"],
                "metadata_json": row["metadata_json"],
                "hash": row["hash"],
            }

            conn.execute(
                """
                INSERT INTO audit_archive
                (archive_id, original_entry_id, archived_at, entry_json)
                VALUES (?, ?, ?, ?)
                """,
                (
                    str(uuid.uuid4()),
                    row["entry_id"],
                    datetime.now(timezone.utc).isoformat(),
                    json.dumps(entry_data),
                ),
            )

    def get_entry_count(self) -> int:
        """Get total number of audit entries.

        Returns:
            Total entry count.
        """
        with self._get_conn() as conn:
            row = conn.execute("SELECT COUNT(*) as cnt FROM audit_log").fetchone()
            return row["cnt"]

    def get_storage_size(self) -> int:
        """Get approximate storage size of the audit log.

        Returns:
            Size in bytes.
        """
        db_path = Path(self.db_path)
        if db_path.exists():
            return db_path.stat().st_size
        return 0

    def close(self) -> None:
        """Close database connections."""
        pass

    def __enter__(self) -> "AuditLogger":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()
