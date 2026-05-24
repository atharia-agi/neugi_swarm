"""
Checkpoint-Based Resilience for MCP Server
===========================================

Provides crash recovery and durable execution for long-running
MCP workflows using periodic state checkpointing.

Inspired by LangGraph's checkpointing pattern, adapted for MCP.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sqlite3
import threading
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class CheckpointData:
    """Represents a single checkpoint in the execution history."""

    def __init__(
        self,
        checkpoint_id: str,
        task_id: str,
        step: int,
        state: dict[str, Any],
        timestamp: float = None,
        metadata: dict[str, Any] | None = None,
    ):
        self.checkpoint_id = checkpoint_id
        self.task_id = task_id
        self.step = step
        self.state = state
        self.timestamp = timestamp or datetime.now().isoformat()
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "checkpoint_id": self.checkpoint_id,
            "task_id": self.task_id,
            "step": self.step,
            "state": self.state,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> CheckpointData:
        return cls(
            checkpoint_id=data["checkpoint_id"],
            task_id=data["task_id"],
            step=data["step"],
            state=data["state"],
            timestamp=data.get("timestamp"),
            metadata=data.get("metadata", {}),
        )


class ExecutionThread:
    """Tracks an executing workflow with checkpoint support."""

    def __init__(self, thread_id: str, checkpoint_store: CheckpointStore):
        self.thread_id = thread_id
        self._store = checkpoint_store
        self._checkpoints: list[CheckpointData] = []
        self._current_step = 0
        self._lock = threading.Lock()
        self._created_at = datetime.now().isoformat()
        self._updated_at = self._created_at
        self._status = "active"  # active, paused, completed, failed
        self._result: dict[str, Any] | None = None

    def checkpoint(self, state: dict[str, Any], metadata: dict[str, Any] | None = None) -> CheckpointData:
        """Create a new checkpoint for this execution thread.

        Args:
            state: Current execution state
            metadata: Additional metadata to store

        Returns:
            The created CheckpointData
        """
        with self._lock:
            cp_id = f"cp-{uuid.uuid4().hex[:12]}"
            checkpoint = CheckpointData(
                checkpoint_id=cp_id,
                task_id=self.thread_id,
                step=self._current_step,
                state=state.copy(),
                metadata=metadata or {},
            )
            self._checkpoints.append(checkpoint)
            self._current_step += 1
            self._updated_at = datetime.now().isoformat()

            # Persist to store
            self._store._save_checkpoint(self.thread_id, checkpoint)

            logger.debug(
                "Checkpoint %s created for thread %s (step=%d)",
                cp_id,
                self.thread_id,
                self._current_step - 1,
            )
            return checkpoint

    @property
    def current_state(self) -> dict[str, Any]:
        """Get the latest state from the most recent checkpoint."""
        with self._lock:
            if self._checkpoints:
                return self._checkpoints[-1].state.copy()
            return {}

    @property
    def last_checkpoint(self) -> CheckpointData | None:
        """Get the most recent checkpoint."""
        with self._lock:
            return self._checkpoints[-1] if self._checkpoints else None

    @property
    def checkpoint_count(self) -> int:
        with self._lock:
            return len(self._checkpoints)

    def to_dict(self) -> dict:
        with self._lock:
            latest_state = self._checkpoints[-1].state.copy() if self._checkpoints else {}
            return {
                "thread_id": self.thread_id,
                "status": self._status,
                "current_step": self._current_step,
                "checkpoint_count": len(self._checkpoints),
                "created_at": self._created_at,
                "updated_at": self._updated_at,
                "result": self._result,
                "latest_state": latest_state,
            }


class CheckpointStore:
    """SQLite-backed persistent store for execution checkpoints.

    Provides durable storage for workflow state, enabling crash recovery
    and resumption of long-running tasks.
    """

    def __init__(self, db_path: str | Path):
        self.db_path = str(db_path)
        self._local = threading.local()
        self._lock = threading.Lock()
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a thread-local database connection."""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(
                self.db_path,
                check_same_thread=False,
                timeout=30.0,
            )
            self._local.conn.row_factory = sqlite3.Row
            # Enable WAL mode for better concurrent access
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA synchronous=NORMAL")
        return self._local.conn

    def _init_db(self) -> None:
        """Initialize the database schema."""
        try:
            conn = self._get_conn()
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS execution_threads (
                    thread_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    current_step INTEGER NOT NULL DEFAULT 0,
                    result TEXT,
                    metadata TEXT
                );

                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    thread_id TEXT NOT NULL,
                    step INTEGER NOT NULL,
                    state TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    metadata TEXT,
                    FOREIGN KEY (thread_id) REFERENCES execution_threads(thread_id)
                );

                CREATE INDEX IF NOT EXISTS idx_checkpoints_thread
                    ON checkpoints(thread_id, step);

                CREATE INDEX IF NOT EXISTS idx_threads_status
                    ON execution_threads(status);

                CREATE TABLE IF NOT EXISTS recovery_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    thread_id TEXT NOT NULL,
                    recovery_timestamp TEXT NOT NULL,
                    original_error TEXT,
                    recovered_from_checkpoint TEXT,
                    status TEXT
                );
            """)
            conn.commit()
            logger.info("Checkpoint store initialized at %s", self.db_path)
        except Exception as e:
            logger.error("Failed to initialize checkpoint store: %s", e)
            raise

    def create_thread(self, thread_id: str, metadata: dict[str, Any] | None = None) -> ExecutionThread:
        """Create a new execution thread with initial checkpoint."""
        with self._lock:
            conn = self._get_conn()
            now = datetime.now().isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO execution_threads (thread_id, status, created_at, updated_at, current_step, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                (
                    thread_id,
                    "active",
                    now,
                    now,
                    0,
                    json.dumps(metadata or {}),
                ),
            )
            conn.commit()

        thread = ExecutionThread(thread_id, self)
        # Create initial checkpoint
        thread.checkpoint(
            {"status": "initialized", "created_at": now},
            metadata=metadata,
        )
        logger.info("Created execution thread: %s", thread_id)
        return thread

    def get_thread(self, thread_id: str) -> ExecutionThread | None:
        """Restore an execution thread from the store.

        This is the key recovery method — restores thread state
        from the last checkpoint.

        Args:
            thread_id: The thread to restore

        Returns:
            ExecutionThread with state restored, or None if not found
        """
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM execution_threads WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()

        if row is None:
            return None

        thread = ExecutionThread(thread_id, self)
        thread._status = row["status"]
        thread._current_step = row["current_step"]
        thread._created_at = row["created_at"]
        thread._updated_at = row["updated_at"]
        thread._result = json.loads(row["result"]) if row["result"] else None

        # Restore checkpoints
        checkpoints = conn.execute(
            "SELECT * FROM checkpoints WHERE thread_id = ? ORDER BY step ASC",
            (thread_id,),
        ).fetchall()

        for cp_row in checkpoints:
            cp = CheckpointData(
                checkpoint_id=cp_row["checkpoint_id"],
                task_id=cp_row["thread_id"],
                step=cp_row["step"],
                state=json.loads(cp_row["state"]),
                timestamp=cp_row["timestamp"],
                metadata=json.loads(cp_row["metadata"]) if cp_row["metadata"] else {},
            )
            thread._checkpoints.append(cp)

        logger.info(
            "Restored thread %s: %d checkpoints, step=%d, status=%s",
            thread_id,
            len(thread._checkpoints),
            thread._current_step,
            thread._status,
        )
        return thread

    def list_threads(self, status: str | None = None) -> list[dict[str, Any]]:
        """List execution threads, optionally filtered by status."""
        conn = self._get_conn()
        if status:
            rows = conn.execute(
                "SELECT * FROM execution_threads WHERE status = ? ORDER BY updated_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM execution_threads ORDER BY updated_at DESC LIMIT 100"
            ).fetchall()

        return [
            {
                "thread_id": r["thread_id"],
                "status": r["status"],
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
                "current_step": r["current_step"],
                "checkpoint_count": self._get_checkpoint_count(r["thread_id"]),
            }
            for r in rows
        ]

    def _get_checkpoint_count(self, thread_id: str) -> int:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT COUNT(*) as cnt FROM checkpoints WHERE thread_id = ?",
            (thread_id,),
        ).fetchone()
        return row["cnt"] if row else 0

    def _save_checkpoint(self, thread_id: str, checkpoint: CheckpointData) -> None:
        """Persist a checkpoint to the database."""
        conn = self._get_conn()
        conn.execute(
            "INSERT OR REPLACE INTO checkpoints (checkpoint_id, thread_id, step, state, timestamp, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (
                checkpoint.checkpoint_id,
                thread_id,
                checkpoint.step,
                json.dumps(checkpoint.state),
                checkpoint.timestamp,
                json.dumps(checkpoint.metadata),
            ),
        )
        conn.execute(
            "UPDATE execution_threads SET updated_at = ?, current_step = ? WHERE thread_id = ?",
            (datetime.now().isoformat(), checkpoint.step + 1, thread_id),
        )
        conn.commit()

    def update_thread_status(self, thread_id: str, status: str, result: Any = None) -> None:
        """Update the status of an execution thread."""
        conn = self._get_conn()
        result_json = json.dumps(result) if result is not None else None
        conn.execute(
            "UPDATE execution_threads SET status = ?, updated_at = ?, result = ? WHERE thread_id = ?",
            (status, datetime.now().isoformat(), result_json, thread_id),
        )
        conn.commit()

    def log_recovery(
        self,
        thread_id: str,
        error: str,
        checkpoint_id: str | None,
        success: bool,
    ) -> None:
        """Log a recovery attempt."""
        conn = self._get_conn()
        conn.execute(
            "INSERT INTO recovery_log (thread_id, recovery_timestamp, original_error, recovered_from_checkpoint, status) VALUES (?, ?, ?, ?, ?)",
            (
                thread_id,
                datetime.now().isoformat(),
                error,
                checkpoint_id,
                "success" if success else "failed",
            ),
        )
        conn.commit()

    def cleanup_old_threads(self, max_age_hours: int = 24, keep_statuses: list[str] | None = None) -> int:
        """Clean up old completed/failed threads.

        Args:
            max_age_hours: Threads older than this will be cleaned
            keep_statuses: Statuses to keep (default: keep 'active' and 'paused')

        Returns:
            Number of threads cleaned up
        """
        if keep_statuses is None:
            keep_statuses = ["active", "paused"]

        cutoff = datetime.now().timestamp() - (max_age_hours * 3600)
        conn = self._get_conn()

        # Get old threads to clean
        old_threads = conn.execute(
            "SELECT thread_id FROM execution_threads WHERE status NOT IN ({}) AND updated_at < ?".format(  # nosec B608
                ",".join("?" for _ in keep_statuses)
            ),
            [*keep_statuses, cutoff],
        ).fetchall()

        cleaned = 0
        for row in old_threads:
            tid = row["thread_id"]
            conn.execute("DELETE FROM checkpoints WHERE thread_id = ?", (tid,))
            conn.execute("DELETE FROM execution_threads WHERE thread_id = ?", (tid,))
            cleaned += 1

        conn.commit()
        logger.info("Cleaned up %d old threads", cleaned)
        return cleaned

    def get_stats(self) -> dict[str, Any]:
        """Get checkpoint store statistics."""
        conn = self._get_conn()
        total_threads = conn.execute("SELECT COUNT(*) FROM execution_threads").fetchone()[0]
        active_threads = conn.execute(
            "SELECT COUNT(*) FROM execution_threads WHERE status = 'active'"
        ).fetchone()[0]
        total_checkpoints = conn.execute("SELECT COUNT(*) FROM checkpoints").fetchone()[0]
        total_recoveries = conn.execute("SELECT COUNT(*) FROM recovery_log").fetchone()[0]
        successful_recoveries = conn.execute(
            "SELECT COUNT(*) FROM recovery_log WHERE status = 'success'"
        ).fetchone()[0]

        return {
            "total_threads": total_threads,
            "active_threads": active_threads,
            "total_checkpoints": total_checkpoints,
            "total_recoveries": total_recoveries,
            "successful_recoveries": successful_recoveries,
            "db_size_bytes": os.path.getsize(self.db_path) if os.path.exists(self.db_path) else 0,
        }

    def close(self) -> None:
        """Close all database connections."""
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None


class ResilientMCPExecutor:
    """MCP workflow executor with checkpoint-based resilience.

    Wraps MCP tool execution with automatic checkpointing and recovery.
    If a crash occurs, execution can resume from the last checkpoint.

    Usage:
        store = CheckpointStore("/path/to/checkpoints.db")
        executor = ResilientMCPExecutor(store, mcp_server)
        result = await executor.execute_workflow("my_task", {"param": "value"})
    """

    def __init__(
        self,
        checkpoint_store: CheckpointStore,
        mcp_server: Any = None,
        auto_resume: bool = True,
        checkpoint_interval: int = 10,
    ):
        """Initialize the resilient executor.

        Args:
            checkpoint_store: The checkpoint store for persistence
            mcp_server: Optional MCPServer for tool execution
            auto_resume: Automatically resume from checkpoint on failure
            checkpoint_interval: Number of steps between checkpoints
        """
        self.store = checkpoint_store
        self.server = mcp_server
        self.auto_resume = auto_resume
        self.checkpoint_interval = checkpoint_interval
        self._active_threads: dict[str, ExecutionThread] = {}
        self._lock = threading.Lock()

    async def execute_workflow(
        self,
        workflow_name: str,
        initial_state: dict[str, Any],
        thread_id: str | None = None,
        max_steps: int = 100,
    ) -> dict[str, Any]:
        """Execute a workflow with checkpoint-based resilience.

        Args:
            workflow_name: Name of the workflow
            initial_state: Initial state for the workflow
            thread_id: Existing thread ID to resume, or None for new
            max_steps: Maximum number of steps before forced checkpoint

        Returns:
            Final workflow result
        """
        # Try to resume from existing thread
        thread = None
        if thread_id:
            thread = self.store.get_thread(thread_id)

        if thread is None:
            # Create new thread
            thread_id = f"wf-{workflow_name}-{uuid.uuid4().hex[:12]}"
            metadata = {
                "workflow_name": workflow_name,
                "started_at": datetime.now().isoformat(),
                "max_steps": max_steps,
            }
            thread = self.store.create_thread(thread_id, metadata)
            logger.info("Created new workflow thread: %s", thread_id)
        else:
            logger.info(
                "Resuming workflow thread %s from checkpoint (step=%d)",
                thread_id,
                thread._current_step,
            )

        with self._lock:
            self._active_threads[thread_id] = thread

        try:
            current_state = thread.current_state

            # Merge initial state with recovered state
            if current_state:
                merged = {**initial_state, **current_state}
                # Don't overwrite explicit initial values
                for k, v in initial_state.items():
                    if k not in current_state or current_state[k] is None:
                        merged[k] = v
                current_state = merged
            else:
                current_state = initial_state.copy()

            # Execute workflow steps
            step = thread._current_step
            while step < max_steps and thread._status == "active":
                # Checkpoint periodically
                if step > 0 and step % self.checkpoint_interval == 0:
                    current_state["_step"] = step
                    current_state["_progress"] = step / max_steps
                    thread.checkpoint(current_state, {"step": step})

                # Simulate workflow step execution
                # In real implementation, this would call MCP tools
                current_state["last_step"] = step
                current_state["last_executed"] = datetime.now().isoformat()

                step += 1

                # In a real workflow, there would be actual tool calls here
                # For now, we advance the state
                await asyncio.sleep(0)  # Yield control

            # Final checkpoint
            current_state["status"] = "completed"
            current_state["completed_at"] = datetime.now().isoformat()
            thread.checkpoint(current_state, {"final": True})

            # Mark thread as completed
            self.store.update_thread_status(thread_id, "completed", current_state)
            thread._status = "completed"
            thread._result = current_state

            logger.info(
                "Workflow %s completed in %d steps", thread_id, thread._current_step
            )
            return current_state

        except Exception as e:
            error_msg = f"{type(e).__name__}: {e}"
            logger.error("Workflow %s failed at step %d: %s", thread_id, step, error_msg)

            # Save error checkpoint for recovery
            current_state["_error"] = error_msg
            current_state["_failed_at_step"] = step
            thread.checkpoint(current_state, {"error": error_msg, "step": step})

            self.store.update_thread_status(thread_id, "failed", {"error": error_msg})
            self.store.log_recovery(thread_id, error_msg, thread.last_checkpoint.checkpoint_id if thread.last_checkpoint else None, False)
            thread._status = "failed"

            if self.auto_resume:
                logger.info("Auto-resume enabled, thread %s can be retried", thread_id)

            raise

        finally:
            with self._lock:
                self._active_threads.pop(thread_id, None)

    def get_thread_status(self, thread_id: str) -> dict[str, Any] | None:
        """Get the status of a workflow thread."""
        thread = self._active_threads.get(thread_id)
        if thread:
            return thread.to_dict()
        return self.store.get_thread(thread_id)

    def list_active_workflows(self) -> list[dict[str, Any]]:
        """List all active workflow threads."""
        return self.store.list_threads("active")

    def cleanup_completed(self, max_age_hours: int = 24) -> int:
        """Clean up completed/failed threads."""
        return self.store.cleanup_old_threads(max_age_hours)

    def get_stats(self) -> dict[str, Any]:
        """Get executor statistics."""
        stats = self.store.get_stats()
        stats["active_threads"] = len(self._active_threads)
        return stats
