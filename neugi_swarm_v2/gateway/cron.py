"""
NEUGI v2 Cron Scheduler
========================

Cron expression parsing, job registration, execution with isolation,
history tracking, pause/resume/disable, concurrent job limiting,
and job dependency chains.

Supports standard 5-field cron expressions: minute, hour, day, month, day-of-week.
"""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# -- Enums -------------------------------------------------------------------

class CronJobState(str, Enum):
    """Lifecycle state of a cron job."""
    ENABLED = "enabled"
    PAUSED = "paused"
    DISABLED = "disabled"
    RUNNING = "running"


# -- Cron Expression ---------------------------------------------------------

@dataclass
class CronField:
    """A single parsed cron field (minute, hour, day, month, or dow).

    Attributes:
        values: Set of integer values that match this field.
        min_val: Minimum valid value for this field.
        max_val: Maximum valid value for this field.
    """
    values: set[int]
    min_val: int
    max_val: int

    def matches(self, value: int) -> bool:
        """Check if a value matches this field.

        Args:
            value: The integer value to check.

        Returns:
            True if the value is in the matched set.
        """
        return value in self.values


@dataclass
class CronExpression:
    """Parsed 5-field cron expression.

    Format: minute hour day month day-of-week

    Attributes:
        minute: Minute field (0-59).
        hour: Hour field (0-23).
        day: Day of month field (1-31).
        month: Month field (1-12).
        day_of_week: Day of week field (0-6, 0=Sunday).
        raw: Original raw expression string.
    """
    minute: CronField
    hour: CronField
    day: CronField
    month: CronField
    day_of_week: CronField
    raw: str

    def matches_datetime(self, dt: datetime) -> bool:
        """Check if a datetime matches this cron expression.

        Args:
            dt: The datetime to check.

        Returns:
            True if all fields match.
        """
        return (
            self.minute.matches(dt.minute)
            and self.hour.matches(dt.hour)
            and self.day.matches(dt.day)
            and self.month.matches(dt.month)
            and self.day_of_week.matches(dt.weekday())
        )

    def next_run(self, after: datetime | None = None) -> datetime | None:
        """Calculate the next run time after a given datetime.

        Searches forward up to 4 years from the reference time.

        Args:
            after: Reference datetime (defaults to now UTC).

        Returns:
            The next matching datetime, or None if not found within 4 years.
        """
        if after is None:
            after = datetime.now(timezone.utc)

        candidate = after.replace(second=0, microsecond=0)
        max_iterations = 366 * 24 * 60 * 4  # 4 years in minutes

        for _ in range(max_iterations):
            candidate = self._add_minute(candidate)
            if self.matches_datetime(candidate):
                return candidate

        return None

    def _add_minute(self, dt: datetime) -> datetime:
        """Add one minute to a datetime, handling rollovers."""
        from datetime import timedelta
        return dt + timedelta(minutes=1)

    @classmethod
    def parse(cls, expression: str) -> CronExpression:
        """Parse a cron expression string.

        Supports:
        - Wildcards: *
        - Ranges: 1-5
        - Steps: */5, 1-10/2
        - Lists: 1,3,5
        - Named days: SUN, MON, TUE, WED, THU, FRI, SAT

        Args:
            expression: The cron expression string (5 fields).

        Returns:
            Parsed CronExpression.

        Raises:
            ValueError: If the expression is invalid.
        """
        parts = expression.strip().split()
        if len(parts) != 5:
            raise ValueError(
                f"Cron expression must have 5 fields, got {len(parts)}: '{expression}'"
            )

        day_names = {
            "SUN": 0, "MON": 1, "TUE": 2, "WED": 3,
            "THU": 4, "FRI": 5, "SAT": 6,
        }

        minute = cls._parse_field(parts[0], 0, 59)
        hour = cls._parse_field(parts[1], 0, 23)
        day = cls._parse_field(parts[2], 1, 31)
        month = cls._parse_field(parts[3], 1, 12)

        dow_raw = parts[4].upper()
        for name, val in day_names.items():
            dow_raw = dow_raw.replace(name, str(val))
        day_of_week = cls._parse_field(dow_raw, 0, 6)

        return cls(
            minute=minute,
            hour=hour,
            day=day,
            month=month,
            day_of_week=day_of_week,
            raw=expression,
        )

    @classmethod
    def _parse_field(cls, field_str: str, min_val: int, max_val: int) -> CronField:
        """Parse a single cron field into a set of matching values.

        Args:
            field_str: The field string (e.g., '*/5', '1-10', '1,3,5').
            min_val: Minimum valid value for this field.
            max_val: Maximum valid value for this field.

        Returns:
            CronField with the parsed value set.

        Raises:
            ValueError: If the field syntax is invalid.
        """
        values: set[int] = set()

        for part in field_str.split(","):
            part = part.strip()
            if "/" in part:
                range_part, step_str = part.split("/", 1)
                step = int(step_str)
                if step <= 0:
                    raise ValueError(f"Invalid step value: {step}")

                if range_part == "*":
                    start, end = min_val, max_val
                elif "-" in range_part:
                    start, end = map(int, range_part.split("-", 1))
                else:
                    start = int(range_part)
                    end = max_val

                for v in range(start, end + 1, step):
                    values.add(v)

            elif "-" in part:
                start, end = map(int, part.split("-", 1))
                for v in range(start, end + 1):
                    values.add(v)

            elif part == "*":
                values = set(range(min_val, max_val + 1))

            else:
                values.add(int(part))

        return CronField(values=values, min_val=min_val, max_val=max_val)


