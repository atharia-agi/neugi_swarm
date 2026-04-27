"""
NEUGI v2 Heartbeat Engine
==========================

DB-backed wakeup queue with coalescing, budget checks, execution locking,
task resume across heartbeats, cron-like scheduling, and missed heartbeat
recovery.

The heartbeat engine ensures that periodic tasks execute reliably even
across process restarts, with no double-work and intelligent merging
of overlapping scheduled executions.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# -- Enums -------------------------------------------------------------------

class HeartbeatState(str, Enum):
    """State of a heartbeat task."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    RESUMING = "resuming"


# -- Data Classes ------------------------------------------------------------

@dataclass
class HeartbeatResult:
    """Result of a heartbeat task execution.

    Attributes:
        task_id: The task that was executed.
        execution_id: Unique identifier for this execution.
        started_at: Unix timestamp when execution started.
        finished_at: Unix timestamp when execution finished.
        state: Final state of the execution.
        error: Error message if execution failed.
        output: Output data from the execution.
        resumed: Whether this execution resumed a previous partial run.
    """
    task_id: str
    execution_id: str
    started_at: float
    finished_at: float
    state: HeartbeatState
    error: str | None = None
    output: Any = None
    resumed: bool = False

    @property
    def duration(self) -> float:
        """Execution duration in seconds."""
        return self.finished_at - self.started_at

    @property
    def success(self) -> bool:
        """Whether the execution was successful."""
        return self.state in (HeartbeatState.COMPLETED, HeartbeatState.SKIPPED)


