"""
Process patterns for multi-agent workflows: sequential, hierarchical,
parallel, and consensus execution with state machine transitions.
"""

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from .agent import Agent, AgentStatus
from .agent_manager import AgentManager

logger = logging.getLogger(__name__)


class ProcessStatus(str, Enum):
    """Process lifecycle states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass
class ProcessStep:
    """A single step within a process."""
    id: str
    name: str
    agent_id: Optional[str]
    agent_name: Optional[str]
    task: str
    status: str = "pending"
    output: Any = None
    error: Optional[str] = None
    duration_seconds: float = 0.0
    started_at: Optional[str] = None
    completed_at: Optional[str] = None


@dataclass
class ProcessResult:
    """Final output of a process execution."""
    process_id: str
    process_type: str
    status: str
    steps: List[ProcessStep]
    final_output: Any
    total_duration_seconds: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Process:
    """
    Base class for multi-agent process patterns.

    Implements a state machine with transitions:
    PENDING -> RUNNING -> COMPLETED | FAILED | CANCELLED
                  -> PAUSED -> RUNNING (resume)
    """

    def __init__(self, name: str, manager: AgentManager) -> None:
        self.id = str(uuid.uuid4())[:12]
        self.name = name
        self.manager = manager
        self.status = ProcessStatus.PENDING
        self.steps: List[ProcessStep] = []
        self.final_output: Any = None
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.started_at: Optional[str] = None
        self.completed_at: Optional[str] = None
        self.error: Optional[str] = None
        self._on_step_complete: Optional[Callable[[ProcessStep], None]] = None

    def on_step_complete(self, callback: Callable[[ProcessStep], None]) -> None:
        """Register a callback invoked after each step completes."""
        self._on_step_complete = callback

    def _transition(self, new_status: ProcessStatus) -> None:
        valid_transitions = {
            ProcessStatus.PENDING: {ProcessStatus.RUNNING, ProcessStatus.CANCELLED},
            ProcessStatus.RUNNING: {
                ProcessStatus.COMPLETED,
                ProcessStatus.FAILED,
                ProcessStatus.PAUSED,
                ProcessStatus.CANCELLED,
            },
            ProcessStatus.PAUSED: {ProcessStatus.RUNNING, ProcessStatus.CANCELLED},
            ProcessStatus.COMPLETED: set(),
            ProcessStatus.FAILED: set(),
            ProcessStatus.CANCELLED: set(),
        }
        allowed = valid_transitions.get(self.status, set())
        if new_status not in allowed:
            raise ValueError(
                f"Invalid transition: {self.status.value} -> {new_status.value}"
            )
        self.status = new_status

    def pause(self) -> bool:
        if self.status == ProcessStatus.RUNNING:
            self._transition(ProcessStatus.PAUSED)
            return True
        return False

    def resume(self) -> bool:
        if self.status == ProcessStatus.PAUSED:
            self._transition(ProcessStatus.RUNNING)
            return True
        return False

    def cancel(self) -> bool:
        if self.status in (ProcessStatus.PENDING, ProcessStatus.RUNNING, ProcessStatus.PAUSED):
            self._transition(ProcessStatus.CANCELLED)
            return True
        return False

    def _execute_step(self, step: ProcessStep) -> ProcessStep:
        """Execute a single step using the assigned agent."""
        step.status = "running"
        step.started_at = datetime.now(timezone.utc).isoformat()
        start = time.monotonic()

        try:
            if step.agent_id:
                agent = self.manager.get_agent(step.agent_id)
                if agent:
                    result = agent.execute(step.task)
                    step.output = result.get("output")
                    step.status = "completed" if result.get("success") else "failed"
                    errs = result.get("errors", [])
                    step.error = errs[-1] if errs else None
                else:
                    step.status = "failed"
                    step.error = f"Agent {step.agent_id} not found"
            else:
                step.status = "failed"
                step.error = "No agent assigned to step"

        except Exception as exc:
            step.status = "failed"
            step.error = str(exc)
            logger.error("Step %s failed: %s", step.id, exc)

        finally:
            step.duration_seconds = round(time.monotonic() - start, 3)
            step.completed_at = datetime.now(timezone.utc).isoformat()
            if self._on_step_complete:
                self._on_step_complete(step)

        return step

    def _build_result(self, start_time: float) -> ProcessResult:
        return ProcessResult(
            process_id=self.id,
            process_type=self.__class__.__name__,
            status=self.status.value,
            steps=self.steps,
            final_output=self.final_output,
            total_duration_seconds=round(time.monotonic() - start_time, 3),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "steps": [
                {
                    "id": s.id,
                    "name": s.name,
                    "agent_name": s.agent_name,
                    "task": s.task,
                    "status": s.status,
                    "error": s.error,
                    "duration_seconds": s.duration_seconds,
                }
                for s in self.steps
            ],
            "error": self.error,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class SequentialProcess(Process):
    """
    Execute steps in strict order. Each step waits for the previous
    to complete before starting. Output from one step can feed the next.
    """

    def run(self, context: Optional[Dict[str, Any]] = None) -> ProcessResult:
        self._transition(ProcessStatus.RUNNING)
        self.started_at = datetime.now(timezone.utc).isoformat()
        start = time.monotonic()
        accumulated_context = context or {}

        for step in self.steps:
            if self.status != ProcessStatus.RUNNING:
                break

            # Inject accumulated context into task
            step.task = step.task.format(**accumulated_context) if accumulated_context else step.task
            step = self._execute_step(step)

            if step.status == "failed":
                self.error = f"Step '{step.name}' failed: {step.error}"
                self._transition(ProcessStatus.FAILED)
                break

            # Pass output to next step
            if step.output:
                accumulated_context[step.name] = step.output

        if self.status == ProcessStatus.RUNNING:
            self.final_output = self.steps[-1].output if self.steps else None
            self._transition(ProcessStatus.COMPLETED)

        self.completed_at = datetime.now(timezone.utc).isoformat()
        return self._build_result(start)


class HierarchicalProcess(Process):
    """
    Manager agent decomposes the task and delegates to worker agents.
    Workers execute in parallel, manager synthesizes results.
    """

    def __init__(
        self,
        name: str,
        manager: AgentManager,
        manager_agent_id: str,
    ) -> None:
        super().__init__(name, manager)
        self.manager_agent_id = manager_agent_id
        self.worker_agents: List[str] = []

    def add_worker(self, agent_id: str) -> None:
        self.worker_agents.append(agent_id)

    def run(self, context: Optional[Dict[str, Any]] = None) -> ProcessResult:
        self._transition(ProcessStatus.RUNNING)
        self.started_at = datetime.now(timezone.utc).isoformat()
        start = time.monotonic()

        mgr = self.manager.get_agent(self.manager_agent_id)
        if mgr is None:
            self.error = f"Manager agent {self.manager_agent_id} not found"
            self._transition(ProcessStatus.FAILED)
            self.completed_at = datetime.now(timezone.utc).isoformat()
            return self._build_result(start)

        # Manager decomposes
        decomposition = mgr.execute(f"Decompose this task into subtasks: {self.name}")
        subtasks = self._extract_subtasks(decomposition)

        # Assign and execute workers
        worker_results = []
        with ThreadPoolExecutor(max_workers=len(self.worker_agents)) as pool:
            futures = {}
            for i, worker_id in enumerate(self.worker_agents):
                if i < len(subtasks):
                    step = ProcessStep(
                        id=str(uuid.uuid4())[:12],
                        name=f"worker_{worker_id}",
                        agent_id=worker_id,
                        agent_name=self.manager.get_agent(worker_id).name
                        if self.manager.get_agent(worker_id)
                        else worker_id,
                        task=subtasks[i],
                    )
                    self.steps.append(step)
                    futures[pool.submit(self._execute_step, step)] = step

            for future in as_completed(futures):
                step = futures[future]
                worker_results.append(step)

        # Check for failures
        failed = [s for s in worker_results if s.status == "failed"]
        if failed:
            self.error = f"{len(failed)} worker(s) failed"
            self._transition(ProcessStatus.FAILED)
        else:
            self._transition(ProcessStatus.COMPLETED)

        # Manager synthesizes
        synthesis_task = f"Synthesize these results: {worker_results}"
        final = mgr.execute(synthesis_task)
        self.final_output = final.get("output")

        self.completed_at = datetime.now(timezone.utc).isoformat()
        return self._build_result(start)

    def _extract_subtasks(self, decomposition: Dict[str, Any]) -> List[str]:
        output = decomposition.get("output", "")
        if isinstance(output, str):
            return [line.strip() for line in output.split("\n") if line.strip()]
        return [self.name]


class ParallelProcess(Process):
    """
    Execute all steps concurrently. Optionally sync at a barrier
    before producing final output.
    """

    def __init__(
        self,
        name: str,
        manager: AgentManager,
        sync_barrier: bool = True,
    ) -> None:
        super().__init__(name, manager)
        self.sync_barrier = sync_barrier

    def run(self, context: Optional[Dict[str, Any]] = None) -> ProcessResult:
        self._transition(ProcessStatus.RUNNING)
        self.started_at = datetime.now(timezone.utc).isoformat()
        start = time.monotonic()

        with ThreadPoolExecutor(max_workers=len(self.steps)) as pool:
            futures = {pool.submit(self._execute_step, step): step for step in self.steps}
            for future in as_completed(futures):
                step = futures[future]
                # Step already updated by _execute_step

        if self.sync_barrier:
            failed = [s for s in self.steps if s.status == "failed"]
            if failed:
                self.error = f"{len(failed)} step(s) failed at barrier"
                self._transition(ProcessStatus.FAILED)
            else:
                self._transition(ProcessStatus.COMPLETED)
        else:
            self._transition(ProcessStatus.COMPLETED)

        self.final_output = [s.output for s in self.steps if s.output]
        self.completed_at = datetime.now(timezone.utc).isoformat()
        return self._build_result(start)


class ConsensusProcess(Process):
    """
    Multiple agents independently produce outputs, then vote
    on the best result. Requires a minimum agreement threshold.
    """

    def __init__(
        self,
        name: str,
        manager: AgentManager,
        agreement_threshold: float = 0.6,
        voting_agent_id: Optional[str] = None,
    ) -> None:
        super().__init__(name, manager)
        self.agreement_threshold = agreement_threshold
        self.voting_agent_id = voting_agent_id

    def run(self, context: Optional[Dict[str, Any]] = None) -> ProcessResult:
        self._transition(ProcessStatus.RUNNING)
        self.started_at = datetime.now(timezone.utc).isoformat()
        start = time.monotonic()

        # All agents execute the same task
        outputs = []
        with ThreadPoolExecutor(max_workers=len(self.steps)) as pool:
            futures = {pool.submit(self._execute_step, step): step for step in self.steps}
            for future in as_completed(futures):
                step = futures[future]
                if step.output:
                    outputs.append(step.output)

        # Voting
        if self.voting_agent_id:
            voter = self.manager.get_agent(self.voting_agent_id)
            if voter:
                vote_result = voter.execute(
                    f"Choose the best output from: {outputs}"
                )
                self.final_output = vote_result.get("output")
        else:
            # Simple majority: pick most common output
            self.final_output = max(set(str(o) for o in outputs), key=lambda o: str(outputs).count(o))

        # Calculate agreement
        if outputs:
            agreement = outputs.count(self.final_output) / len(outputs)
            if agreement < self.agreement_threshold:
                self.error = f"Agreement {agreement:.2f} below threshold {self.agreement_threshold}"
                self._transition(ProcessStatus.FAILED)
            else:
                self._transition(ProcessStatus.COMPLETED)
        else:
            self.error = "No outputs produced"
            self._transition(ProcessStatus.FAILED)

        self.completed_at = datetime.now(timezone.utc).isoformat()
        return self._build_result(start)