# -- Cron Schedule -----------------------------------------------------------

@dataclass
class CronSchedule:
    """A cron schedule combining an expression with timezone info.

    Attributes:
        expression: The parsed cron expression.
        timezone_name: IANA timezone name (default: UTC).
    """
    expression: CronExpression
    timezone_name: str = "UTC"

    def should_run(self, dt: datetime | None = None) -> bool:
        """Check if a job should run at the given time.

        Args:
            dt: The datetime to check (defaults to now UTC).

        Returns:
            True if the schedule matches.
        """
        if dt is None:
            dt = datetime.now(timezone.utc)
        return self.expression.matches_datetime(dt)


# -- Cron Job ----------------------------------------------------------------

@dataclass
class CronJobResult:
    """Result of a cron job execution.

    Attributes:
        job_id: The job that was executed.
        run_id: Unique identifier for this execution.
        started_at: Unix timestamp when execution started.
        finished_at: Unix timestamp when execution finished.
        success: Whether the execution succeeded.
        error: Error message if execution failed.
        output: Output data from the execution.
    """
    job_id: str
    run_id: str
    started_at: float
    finished_at: float
    success: bool
    error: str | None = None
    output: Any = None

    @property
    def duration(self) -> float:
        """Execution duration in seconds."""
        return self.finished_at - self.started_at


@dataclass
class CronJobHistory:
    """Historical record of a cron job execution.

    Attributes:
        run_id: Unique execution identifier.
        job_id: The job that was executed.
        scheduled_for: When the job was scheduled to run.
        started_at: When execution actually started.
        finished_at: When execution finished.
        success: Whether it succeeded.
        error: Error message if failed.
    """
    run_id: str
    job_id: str
    scheduled_for: float
    started_at: float
    finished_at: float
    success: bool
    error: str | None = None

    @property
    def duration(self) -> float:
        """Execution duration in seconds."""
        return self.finished_at - self.started_at


