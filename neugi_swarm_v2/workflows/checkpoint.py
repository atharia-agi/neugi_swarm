"""CheckpointManager: Durable execution with SQLite persistence.

Provides checkpoint-based recovery for workflows, allowing execution
to resume from the last saved state after failures or interruptions.
"""

from __future__ import annotations

import json
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class CheckpointDiff:
    """Diff between two checkpoints showing what changed.

    Attributes:
        added: Keys that were added in the new checkpoint.
        removed: Keys that were removed in the new checkpoint.
        modified: Keys that were modified with old and new values.
    """

    added: Dict[str, Any] = field(default_factory=dict)
    removed: Dict[str, Any] = field(default_factory=dict)
    modified: Dict[str, Tuple[Any, Any]] = field(default_factory=dict)

    @property
    def has_changes(self) -> bool:
        """Check if there are any changes."""
        return bool(self.added or self.removed or self.modified)

    def to_dict(self) -> Dict[str, Any]:
        """Convert diff to dictionary."""
        return {
            "added": dict(self.added),
            "removed": dict(self.removed),
            "modified": {k: {"old": v[0], "new": v[1]} for k, v in self.modified.items()},
        }


@dataclass
class Checkpoint:
    """A saved checkpoint of workflow execution state.

    Attributes:
        checkpoint_id: Unique identifier for the checkpoint.
        workflow_id: Identifier for the workflow instance.
        node_name: Last completed node name.
        state: Serialized workflow state.
        execution_path: List of completed node names.
        version: Checkpoint version number.
        created_at: Timestamp when checkpoint was created.
        metadata: Arbitrary metadata.
    """

    checkpoint_id: str
    workflow_id: str
    node_name: str
    state: Dict[str, Any]
    execution_path: List[str]
    version: int
    created_at: float
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert checkpoint to dictionary for serialization."""
        return {
            "checkpoint_id": self.checkpoint_id,
            "workflow_id": self.workflow_id,
            "node_name": self.node_name,
            "state": self.state,
            "execution_path": self.execution_path,
            "version": self.version,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Checkpoint":
        """Create a checkpoint from a dictionary.

        Args:
            data: Dictionary with checkpoint data.

        Returns:
            Checkpoint instance.
        """
        return cls(
            checkpoint_id=data["checkpoint_id"],
            workflow_id=data["workflow_id"],
            node_name=data["node_name"],
            state=data["state"],
            execution_path=data["execution_path"],
            version=data["version"],
            created_at=data["created_at"],
            metadata=data.get("metadata", {}),
        )


class CheckpointStorage:
    """Abstract base class for checkpoint storage backends."""

    def save(self, checkpoint: Checkpoint) -> None:
        """Save a checkpoint.

        Args:
            checkpoint: Checkpoint to save.
        """
        raise NotImplementedError

    def load(self, workflow_id: str, version: Optional[int] = None) -> Optional[Checkpoint]:
        """Load the latest or specific version checkpoint for a workflow.

        Args:
            workflow_id: Workflow identifier.
            version: Optional specific version to load.

        Returns:
            Checkpoint if found, None otherwise.
        """
        raise NotImplementedError

    def list_checkpoints(self, workflow_id: str) -> List[Checkpoint]:
        """List all checkpoints for a workflow.

        Args:
            workflow_id: Workflow identifier.

        Returns:
            List of checkpoints ordered by version.
        """
        raise NotImplementedError

    def delete(self, checkpoint_id: str) -> bool:
        """Delete a specific checkpoint.

        Args:
            checkpoint_id: Checkpoint to delete.

        Returns:
            True if deleted, False if not found.
        """
        raise NotImplementedError

    def delete_workflow_checkpoints(self, workflow_id: str) -> int:
        """Delete all checkpoints for a workflow.

        Args:
            workflow_id: Workflow identifier.

        Returns:
            Number of checkpoints deleted.
        """
        raise NotImplementedError


class SQLiteCheckpointStorage(CheckpointStorage):
    """SQLite-based checkpoint storage.

    Provides persistent storage for checkpoints with support for
    versioning, querying, and cleanup.

    Example:
        storage = SQLiteCheckpointStorage("checkpoints.db")
        storage.save(checkpoint)
        latest = storage.load("workflow_123")
    """

    def __init__(self, db_path: str = "checkpoints.db") -> None:
        """Initialize the SQLite storage.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS checkpoints (
                    checkpoint_id TEXT PRIMARY KEY,
                    workflow_id TEXT NOT NULL,
                    node_name TEXT NOT NULL,
                    state TEXT NOT NULL,
                    execution_path TEXT NOT NULL,
                    version INTEGER NOT NULL,
                    created_at REAL NOT NULL,
                    metadata TEXT DEFAULT '{}'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_workflow_version
                ON checkpoints (workflow_id, version)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_created_at
                ON checkpoints (created_at)
            """)

    def save(self, checkpoint: Checkpoint) -> None:
        """Save a checkpoint to the database.

        Args:
            checkpoint: Checkpoint to save.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                INSERT OR REPLACE INTO checkpoints
                (checkpoint_id, workflow_id, node_name, state, execution_path,
                 version, created_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                checkpoint.checkpoint_id,
                checkpoint.workflow_id,
                checkpoint.node_name,
                json.dumps(checkpoint.state),
                json.dumps(checkpoint.execution_path),
                checkpoint.version,
                checkpoint.created_at,
                json.dumps(checkpoint.metadata),
            ))

    def load(self, workflow_id: str, version: Optional[int] = None) -> Optional[Checkpoint]:
        """Load a checkpoint from the database.

        Args:
            workflow_id: Workflow identifier.
            version: Optional specific version to load.

        Returns:
            Checkpoint if found, None otherwise.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row

            if version is not None:
                cursor = conn.execute(
                    "SELECT * FROM checkpoints WHERE workflow_id = ? AND version = ?",
                    (workflow_id, version),
                )
            else:
                cursor = conn.execute(
                    "SELECT * FROM checkpoints WHERE workflow_id = ? ORDER BY version DESC LIMIT 1",
                    (workflow_id,),
                )

            row = cursor.fetchone()
            if not row:
                return None

            return Checkpoint(
                checkpoint_id=row["checkpoint_id"],
                workflow_id=row["workflow_id"],
                node_name=row["node_name"],
                state=json.loads(row["state"]),
                execution_path=json.loads(row["execution_path"]),
                version=row["version"],
                created_at=row["created_at"],
                metadata=json.loads(row["metadata"]),
            )

    def list_checkpoints(self, workflow_id: str) -> List[Checkpoint]:
        """List all checkpoints for a workflow.

        Args:
            workflow_id: Workflow identifier.

        Returns:
            List of checkpoints ordered by version.
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(
                "SELECT * FROM checkpoints WHERE workflow_id = ? ORDER BY version ASC",
                (workflow_id,),
            )

            return [
                Checkpoint(
                    checkpoint_id=row["checkpoint_id"],
                    workflow_id=row["workflow_id"],
                    node_name=row["node_name"],
                    state=json.loads(row["state"]),
                    execution_path=json.loads(row["execution_path"]),
                    version=row["version"],
                    created_at=row["created_at"],
                    metadata=json.loads(row["metadata"]),
                )
                for row in cursor.fetchall()
            ]

    def delete(self, checkpoint_id: str) -> bool:
        """Delete a specific checkpoint.

        Args:
            checkpoint_id: Checkpoint to delete.

        Returns:
            True if deleted, False if not found.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM checkpoints WHERE checkpoint_id = ?",
                (checkpoint_id,),
            )
            return cursor.rowcount > 0

    def delete_workflow_checkpoints(self, workflow_id: str) -> int:
        """Delete all checkpoints for a workflow.

        Args:
            workflow_id: Workflow identifier.

        Returns:
            Number of checkpoints deleted.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM checkpoints WHERE workflow_id = ?",
                (workflow_id,),
            )
            return cursor.rowcount

    def cleanup_old_checkpoints(self, max_age_seconds: float) -> int:
        """Delete checkpoints older than a specified age.

        Args:
            max_age_seconds: Maximum age in seconds.

        Returns:
            Number of checkpoints deleted.
        """
        cutoff = time.time() - max_age_seconds
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM checkpoints WHERE created_at < ?",
                (cutoff,),
            )
            return cursor.rowcount

    def cleanup_keep_latest(self, workflow_id: str, keep_count: int) -> int:
        """Keep only the latest N checkpoints for a workflow.

        Args:
            workflow_id: Workflow identifier.
            keep_count: Number of checkpoints to keep.

        Returns:
            Number of checkpoints deleted.
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute("""
                DELETE FROM checkpoints
                WHERE workflow_id = ?
                AND checkpoint_id NOT IN (
                    SELECT checkpoint_id
                    FROM checkpoints
                    WHERE workflow_id = ?
                    ORDER BY version DESC
                    LIMIT ?
                )
            """, (workflow_id, workflow_id, keep_count))
            return cursor.rowcount

    def get_checkpoint_count(self, workflow_id: Optional[str] = None) -> int:
        """Get the number of checkpoints.

        Args:
            workflow_id: Optional workflow to count. If None, counts all.

        Returns:
            Number of checkpoints.
        """
        with sqlite3.connect(self.db_path) as conn:
            if workflow_id:
                cursor = conn.execute(
                    "SELECT COUNT(*) FROM checkpoints WHERE workflow_id = ?",
                    (workflow_id,),
                )
            else:
                cursor = conn.execute("SELECT COUNT(*) FROM checkpoints")
            return cursor.fetchone()[0]


class CheckpointManager:
    """Manages checkpoint lifecycle for durable workflow execution.

    Coordinates checkpoint creation, loading, diffing, and cleanup.
    Works with any CheckpointStorage backend.

    Example:
        manager = CheckpointManager(SQLiteCheckpointStorage())
        checkpoint = manager.create_checkpoint("workflow_1", "node_a", state)
        restored = manager.restore_checkpoint("workflow_1")
    """

    def __init__(
        self,
        storage: Optional[CheckpointStorage] = None,
        auto_checkpoint: bool = True,
    ) -> None:
        """Initialize the checkpoint manager.

        Args:
            storage: Checkpoint storage backend. Defaults to SQLite.
            auto_checkpoint: Whether to auto-generate checkpoint IDs.
        """
        self.storage = storage or SQLiteCheckpointStorage()
        self.auto_checkpoint = auto_checkpoint
        self._checkpoint_counter: Dict[str, int] = {}

    def create_checkpoint(
        self,
        workflow_id: str,
        node_name: str,
        state: Dict[str, Any],
        execution_path: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Checkpoint:
        """Create and save a new checkpoint.

        Args:
            workflow_id: Workflow identifier.
            node_name: Last completed node name.
            state: Current workflow state.
            execution_path: List of completed nodes.
            metadata: Optional metadata.

        Returns:
            Created checkpoint.
        """
        # Get next version
        version = self._get_next_version(workflow_id)

        # Generate checkpoint ID
        checkpoint_id = f"{workflow_id}_v{version}"

        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            workflow_id=workflow_id,
            node_name=node_name,
            state=state,
            execution_path=execution_path or [],
            version=version,
            created_at=time.time(),
            metadata=metadata or {},
        )

        self.storage.save(checkpoint)
        return checkpoint

    def restore_checkpoint(
        self,
        workflow_id: str,
        version: Optional[int] = None,
    ) -> Optional[Checkpoint]:
        """Restore a checkpoint for a workflow.

        Args:
            workflow_id: Workflow identifier.
            version: Optional specific version to restore.

        Returns:
            Checkpoint if found, None otherwise.
        """
        return self.storage.load(workflow_id, version)

    def get_checkpoint_diff(
        self,
        workflow_id: str,
        version_a: int,
        version_b: Optional[int] = None,
    ) -> Optional[CheckpointDiff]:
        """Get the diff between two checkpoints.

        Args:
            workflow_id: Workflow identifier.
            version_a: First version.
            version_b: Second version (latest if None).

        Returns:
            CheckpointDiff if both checkpoints exist, None otherwise.
        """
        cp_a = self.storage.load(workflow_id, version_a)
        cp_b = self.storage.load(workflow_id, version_b) if version_b else self.storage.load(workflow_id)

        if not cp_a or not cp_b:
            return None

        return self._compute_diff(cp_a.state, cp_b.state)

    def _compute_diff(
        self,
        state_a: Dict[str, Any],
        state_b: Dict[str, Any],
    ) -> CheckpointDiff:
        """Compute the diff between two state dictionaries.

        Args:
            state_a: First state.
            state_b: Second state.

        Returns:
            CheckpointDiff showing changes.
        """
        keys_a = set(state_a.keys())
        keys_b = set(state_b.keys())

        added = {k: state_b[k] for k in keys_b - keys_a}
        removed = {k: state_a[k] for k in keys_a - keys_b}
        modified = {
            k: (state_a[k], state_b[k])
            for k in keys_a & keys_b
            if state_a[k] != state_b[k]
        }

        return CheckpointDiff(
            added=added,
            removed=removed,
            modified=modified,
        )

    def list_checkpoints(self, workflow_id: str) -> List[Checkpoint]:
        """List all checkpoints for a workflow.

        Args:
            workflow_id: Workflow identifier.

        Returns:
            List of checkpoints.
        """
        return self.storage.list_checkpoints(workflow_id)

    def delete_checkpoint(self, checkpoint_id: str) -> bool:
        """Delete a specific checkpoint.

        Args:
            checkpoint_id: Checkpoint to delete.

        Returns:
            True if deleted, False if not found.
        """
        return self.storage.delete(checkpoint_id)

    def cleanup(
        self,
        workflow_id: Optional[str] = None,
        max_age_seconds: Optional[float] = None,
        keep_latest: Optional[int] = None,
    ) -> int:
        """Clean up old checkpoints.

        Args:
            workflow_id: Optional workflow to clean. If None, applies to all.
            max_age_seconds: Delete checkpoints older than this.
            keep_latest: Keep only the latest N checkpoints per workflow.

        Returns:
            Total number of checkpoints deleted.
        """
        total_deleted = 0

        if max_age_seconds is not None:
            total_deleted += self.storage.cleanup_old_checkpoints(max_age_seconds)

        if keep_latest is not None:
            if workflow_id:
                total_deleted += self.storage.cleanup_keep_latest(workflow_id, keep_latest)
            else:
                # Get all workflow IDs
                workflows = self._get_all_workflow_ids()
                for wf_id in workflows:
                    total_deleted += self.storage.cleanup_keep_latest(wf_id, keep_latest)

        return total_deleted

    def _get_next_version(self, workflow_id: str) -> int:
        """Get the next version number for a workflow.

        Args:
            workflow_id: Workflow identifier.

        Returns:
            Next version number.
        """
        if workflow_id in self._checkpoint_counter:
            self._checkpoint_counter[workflow_id] += 1
            return self._checkpoint_counter[workflow_id]

        # Check storage for existing checkpoints
        checkpoints = self.storage.list_checkpoints(workflow_id)
        if checkpoints:
            max_version = max(cp.version for cp in checkpoints)
            self._checkpoint_counter[workflow_id] = max_version + 1
            return max_version + 1

        self._checkpoint_counter[workflow_id] = 1
        return 1

    def _get_all_workflow_ids(self) -> List[str]:
        """Get all workflow IDs that have checkpoints.

        Returns:
            List of unique workflow IDs.
        """
        # This requires a query that the storage doesn't expose
        # For now, return empty list - would need to add to storage interface
        return []

    def get_checkpoint_history(
        self,
        workflow_id: str,
    ) -> List[Dict[str, Any]]:
        """Get a summary of checkpoint history for a workflow.

        Args:
            workflow_id: Workflow identifier.

        Returns:
            List of checkpoint summaries with diffs from previous.
        """
        checkpoints = self.storage.list_checkpoints(workflow_id)
        history = []

        for i, cp in enumerate(checkpoints):
            entry = {
                "version": cp.version,
                "node_name": cp.node_name,
                "created_at": cp.created_at,
                "path_length": len(cp.execution_path),
            }

            if i > 0:
                diff = self._compute_diff(checkpoints[i - 1].state, cp.state)
                entry["diff_summary"] = {
                    "added": len(diff.added),
                    "removed": len(diff.removed),
                    "modified": len(diff.modified),
                }
            else:
                entry["diff_summary"] = {"added": len(cp.state), "removed": 0, "modified": 0}

            history.append(entry)

        return history