@dataclass
class HeartbeatTask:
    """A scheduled heartbeat task.

    Attributes:
        task_id: Unique task identifier.
        name: Human-readable task name.
        interval_seconds: Seconds between executions.
        handler: Callable to execute on heartbeat.
        state: Current task state.
        budget_check: Optional callable to check if execution is allowed.
        max_retries: Maximum retries on failure (0 = no retries).
        retry_count: Current retry count.
        last_run_at: Unix timestamp of last execution.
        next_run_at: Unix timestamp of next scheduled execution.
        last_result: Result of the last execution.
        resume_state: Persisted state for resuming across heartbeats.
        coalesce_key: Key for coalescing overlapping tasks.
        created_at: Unix timestamp of creation.
        metadata: Arbitrary task metadata.
    """
    task_id: str
    name: str
    interval_seconds: float
    handler: Callable[..., Any]
    state: HeartbeatState = HeartbeatState.PENDING
    budget_check: Callable[[], bool] | None = None
    max_retries: int = 3
    retry_count: int = 0
    last_run_at: float = 0.0
    next_run_at: float = 0.0
    last_result: HeartbeatResult | None = None
    resume_state: dict[str, Any] = field(default_factory=dict)
    coalesce_key: str = ""
    created_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize task to a dictionary (excludes handler)."""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "interval_seconds": self.interval_seconds,
            "state": self.state.value,
            "max_retries": self.max_retries,
            "retry_count": self.retry_count,
            "last_run_at": self.last_run_at,
            "next_run_at": self.next_run_at,
            "coalesce_key": self.coalesce_key,
            "created_at": self.created_at,
            "resume_state": self.resume_state,
            "metadata": self.metadata,
        }


# -- Exceptions --------------------------------------------------------------

class HeartbeatError(Exception):
    """Base exception for heartbeat engine errors."""

    def __init__(self, message: str, task_id: str | None = None) -> None:
        self.task_id = task_id
        super().__init__(message)


class HeartbeatTaskNotFoundError(HeartbeatError):
    """Raised when a heartbeat task is not found."""
    pass


class HeartbeatTaskAlreadyExistsError(HeartbeatError):
    """Raised when attempting to register a duplicate task ID."""
    pass


class HeartbeatBudgetExceededError(HeartbeatError):
    """Raised when a budget check prevents execution."""
    pass


class HeartbeatExecutionLockedError(HeartbeatError):
    """Raised when a task is already executing (double-work prevention)."""
    pass


# -- Wakeup Queue ------------------------------------------------------------

class WakeupQueue:
    """Database-backed wakeup queue with coalescing support.

    Stores pending heartbeat executions and merges overlapping tasks
    based on coalesce keys.

    Attributes:
        db_path: Path to the SQLite database file.
        _lock: Lock for thread safety.
    """

    def __init__(self, db_path: str | Path) -> None:
        """Initialize the wakeup queue.

        Args:
            db_path: Path to SQLite database.
        """
        self.db_path = str(db_path)
        self._lock = threading.Lock()
        self._init_db()

    def _init_db(self) -> None:
        """Initialize the database schema."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS wakeup_queue (
                    queue_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL,
                    coalesce_key TEXT NOT NULL DEFAULT '',
                    scheduled_at REAL NOT NULL,
                    state TEXT NOT NULL DEFAULT 'pending',
                    priority INTEGER NOT NULL DEFAULT 0,
                    payload TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL
                );

                CREATE INDEX IF NOT EXISTS idx_wakeup_task
                    ON wakeup_queue(task_id);

                CREATE INDEX IF NOT EXISTS idx_wakeup_scheduled
                    ON wakeup_queue(scheduled_at);

                CREATE INDEX IF NOT EXISTS idx_wakeup_coalesce
                    ON wakeup_queue(coalesce_key);
            """)

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def enqueue(
        self,
        task_id: str,
        scheduled_at: float,
        coalesce_key: str = "",
        priority: int = 0,
        payload: dict[str, Any] | None = None,
    ) -> str:
        """Add a task to the wakeup queue.

        If a task with the same coalesce key is already pending, the
        existing entry is updated instead of creating a duplicate.

        Args:
            task_id: The task to enqueue.
            scheduled_at: Unix timestamp when the task should run.
            coalesce_key: Key for coalescing (empty = no coalescing).
            priority: Execution priority (higher = sooner).
            payload: Arbitrary payload data.

        Returns:
            The queue entry ID.
        """
        payload = payload or {}
        queue_id = str(uuid.uuid4())

        with self._lock:
            with self._get_conn() as conn:
                if coalesce_key:
                    existing = conn.execute(
                        """SELECT queue_id FROM wakeup_queue
                           WHERE coalesce_key = ? AND state = 'pending'""",
                        (coalesce_key,),
                    ).fetchone()

                    if existing:
                        conn.execute(
                            """UPDATE wakeup_queue
                               SET scheduled_at = ?, priority = ?, payload = ?
                               WHERE queue_id = ?""",
                            (
                                scheduled_at, priority,
                                json.dumps(payload), existing["queue_id"],
                            ),
                        )
                        return existing["queue_id"]

                conn.execute(
                    """INSERT INTO wakeup_queue
                       (queue_id, task_id, coalesce_key, scheduled_at,
                        state, priority, payload, created_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        queue_id, task_id, coalesce_key, scheduled_at,
                        HeartbeatState.PENDING.value, priority,
                        json.dumps(payload), time.time(),
                    ),
                )

        return queue_id

    def dequeue(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get pending tasks that are due to run.

        Args:
            limit: Maximum number of tasks to dequeue.

        Returns:
            List of pending queue entries with their data.
        """
        now = time.time()

        with self._lock:
            with self._get_conn() as conn:
                rows = conn.execute(
                    """SELECT * FROM wakeup_queue
                       WHERE state = 'pending' AND scheduled_at <= ?
                       ORDER BY priority DESC, scheduled_at ASC
                       LIMIT ?""",
                    (now, limit),
                ).fetchall()

                entries = []
                for row in rows:
                    conn.execute(
                        "UPDATE wakeup_queue SET state = 'queued' WHERE queue_id = ?",
                        (row["queue_id"],),
                    )
                    entries.append({
                        "queue_id": row["queue_id"],
                        "task_id": row["task_id"],
                        "coalesce_key": row["coalesce_key"],
                        "scheduled_at": row["scheduled_at"],
                        "priority": row["priority"],
                        "payload": json.loads(row["payload"]),
                    })

                return entries

    def complete(self, queue_id: str) -> None:
        """Mark a queue entry as completed.

        Args:
            queue_id: The queue entry to complete.
        """
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    "DELETE FROM wakeup_queue WHERE queue_id = ?",
                    (queue_id,),
                )

    def fail(self, queue_id: str) -> None:
        """Mark a queue entry as failed.

        Args:
            queue_id: The queue entry to fail.
        """
        with self._lock:
            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE wakeup_queue SET state = 'failed' WHERE queue_id = ?",
                    (queue_id,),
                )

    def clear_pending(self, task_id: str | None = None) -> int:
        """Clear pending entries from the queue.

        Args:
            task_id: If provided, only clear entries for this task.

        Returns:
            Number of entries cleared.
        """
        with self._lock:
            with self._get_conn() as conn:
                if task_id:
                    result = conn.execute(
                        "DELETE FROM wakeup_queue WHERE task_id = ? AND state = 'pending'",
                        (task_id,),
                    )
                else:
                    result = conn.execute(
                        "DELETE FROM wakeup_queue WHERE state = 'pending'",
                    )
                return result.rowcount

    def get_pending_count(self, task_id: str | None = None) -> int:
        """Get the number of pending entries.

        Args:
            task_id: If provided, count only entries for this task.

        Returns:
            Number of pending entries.
        """
        with self._lock:
            with self._get_conn() as conn:
                if task_id:
                    row = conn.execute(
                        "SELECT COUNT(*) as cnt FROM wakeup_queue WHERE task_id = ? AND state = 'pending'",
                        (task_id,),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT COUNT(*) as cnt FROM wakeup_queue WHERE state = 'pending'",
                    ).fetchone()
                return row["cnt"]


# -- Heartbeat Engine --------------------------------------------------------

class HeartbeatEngine:
    """Executes heartbeat tasks with reliability guarantees.

    Provides DB-backed wakeup queue, coalescing of overlapping heartbeats,
    budget checks before execution, execution lock (no double-work),
    task resume across heartbeats, cron-like scheduling, and missed
    heartbeat recovery.

    All operations are thread-safe via a reentrant lock.

    Attributes:
        db_path: Path to the SQLite database file.
        wakeup_queue: The backing wakeup queue.
        _lock: Reentrant lock for thread safety.
        _tasks: In-memory map of task_id -> HeartbeatTask.
        _executing: Set of currently executing task IDs (execution lock).
    """

    def __init__(self, db_path: str | Path) -> None:
        """Initialize the heartbeat engine.

        Args:
            db_path: Path to SQLite database for task persistence.
        """
        self.db_path = str(db_path)
        self.wakeup_queue = WakeupQueue(db_path)
        self._lock = threading.RLock()
        self._tasks: dict[str, HeartbeatTask] = {}
        self._executing: set[str] = set()
        self._init_db()
        self._recover_missed_heartbeats()
        logger.info("HeartbeatEngine initialized")

    def _init_db(self) -> None:
        """Initialize the SQLite database schema."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS heartbeat_tasks (
                    task_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    interval_seconds REAL NOT NULL,
                    state TEXT NOT NULL DEFAULT 'pending',
                    budget_check_name TEXT,
                    max_retries INTEGER NOT NULL DEFAULT 3,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    last_run_at REAL NOT NULL DEFAULT 0,
                    next_run_at REAL NOT NULL DEFAULT 0,
                    coalesce_key TEXT NOT NULL DEFAULT '',
                    resume_state TEXT NOT NULL DEFAULT '{}',
                    created_at REAL NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS heartbeat_results (
                    execution_id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES heartbeat_tasks(task_id),
                    started_at REAL NOT NULL,
                    finished_at REAL NOT NULL,
                    state TEXT NOT NULL,
                    error TEXT,
                    output TEXT,
                    resumed INTEGER NOT NULL DEFAULT 0
                );

                CREATE INDEX IF NOT EXISTS idx_results_task
                    ON heartbeat_results(task_id);
            """)

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # -- Task Registration ---------------------------------------------------

    def register_task(
        self,
        name: str,
        interval_seconds: float,
        handler: Callable[..., Any],
        task_id: str | None = None,
        budget_check: Callable[[], bool] | None = None,
        max_retries: int = 3,
        coalesce_key: str = "",
        initial_state: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> HeartbeatTask:
        """Register a new heartbeat task.

        Args:
            name: Human-readable task name.
            interval_seconds: Seconds between executions.
            handler: Callable to execute on heartbeat.
            task_id: Unique task ID (auto-generated if None).
            budget_check: Optional callable returning True if execution is allowed.
            max_retries: Maximum retries on failure.
            coalesce_key: Key for coalescing overlapping executions.
            initial_state: Initial resume state for the task.
            metadata: Arbitrary task metadata.

        Returns:
            The registered HeartbeatTask.

        Raises:
            HeartbeatTaskAlreadyExistsError: If task_id already exists.
        """
        task_id = task_id or str(uuid.uuid4())
        initial_state = initial_state or {}
        metadata = metadata or {}
        now = time.time()

        task = HeartbeatTask(
            task_id=task_id,
            name=name,
            interval_seconds=interval_seconds,
            handler=handler,
            state=HeartbeatState.PENDING,
            budget_check=budget_check,
            max_retries=max_retries,
            next_run_at=now + interval_seconds,
            resume_state=initial_state,
            coalesce_key=coalesce_key or task_id,
            created_at=now,
            metadata=metadata,
        )

        with self._lock:
            if task_id in self._tasks:
                raise HeartbeatTaskAlreadyExistsError(
                    f"Task '{task_id}' already exists", task_id
                )

            self._tasks[task_id] = task

            with self._get_conn() as conn:
                conn.execute(
                    """INSERT INTO heartbeat_tasks
                       (task_id, name, interval_seconds, state, max_retries,
                        next_run_at, coalesce_key, resume_state, created_at, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        task_id, name, interval_seconds,
                        HeartbeatState.PENDING.value, max_retries,
                        task.next_run_at, task.coalesce_key,
                        json.dumps(initial_state), now, json.dumps(metadata),
                    ),
                )

            self.wakeup_queue.enqueue(
                task_id=task_id,
                scheduled_at=task.next_run_at,
                coalesce_key=task.coalesce_key,
            )

        logger.info(
            "Heartbeat task registered: %s (interval=%ds)",
            name, interval_seconds,
        )
        return task

    # -- Task Management -----------------------------------------------------

    def get_task(self, task_id: str) -> HeartbeatTask:
        """Get a heartbeat task by ID.

        Args:
            task_id: The task identifier.

        Returns:
            The HeartbeatTask.

        Raises:
            HeartbeatTaskNotFoundError: If not found.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise HeartbeatTaskNotFoundError(
                    f"Task '{task_id}' not found", task_id
                )
            return task

    def list_tasks(
        self,
        state: HeartbeatState | None = None,
    ) -> list[HeartbeatTask]:
        """List all registered tasks with optional state filter.

        Args:
            state: Filter by task state.

        Returns:
            List of matching HeartbeatTask objects.
        """
        with self._lock:
            tasks = list(self._tasks.values())
            if state:
                tasks = [t for t in tasks if t.state == state]
            return tasks

    def pause_task(self, task_id: str) -> HeartbeatTask:
        """Pause a task — it will not execute until resumed.

        Args:
            task_id: The task to pause.

        Returns:
            The updated HeartbeatTask.
        """
        return self._set_task_state(task_id, HeartbeatState.FAILED)

    def resume_task(self, task_id: str) -> HeartbeatTask:
        """Resume a paused task.

        Args:
            task_id: The task to resume.

        Returns:
            The updated HeartbeatTask.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise HeartbeatTaskNotFoundError(
                    f"Task '{task_id}' not found", task_id
                )

            task.state = HeartbeatState.PENDING
            task.next_run_at = time.time() + task.interval_seconds

            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE heartbeat_tasks SET state = ?, next_run_at = ? WHERE task_id = ?",
                    (HeartbeatState.PENDING.value, task.next_run_at, task_id),
                )

            self.wakeup_queue.enqueue(
                task_id=task_id,
                scheduled_at=task.next_run_at,
                coalesce_key=task.coalesce_key,
            )

        return task

    def delete_task(self, task_id: str) -> None:
        """Permanently delete a heartbeat task.

        Args:
            task_id: The task to delete.

        Raises:
            HeartbeatTaskNotFoundError: If not found.
        """
        with self._lock:
            if task_id not in self._tasks:
                raise HeartbeatTaskNotFoundError(
                    f"Task '{task_id}' not found", task_id
                )

            del self._tasks[task_id]
            self.wakeup_queue.clear_pending(task_id)

            with self._get_conn() as conn:
                conn.execute(
                    "DELETE FROM heartbeat_results WHERE task_id = ?",
                    (task_id,),
                )
                conn.execute(
                    "DELETE FROM heartbeat_tasks WHERE task_id = ?",
                    (task_id,),
                )

        logger.info("Heartbeat task deleted: %s", task_id[:8])

    def update_task_state(self, task_id: str, state: dict[str, Any]) -> None:
        """Update the persisted resume state for a task.

        Allows a task to save partial progress that will be available
        if the task is resumed after a restart.

        Args:
            task_id: The task to update state for.
            state: New state dictionary to persist.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                return

            task.resume_state = state

            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE heartbeat_tasks SET resume_state = ? WHERE task_id = ?",
                    (json.dumps(state), task_id),
                )

    # -- Execution -----------------------------------------------------------

    def tick(self) -> list[HeartbeatResult]:
        """Execute all due heartbeat tasks.

        This is the main execution method — call it on each heartbeat
        interval to process the wakeup queue.

        Returns:
            List of HeartbeatResult objects for executed tasks.
        """
        results: list[HeartbeatResult] = []
        due_entries = self.wakeup_queue.dequeue(limit=50)

        for entry in due_entries:
            task_id = entry["task_id"]
            queue_id = entry["queue_id"]

            try:
                result = self._execute_task(task_id, queue_id, entry["payload"])
                results.append(result)
            except HeartbeatError as e:
                logger.warning("Heartbeat tick failed for %s: %s", task_id, e)
                self.wakeup_queue.fail(queue_id)
            except Exception as e:
                logger.error("Unexpected heartbeat error for %s: %s", task_id, e)
                self.wakeup_queue.fail(queue_id)

        return results

    def execute_task(
        self,
        task_id: str,
        *args: Any,
        **kwargs: Any,
    ) -> HeartbeatResult:
        """Execute a specific task immediately.

        Args:
            task_id: The task to execute.
            *args: Positional arguments to pass to the handler.
            **kwargs: Keyword arguments to pass to the handler.

        Returns:
            HeartbeatResult with execution details.

        Raises:
            HeartbeatTaskNotFoundError: If not found.
            HeartbeatExecutionLockedError: If task is already running.
            HeartbeatBudgetExceededError: If budget check fails.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                raise HeartbeatTaskNotFoundError(
                    f"Task '{task_id}' not found", task_id
                )

            if task_id in self._executing:
                raise HeartbeatExecutionLockedError(
                    f"Task '{task_id}' is already executing", task_id
                )

            if task.budget_check and not task.budget_check():
                raise HeartbeatBudgetExceededError(
                    f"Budget check failed for task '{task_id}'", task_id
                )

            self._executing.add(task_id)

        execution_id = f"{task_id}:{uuid.uuid4().hex[:8]}"
        started_at = time.time()
        resumed = bool(task.resume_state)

        try:
            output = task.handler(*args, **kwargs)
            finished_at = time.time()
            state = HeartbeatState.COMPLETED
            error = None
            task.retry_count = 0

        except Exception as e:
            finished_at = time.time()
            state = HeartbeatState.FAILED
            error = str(e)
            output = None
            task.retry_count += 1
            logger.error("Heartbeat task %s failed: %s", task_id, error)

        result = HeartbeatResult(
            task_id=task_id,
            execution_id=execution_id,
            started_at=started_at,
            finished_at=finished_at,
            state=state,
            error=error,
            output=output,
            resumed=resumed,
        )

        self._record_result(task_id, result)

        with self._lock:
            self._executing.discard(task_id)

            task = self._tasks.get(task_id)
            if task:
                task.last_run_at = finished_at
                task.next_run_at = finished_at + task.interval_seconds
                task.state = state
                task.last_result = result

                with self._get_conn() as conn:
                    conn.execute(
                        """UPDATE heartbeat_tasks
                           SET last_run_at = ?, next_run_at = ?, state = ?,
                               retry_count = ?
                           WHERE task_id = ?""",
                        (
                            task.last_run_at, task.next_run_at,
                            state.value, task.retry_count, task_id,
                        ),
                    )

                if state == HeartbeatState.COMPLETED:
                    task.resume_state = {}
                    with self._get_conn() as conn:
                        conn.execute(
                            "UPDATE heartbeat_tasks SET resume_state = '{}' WHERE task_id = ?",
                            (task_id,),
                        )

                self.wakeup_queue.enqueue(
                    task_id=task_id,
                    scheduled_at=task.next_run_at,
                    coalesce_key=task.coalesce_key,
                )

        return result

    def _execute_task(
        self,
        task_id: str,
        queue_id: str,
        payload: dict[str, Any],
    ) -> HeartbeatResult:
        """Execute a task from the wakeup queue.

        Args:
            task_id: The task to execute.
            queue_id: The queue entry ID.
            payload: Payload data from the queue entry.

        Returns:
            HeartbeatResult with execution details.
        """
        with self._lock:
            task = self._tasks.get(task_id)
            if task is None:
                self.wakeup_queue.complete(queue_id)
                raise HeartbeatTaskNotFoundError(
                    f"Task '{task_id}' not found", task_id
                )

            if task_id in self._executing:
                self.wakeup_queue.fail(queue_id)
                raise HeartbeatExecutionLockedError(
                    f"Task '{task_id}' is already executing", task_id
                )

            if task.budget_check and not task.budget_check():
                self.wakeup_queue.complete(queue_id)
                result = HeartbeatResult(
                    task_id=task_id,
                    execution_id=f"{task_id}:{uuid.uuid4().hex[:8]}",
                    started_at=time.time(),
                    finished_at=time.time(),
                    state=HeartbeatState.SKIPPED,
                    error="Budget check failed",
                )
                return result

            self._executing.add(task_id)
            task.state = HeartbeatState.RUNNING

        execution_id = f"{task_id}:{uuid.uuid4().hex[:8]}"
        started_at = time.time()
        resumed = bool(task.resume_state)

        try:
            output = task.handler()
            finished_at = time.time()
            state = HeartbeatState.COMPLETED
            error = None
            task.retry_count = 0

        except Exception as e:
            finished_at = time.time()
            state = HeartbeatState.FAILED
            error = str(e)
            output = None
            task.retry_count += 1
            logger.error("Heartbeat task %s failed: %s", task_id, error)

        result = HeartbeatResult(
            task_id=task_id,
            execution_id=execution_id,
            started_at=started_at,
            finished_at=finished_at,
            state=state,
            error=error,
            output=output,
            resumed=resumed,
        )

        self._record_result(task_id, result)

        with self._lock:
            self._executing.discard(task_id)
            self.wakeup_queue.complete(queue_id)

            task = self._tasks.get(task_id)
            if task:
                task.last_run_at = finished_at
                task.next_run_at = finished_at + task.interval_seconds
                task.state = state
                task.last_result = result

                if state == HeartbeatState.COMPLETED:
                    task.resume_state = {}

                with self._get_conn() as conn:
                    conn.execute(
                        """UPDATE heartbeat_tasks
                           SET last_run_at = ?, next_run_at = ?, state = ?,
                               retry_count = ?, resume_state = ?
                           WHERE task_id = ?""",
                        (
                            task.last_run_at, task.next_run_at,
                            state.value, task.retry_count,
                            json.dumps(task.resume_state), task_id,
                        ),
                    )

                if task.retry_count < task.max_retries:
                    retry_delay = task.interval_seconds * (2 ** task.retry_count)
                    self.wakeup_queue.enqueue(
                        task_id=task_id,
                        scheduled_at=time.time() + retry_delay,
                        coalesce_key=task.coalesce_key,
                        priority=10,
                    )
                else:
                    logger.warning(
                        "Task %s exhausted retries (%d)", task_id, task.max_retries
                    )

        return result

    # -- Recovery ------------------------------------------------------------

    def _recover_missed_heartbeats(self) -> int:
        """Recover tasks that missed their heartbeat during downtime.

        Scans persisted tasks and re-queues any that are overdue.

        Returns:
            Number of tasks recovered.
        """
        recovered = 0
        now = time.time()

        with self._lock:
            with self._get_conn() as conn:
                rows = conn.execute(
                    """SELECT * FROM heartbeat_tasks
                       WHERE next_run_at <= ? AND state != 'failed'""",
                    (now,),
                ).fetchall()

                for row in rows:
                    task_id = row["task_id"]
                    resume_state = json.loads(row["resume_state"])

                    if task_id in self._tasks:
                        task = self._tasks[task_id]
                        task.resume_state = resume_state
                        task.state = HeartbeatState.RESUMING

                    self.wakeup_queue.enqueue(
                        task_id=task_id,
                        scheduled_at=now,
                        coalesce_key=row["coalesce_key"],
                        priority=5,
                    )
                    recovered += 1

        if recovered:
            logger.info("Recovered %d missed heartbeat tasks", recovered)

        return recovered

    # -- History -------------------------------------------------------------

    def get_task_history(
        self,
        task_id: str,
        limit: int = 50,
    ) -> list[HeartbeatResult]:
        """Get execution history for a task.

        Args:
            task_id: The task to get history for.
            limit: Maximum number of entries to return.

        Returns:
            List of HeartbeatResult objects, newest first.
        """
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM heartbeat_results
                   WHERE task_id = ?
                   ORDER BY started_at DESC
                   LIMIT ?""",
                (task_id, limit),
            ).fetchall()

            return [
                HeartbeatResult(
                    task_id=row["task_id"],
                    execution_id=row["execution_id"],
                    started_at=row["started_at"],
                    finished_at=row["finished_at"],
                    state=HeartbeatState(row["state"]),
                    error=row["error"],
                    output=json.loads(row["output"]) if row["output"] else None,
                    resumed=bool(row["resumed"]),
                )
                for row in rows
            ]

    def _record_result(self, task_id: str, result: HeartbeatResult) -> None:
        """Persist an execution result to the database.

        Args:
            task_id: The task that was executed.
            result: The execution result.
        """
        output_json = None
        if result.output is not None:
            try:
                output_json = json.dumps(result.output)
            except (TypeError, ValueError):
                output_json = json.dumps({"_raw": str(result.output)})

        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO heartbeat_results
                   (execution_id, task_id, started_at, finished_at,
                    state, error, output, resumed)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.execution_id, task_id,
                    result.started_at, result.finished_at,
                    result.state.value, result.error,
                    output_json, int(result.resumed),
                ),
            )

    # -- Utility -------------------------------------------------------------

    def get_next_run_time(self, task_id: str) -> float | None:
        """Get the next scheduled run time for a task.

        Args:
            task_id: The task to query.

        Returns:
            Unix timestamp of next run, or None if not found.
        """
        task = self._tasks.get(task_id)
        return task.next_run_at if task else None

    def get_task_stats(self) -> dict[str, Any]:
        """Get aggregate statistics for all tasks.

        Returns:
            Dictionary with task counts by state and other metrics.
        """
        with self._lock:
            stats: dict[str, int] = {}
            for task in self._tasks.values():
                state_key = task.state.value
                stats[state_key] = stats.get(state_key, 0) + 1

            stats["total"] = len(self._tasks)
            stats["executing"] = len(self._executing)
            stats["pending_queue"] = self.wakeup_queue.get_pending_count()

            return stats

    def close(self) -> None:
        """Shut down the heartbeat engine."""
        with self._lock:
            self._tasks.clear()
            self._executing.clear()

        logger.info("HeartbeatEngine shut down")