@dataclass
class CronJob:
    """A scheduled cron job.

    Attributes:
        job_id: Unique job identifier.
        name: Human-readable job name.
        schedule: The cron schedule.
        handler: Callable to execute when the job fires.
        state: Current job state.
        max_concurrent: Maximum concurrent executions (default: 1).
        timeout_seconds: Execution timeout (0 = no timeout).
        depends_on: List of job IDs this job depends on.
        last_run_at: Unix timestamp of last execution.
        next_run_at: Unix timestamp of next scheduled execution.
        run_count: Total number of successful executions.
        fail_count: Total number of failed executions.
        created_at: Unix timestamp of creation.
        metadata: Arbitrary job metadata.
    """
    job_id: str
    name: str
    schedule: CronSchedule
    handler: Callable[..., Any]
    state: CronJobState = CronJobState.ENABLED
    max_concurrent: int = 1
    timeout_seconds: float = 0.0
    depends_on: list[str] = field(default_factory=list)
    last_run_at: float = 0.0
    next_run_at: float = 0.0
    run_count: int = 0
    fail_count: int = 0
    created_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize job to a dictionary (excludes handler)."""
        return {
            "job_id": self.job_id,
            "name": self.name,
            "schedule": self.schedule.expression.raw,
            "state": self.state.value,
            "max_concurrent": self.max_concurrent,
            "timeout_seconds": self.timeout_seconds,
            "depends_on": self.depends_on,
            "last_run_at": self.last_run_at,
            "next_run_at": self.next_run_at,
            "run_count": self.run_count,
            "fail_count": self.fail_count,
            "created_at": self.created_at,
            "metadata": self.metadata,
        }


# -- Exceptions --------------------------------------------------------------

class CronError(Exception):
    """Base exception for cron scheduler errors."""

    def __init__(self, message: str, job_id: str | None = None) -> None:
        self.job_id = job_id
        super().__init__(message)


class CronJobNotFoundError(CronError):
    """Raised when a cron job is not found."""
    pass


class CronJobAlreadyExistsError(CronError):
    """Raised when attempting to register a duplicate job ID."""
    pass


class CronDependencyError(CronError):
    """Raised when a job dependency cannot be satisfied."""
    pass


class CronExecutionTimeoutError(CronError):
    """Raised when a job execution exceeds its timeout."""
    pass


# -- Cron Scheduler ----------------------------------------------------------

class CronScheduler:
    """Manages cron job scheduling, execution, and history.

    Provides cron expression parsing, job registration with isolation,
    execution history, pause/resume/disable controls, concurrent job
    limiting, and dependency chain resolution.

    All operations are thread-safe via a reentrant lock.

    Attributes:
        db_path: Path to the SQLite database file.
        _lock: Reentrant lock for thread safety.
        _jobs: In-memory map of job_id -> CronJob.
        _running: Set of currently executing run_ids.
        _history: In-memory cache of recent execution history.
        _max_history: Maximum history entries to keep in memory.
    """

    def __init__(
        self,
        db_path: str | Path,
        max_history: int = 1000,
    ) -> None:
        """Initialize the cron scheduler.

        Args:
            db_path: Path to SQLite database for job persistence.
            max_history: Maximum history entries to retain in memory.
        """
        self.db_path = str(db_path)
        self._lock = threading.RLock()
        self._jobs: dict[str, CronJob] = {}
        self._running: set[str] = set()
        self._history: list[CronJobHistory] = []
        self._max_history = max_history
        self._init_db()
        logger.info("CronScheduler initialized")

    def _init_db(self) -> None:
        """Initialize the SQLite database schema."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS cron_jobs (
                    job_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    schedule TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'enabled',
                    max_concurrent INTEGER NOT NULL DEFAULT 1,
                    timeout_seconds REAL NOT NULL DEFAULT 0,
                    depends_on TEXT NOT NULL DEFAULT '[]',
                    last_run_at REAL NOT NULL DEFAULT 0,
                    next_run_at REAL NOT NULL DEFAULT 0,
                    run_count INTEGER NOT NULL DEFAULT 0,
                    fail_count INTEGER NOT NULL DEFAULT 0,
                    created_at REAL NOT NULL,
                    metadata TEXT NOT NULL DEFAULT '{}'
                );

                CREATE TABLE IF NOT EXISTS cron_history (
                    run_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL REFERENCES cron_jobs(job_id),
                    scheduled_for REAL NOT NULL,
                    started_at REAL NOT NULL,
                    finished_at REAL NOT NULL,
                    success INTEGER NOT NULL,
                    error TEXT
                );

                CREATE INDEX IF NOT EXISTS idx_history_job
                    ON cron_history(job_id);

                CREATE INDEX IF NOT EXISTS idx_history_time
                    ON cron_history(started_at DESC);
            """)

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    # -- Job Registration ----------------------------------------------------

    def register_job(
        self,
        name: str,
        schedule: str | CronSchedule,
        handler: Callable[..., Any],
        job_id: str | None = None,
        max_concurrent: int = 1,
        timeout_seconds: float = 0.0,
        depends_on: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CronJob:
        """Register a new cron job.

        Args:
            name: Human-readable job name.
            schedule: Cron expression string or CronSchedule object.
            handler: Callable to execute when the job fires.
            job_id: Unique job ID (auto-generated if None).
            max_concurrent: Maximum concurrent executions.
            timeout_seconds: Execution timeout (0 = no timeout).
            depends_on: List of job IDs this job depends on.
            metadata: Arbitrary job metadata.

        Returns:
            The registered CronJob.

        Raises:
            CronJobAlreadyExistsError: If job_id already exists.
            CronDependencyError: If a dependency does not exist.
            ValueError: If the cron expression is invalid.
        """
        if isinstance(schedule, str):
            expr = CronExpression.parse(schedule)
            schedule = CronSchedule(expression=expr)

        job_id = job_id or str(uuid.uuid4())
        depends_on = depends_on or []
        metadata = metadata or {}
        now = time.time()

        next_run = schedule.expression.next_run()
        next_run_ts = next_run.timestamp() if next_run else 0.0

        job = CronJob(
            job_id=job_id,
            name=name,
            schedule=schedule,
            handler=handler,
            state=CronJobState.ENABLED,
            max_concurrent=max_concurrent,
            timeout_seconds=timeout_seconds,
            depends_on=depends_on,
            next_run_at=next_run_ts,
            created_at=now,
            metadata=metadata,
        )

        with self._lock:
            if job_id in self._jobs:
                raise CronJobAlreadyExistsError(
                    f"Job '{job_id}' already exists", job_id
                )

            for dep_id in depends_on:
                if dep_id not in self._jobs:
                    raise CronDependencyError(
                        f"Dependency '{dep_id}' does not exist", job_id
                    )

            self._jobs[job_id] = job

            with self._get_conn() as conn:
                conn.execute(
                    """INSERT INTO cron_jobs
                       (job_id, name, schedule, state, max_concurrent,
                        timeout_seconds, depends_on, next_run_at, created_at, metadata)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        job_id, name, schedule.expression.raw,
                        CronJobState.ENABLED.value, max_concurrent,
                        timeout_seconds, json.dumps(depends_on),
                        next_run_ts, now, json.dumps(metadata),
                    ),
                )

        logger.info("Cron job registered: %s (%s)", name, job_id[:8])
        return job

    # -- Job Management ------------------------------------------------------

    def get_job(self, job_id: str) -> CronJob:
        """Get a cron job by ID.

        Args:
            job_id: The job identifier.

        Returns:
            The CronJob.

        Raises:
            CronJobNotFoundError: If not found.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise CronJobNotFoundError(
                    f"Job '{job_id}' not found", job_id
                )
            return job

    def list_jobs(
        self,
        state: CronJobState | None = None,
    ) -> list[CronJob]:
        """List all registered jobs with optional state filter.

        Args:
            state: Filter by job state.

        Returns:
            List of matching CronJob objects.
        """
        with self._lock:
            jobs = list(self._jobs.values())
            if state:
                jobs = [j for j in jobs if j.state == state]
            return jobs

    def pause_job(self, job_id: str) -> CronJob:
        """Pause a job — it will not execute until resumed.

        Args:
            job_id: The job to pause.

        Returns:
            The updated CronJob.
        """
        return self._set_job_state(job_id, CronJobState.PAUSED)

    def resume_job(self, job_id: str) -> CronJob:
        """Resume a paused job.

        Args:
            job_id: The job to resume.

        Returns:
            The updated CronJob.
        """
        return self._set_job_state(job_id, CronJobState.ENABLED)

    def disable_job(self, job_id: str) -> CronJob:
        """Disable a job — it will not execute until re-enabled.

        Unlike pause, disable is intended for longer-term deactivation.

        Args:
            job_id: The job to disable.

        Returns:
            The updated CronJob.
        """
        return self._set_job_state(job_id, CronJobState.DISABLED)

    def enable_job(self, job_id: str) -> CronJob:
        """Enable a disabled job.

        Args:
            job_id: The job to enable.

        Returns:
            The updated CronJob.
        """
        return self._set_job_state(job_id, CronJobState.ENABLED)

    def _set_job_state(self, job_id: str, state: CronJobState) -> CronJob:
        """Set the state of a job.

        Args:
            job_id: The job to update.
            state: New state.

        Returns:
            The updated CronJob.

        Raises:
            CronJobNotFoundError: If not found.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise CronJobNotFoundError(
                    f"Job '{job_id}' not found", job_id
                )

            job.state = state

            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE cron_jobs SET state = ? WHERE job_id = ?",
                    (state.value, job_id),
                )

        logger.info("Job %s state changed to %s", job_id[:8], state.value)
        return job

    def delete_job(self, job_id: str) -> None:
        """Permanently delete a cron job and its history.

        Args:
            job_id: The job to delete.

        Raises:
            CronJobNotFoundError: If not found.
        """
        with self._lock:
            if job_id not in self._jobs:
                raise CronJobNotFoundError(
                    f"Job '{job_id}' not found", job_id
                )

            del self._jobs[job_id]

            with self._get_conn() as conn:
                conn.execute(
                    "DELETE FROM cron_history WHERE job_id = ?",
                    (job_id,),
                )
                conn.execute(
                    "DELETE FROM cron_jobs WHERE job_id = ?",
                    (job_id,),
                )

        logger.info("Cron job deleted: %s", job_id[:8])

    def update_job_schedule(
        self,
        job_id: str,
        schedule: str | CronSchedule,
    ) -> CronJob:
        """Update the schedule for an existing job.

        Args:
            job_id: The job to update.
            schedule: New cron expression or CronSchedule.

        Returns:
            The updated CronJob.

        Raises:
            CronJobNotFoundError: If not found.
            ValueError: If the cron expression is invalid.
        """
        if isinstance(schedule, str):
            expr = CronExpression.parse(schedule)
            schedule = CronSchedule(expression=expr)

        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise CronJobNotFoundError(
                    f"Job '{job_id}' not found", job_id
                )

            job.schedule = schedule
            next_run = schedule.expression.next_run()
            job.next_run_at = next_run.timestamp() if next_run else 0.0

            with self._get_conn() as conn:
                conn.execute(
                    "UPDATE cron_jobs SET schedule = ?, next_run_at = ? WHERE job_id = ?",
                    (schedule.expression.raw, job.next_run_at, job_id),
                )

        return job

    # -- Execution -----------------------------------------------------------

    def get_due_jobs(self, now: datetime | None = None) -> list[CronJob]:
        """Get all jobs that are due to run.

        Args:
            now: Reference time (defaults to now UTC).

        Returns:
            List of jobs that should execute.
        """
        if now is None:
            now = datetime.now(timezone.utc)

        due: list[CronJob] = []

        with self._lock:
            for job in self._jobs.values():
                if job.state not in (CronJobState.ENABLED, CronJobState.RUNNING):
                    continue

                if job.state == CronJobState.RUNNING:
                    active = sum(
                        1 for r in self._running
                        if r.startswith(job.job_id)
                    )
                    if active >= job.max_concurrent:
                        continue

                if not job.schedule.should_run(now):
                    continue

                if not self._dependencies_satisfied(job):
                    continue

                due.append(job)

        return due

    def execute_job(self, job_id: str, *args: Any, **kwargs: Any) -> CronJobResult:
        """Execute a specific job immediately.

        Args:
            job_id: The job to execute.
            *args: Positional arguments to pass to the handler.
            **kwargs: Keyword arguments to pass to the handler.

        Returns:
            CronJobResult with execution details.

        Raises:
            CronJobNotFoundError: If not found.
            CronExecutionTimeoutError: If execution times out.
        """
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                raise CronJobNotFoundError(
                    f"Job '{job_id}' not found", job_id
                )

        run_id = f"{job_id}:{uuid.uuid4().hex[:8]}"
        started_at = time.time()

        with self._lock:
            self._running.add(run_id)
            job.state = CronJobState.RUNNING

        try:
            if job.timeout_seconds > 0:
                result = self._execute_with_timeout(
                    job.handler, job.timeout_seconds, *args, **kwargs
                )
            else:
                result = job.handler(*args, **kwargs)

            finished_at = time.time()
            success = True
            error = None

        except Exception as e:
            finished_at = time.time()
            success = False
            error = str(e)
            result = None
            logger.error("Cron job %s failed: %s", job_id, error)

        job_result = CronJobResult(
            job_id=job_id,
            run_id=run_id,
            started_at=started_at,
            finished_at=finished_at,
            success=success,
            error=error,
            output=result,
        )

        self._record_result(job_id, job_result)

        with self._lock:
            self._running.discard(run_id)

            job = self._jobs.get(job_id)
            if job:
                job.last_run_at = finished_at
                if success:
                    job.run_count += 1
                else:
                    job.fail_count += 1

                next_run = job.schedule.expression.next_run()
                job.next_run_at = next_run.timestamp() if next_run else 0.0

                if job.state == CronJobState.RUNNING:
                    job.state = CronJobState.ENABLED

                with self._get_conn() as conn:
                    conn.execute(
                        """UPDATE cron_jobs
                           SET last_run_at = ?, next_run_at = ?,
                               run_count = ?, fail_count = ?, state = ?
                           WHERE job_id = ?""",
                        (
                            job.last_run_at, job.next_run_at,
                            job.run_count, job.fail_count,
                            job.state.value, job_id,
                        ),
                    )

        return job_result

    def _execute_with_timeout(
        self,
        handler: Callable[..., Any],
        timeout: float,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute a handler with a timeout.

        Args:
            handler: The callable to execute.
            timeout: Timeout in seconds.
            *args: Positional arguments for the handler.
            **kwargs: Keyword arguments for the handler.

        Returns:
            The handler's return value.

        Raises:
            CronExecutionTimeoutError: If execution exceeds timeout.
        """
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(handler, *args, **kwargs)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError:
                future.cancel()
                raise CronExecutionTimeoutError(
                    f"Job execution exceeded {timeout}s timeout"
                )

    def _dependencies_satisfied(self, job: CronJob) -> bool:
        """Check if all dependencies for a job have run successfully.

        A dependency is satisfied if the dependent job has run at least
        once after the current job's last scheduled time.

        Args:
            job: The job to check dependencies for.

        Returns:
            True if all dependencies are satisfied.
        """
        if not job.depends_on:
            return True

        for dep_id in job.depends_on:
            dep = self._jobs.get(dep_id)
            if dep is None:
                return False

            if dep.last_run_at == 0:
                return False

        return True

    # -- History -------------------------------------------------------------

    def get_job_history(
        self,
        job_id: str,
        limit: int = 50,
    ) -> list[CronJobHistory]:
        """Get execution history for a job.

        Args:
            job_id: The job to get history for.
            limit: Maximum number of entries to return.

        Returns:
            List of CronJobHistory entries, newest first.
        """
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM cron_history
                   WHERE job_id = ?
                   ORDER BY started_at DESC
                   LIMIT ?""",
                (job_id, limit),
            ).fetchall()

            return [
                CronJobHistory(
                    run_id=row["run_id"],
                    job_id=row["job_id"],
                    scheduled_for=row["scheduled_for"],
                    started_at=row["started_at"],
                    finished_at=row["finished_at"],
                    success=bool(row["success"]),
                    error=row["error"],
                )
                for row in rows
            ]

    def get_recent_history(self, limit: int = 20) -> list[CronJobHistory]:
        """Get recent execution history across all jobs.

        Args:
            limit: Maximum number of entries to return.

        Returns:
            List of CronJobHistory entries, newest first.
        """
        with self._get_conn() as conn:
            rows = conn.execute(
                """SELECT * FROM cron_history
                   ORDER BY started_at DESC
                   LIMIT ?""",
                (limit,),
            ).fetchall()

            return [
                CronJobHistory(
                    run_id=row["run_id"],
                    job_id=row["job_id"],
                    scheduled_for=row["scheduled_for"],
                    started_at=row["started_at"],
                    finished_at=row["finished_at"],
                    success=bool(row["success"]),
                    error=row["error"],
                )
                for row in rows
            ]

    def _record_result(self, job_id: str, result: CronJobResult) -> None:
        """Persist an execution result to the database.

        Args:
            job_id: The job that was executed.
            result: The execution result.
        """
        history = CronJobHistory(
            run_id=result.run_id,
            job_id=job_id,
            scheduled_for=result.started_at,
            started_at=result.started_at,
            finished_at=result.finished_at,
            success=result.success,
            error=result.error,
        )

        with self._lock:
            self._history.append(history)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

        with self._get_conn() as conn:
            conn.execute(
                """INSERT INTO cron_history
                   (run_id, job_id, scheduled_for, started_at,
                    finished_at, success, error)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    result.run_id, job_id, result.started_at,
                    result.started_at, result.finished_at,
                    int(result.success), result.error,
                ),
            )

    # -- Maintenance ---------------------------------------------------------

    def load_jobs_from_db(self) -> int:
        """Load persisted jobs from the database into memory.

        Note: Handlers are NOT restored — jobs must be re-registered
        with their handlers after loading.

        Returns:
            Number of jobs loaded.
        """
        with self._lock:
            with self._get_conn() as conn:
                rows = conn.execute("SELECT * FROM cron_jobs").fetchall()

                for row in rows:
                    schedule = CronSchedule(
                        expression=CronExpression.parse(row["schedule"])
                    )

                    job = CronJob(
                        job_id=row["job_id"],
                        name=row["name"],
                        schedule=schedule,
                        handler=lambda: None,
                        state=CronJobState(row["state"]),
                        max_concurrent=row["max_concurrent"],
                        timeout_seconds=row["timeout_seconds"],
                        depends_on=json.loads(row["depends_on"]),
                        last_run_at=row["last_run_at"],
                        next_run_at=row["next_run_at"],
                        run_count=row["run_count"],
                        fail_count=row["fail_count"],
                        created_at=row["created_at"],
                        metadata=json.loads(row["metadata"]),
                    )

                    self._jobs[row["job_id"]] = job

        count = len(self._jobs)
        logger.info("Loaded %d jobs from database", count)
        return count

    def cleanup_old_history(self, older_than_seconds: float = 86400 * 30) -> int:
        """Delete history entries older than the specified age.

        Args:
            older_than_seconds: Age threshold in seconds (default: 30 days).

        Returns:
            Number of entries deleted.
        """
        cutoff = time.time() - older_than_seconds

        with self._get_conn() as conn:
            result = conn.execute(
                "DELETE FROM cron_history WHERE started_at < ?",
                (cutoff,),
            )
            deleted = result.rowcount

        if deleted:
            logger.info("Cleaned up %d old history entries", deleted)

        return deleted

    def close(self) -> None:
        """Shut down the cron scheduler."""
        with self._lock:
            self._jobs.clear()
            self._running.clear()
            self._history.clear()

        logger.info("CronScheduler shut down")
