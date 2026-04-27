"""
Orchestrator-worker pattern: central task decomposition, capability-based
worker assignment, parallel execution, result aggregation, and error recovery.
"""

import logging
import time
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

from .agent import Agent, AgentRole, AgentStatus
from .agent_manager import AgentManager

logger = logging.getLogger(__name__)


@dataclass
class WorkerResult:
    """Output from a single worker execution."""
    worker_id: str
    worker_name: str
    subtask: str
    output: Any
    success: bool
    error: Optional[str]
    duration_seconds: float
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class OrchestratorReport:
    """Aggregated report from a full orchestration run."""
    task: str
    total_workers: int
    successful: int
    failed: int
    retried: int
    total_duration_seconds: float
    worker_results: List[WorkerResult]
    synthesis: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Orchestrator:
    """
    Central orchestrator that decomposes complex tasks into subtasks,
    assigns workers based on capabilities, executes in parallel,
    aggregates results, and handles failures with retry/reassign.

    Pattern: Anthropic's "Orchestrator-Workers" from Building Effective Agents.
    """

    def __init__(
        self,
        manager: AgentManager,
        max_workers: int = 5,
        max_retries: int = 2,
        retry_delay: float = 0.5,
    ) -> None:
        self.manager = manager
        self.max_workers = max_workers
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._decomposer: Optional[Callable[[str], List[str]]] = None
        self._synthesizer: Optional[Callable[[str, List[WorkerResult]], str]] = None

    # ------------------------------------------------------------------
    # Custom hooks
    # ------------------------------------------------------------------

    def set_decomposer(self, func: Callable[[str], List[str]]) -> None:
        """Set a custom task decomposition function."""
        self._decomposer = func

    def set_synthesizer(
        self, func: Callable[[str, List[WorkerResult]], str]
    ) -> None:
        """Set a custom result synthesis function."""
        self._synthesizer = func

    # ------------------------------------------------------------------
    # Main orchestration
    # ------------------------------------------------------------------

    def run(self, task: str, context: Optional[Dict[str, Any]] = None) -> OrchestratorReport:
        """
        Execute the full orchestrator pipeline:
        1. Decompose task into subtasks
        2. Assign workers by capability
        3. Execute workers in parallel
        4. Retry failed workers
        5. Aggregate and synthesize results
        """
        start = time.monotonic()
        subtasks = self._decompose(task)
        assignments = self._assign_workers(subtasks)

        results: List[WorkerResult] = []
        retried = 0

        # First pass: parallel execution
        first_pass = self._execute_workers(assignments, context)
        results.extend(first_pass)

        # Retry failed workers
        failed = [r for r in first_pass if not r.success]
        for attempt in range(self.max_retries):
            if not failed:
                break
            time.sleep(self.retry_delay)
            retry_assignments = self._reassign_workers(
                [(f.subtask, f.worker_id) for f in failed]
            )
            retry_results = self._execute_workers(retry_assignments, context)
            retried += len(retry_results)
            # Replace failed entries
            result_map = {r.subtask: r for r in results}
            for r in retry_results:
                result_map[r.subtask] = r
            results = list(result_map.values())
            failed = [r for r in retry_results if not r.success]

        duration = time.monotonic() - start
        synthesis = self._synthesize(task, results)

        successful = sum(1 for r in results if r.success)
        report = OrchestratorReport(
            task=task,
            total_workers=len(results),
            successful=successful,
            failed=len(results) - successful,
            retried=retried,
            total_duration_seconds=round(duration, 3),
            worker_results=results,
            synthesis=synthesis,
        )
        logger.info(
            "Orchestration complete: %d workers, %d success, %d failed, %.2fs",
            report.total_workers,
            report.successful,
            report.failed,
            report.total_duration_seconds,
        )
        return report

    # ------------------------------------------------------------------
    # Decomposition
    # ------------------------------------------------------------------

    def _decompose(self, task: str) -> List[str]:
        """Break a task into subtasks."""
        if self._decomposer:
            return self._decomposer(task)
        return self._default_decompose(task)

    def _default_decompose(self, task: str) -> List[str]:
        """Default decomposition: research, plan, implement, review."""
        return [
            f"Research and analyze: {task}",
            f"Plan approach for: {task}",
            f"Implement solution for: {task}",
            f"Review and validate: {task}",
        ]

    # ------------------------------------------------------------------
    # Worker assignment
    # ------------------------------------------------------------------

    def _assign_workers(
        self, subtasks: List[str]
    ) -> List[Tuple[str, Agent]]:
        """Match subtasks to agents by role and availability."""
        assignments = []
        for subtask in subtasks:
            agent = self._best_agent_for_task(subtask)
            if agent:
                assignments.append((subtask, agent))
        return assignments

    def _reassign_workers(
        self, failed_pairs: List[Tuple[str, str]]
    ) -> List[Tuple[str, Agent]]:
        """Reassign failed subtasks to different agents."""
        assignments = []
        for subtask, _ in failed_pairs:
            agent = self._best_agent_for_task(subtask, exclude_ids=set())
            if agent:
                assignments.append((subtask, agent))
        return assignments

    def _best_agent_for_task(
        self, task: str, exclude_ids: Optional[set] = None
    ) -> Optional[Agent]:
        """Find the best idle agent for a task."""
        exclude = exclude_ids or set()
        candidates = [
            a for a in self.manager.list_agents()
            if a.id not in exclude and a.status == AgentStatus.IDLE
        ]
        if not candidates:
            candidates = self.manager.list_agents()

        inferred = self._infer_role(task)
        role_match = [a for a in candidates if a.role == inferred]
        if role_match:
            return role_match[0]
        return candidates[0] if candidates else None

    def _infer_role(self, task: str) -> AgentRole:
        task_lower = task.lower()
        keywords = {
            AgentRole.RESEARCHER: ["research", "analyze", "investigate", "search"],
            AgentRole.CODER: ["code", "implement", "build", "develop", "function"],
            AgentRole.CREATOR: ["design", "create", "prototype", "concept"],
            AgentRole.ANALYST: ["metric", "report", "trend", "data"],
            AgentRole.STRATEGIST: ["strategy", "plan", "roadmap", "optimize"],
            AgentRole.SECURITY: ["security", "audit", "vulnerability", "threat"],
            AgentRole.SOCIAL: ["social", "post", "community"],
            AgentRole.WRITER: ["write", "document", "article", "copy"],
            AgentRole.MANAGER: ["manage", "coordinate", "delegate"],
        }
        for role, kws in keywords.items():
            if any(kw in task_lower for kw in kws):
                return role
        return AgentRole.MANAGER

    # ------------------------------------------------------------------
    # Execution
    # ------------------------------------------------------------------

    def _execute_workers(
        self,
        assignments: List[Tuple[str, Agent]],
        context: Optional[Dict[str, Any]],
    ) -> List[WorkerResult]:
        """Execute assigned workers, using threads for parallelism."""
        results: List[WorkerResult] = []
        if not assignments:
            return results

        with ThreadPoolExecutor(max_workers=min(self.max_workers, len(assignments))) as pool:
            futures = {
                pool.submit(self._run_worker, subtask, agent, context): subtask
                for subtask, agent in assignments
            }
            for future in as_completed(futures):
                subtask = futures[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as exc:
                    results.append(
                        WorkerResult(
                            worker_id="unknown",
                            worker_name="unknown",
                            subtask=subtask,
                            output=None,
                            success=False,
                            error=str(exc),
                            duration_seconds=0.0,
                        )
                    )
        return results

    def _run_worker(
        self,
        subtask: str,
        agent: Agent,
        context: Optional[Dict[str, Any]],
    ) -> WorkerResult:
        start = time.monotonic()
        try:
            result = agent.execute(subtask, context)
            duration = time.monotonic() - start
            errs = result.get("errors", [])
            return WorkerResult(
                worker_id=agent.id,
                worker_name=agent.name,
                subtask=subtask,
                output=result.get("output"),
                success=result.get("success", False),
                error=errs[-1] if errs else None,
                duration_seconds=round(duration, 3),
            )
        except Exception as exc:
            duration = time.monotonic() - start
            return WorkerResult(
                worker_id=agent.id,
                worker_name=agent.name,
                subtask=subtask,
                output=None,
                success=False,
                error=str(exc),
                duration_seconds=round(duration, 3),
            )

    # ------------------------------------------------------------------
    # Synthesis
    # ------------------------------------------------------------------

    def _synthesize(self, task: str, results: List[WorkerResult]) -> str:
        """Combine worker outputs into a final answer."""
        if self._synthesizer:
            return self._synthesizer(task, results)
        return self._default_synthesize(task, results)

    def _default_synthesize(self, task: str, results: List[WorkerResult]) -> str:
        parts = []
        for r in results:
            status = "OK" if r.success else "FAILED"
            output = str(r.output)[:200] if r.output else "no output"
            parts.append(f"[{r.worker_name}] ({status}): {output}")
        successful = sum(1 for r in results if r.success)
        header = (
            f"Orchestration complete for: {task}\n"
            f"Workers: {len(results)}, Successful: {successful}\n"
        )
        return header + "\n".join(parts)

    # ------------------------------------------------------------------
    # Progress tracking
    # ------------------------------------------------------------------

    def run_with_progress(
        self,
        task: str,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> OrchestratorReport:
        """Run orchestration with progress updates via callback."""
        subtasks = self._decompose(task)
        total = len(subtasks)
        if progress_callback:
            progress_callback("decomposed", 0.1)

        assignments = self._assign_workers(subtasks)
        if progress_callback:
            progress_callback("assigned", 0.2)

        results: List[WorkerResult] = []
        for i, (subtask, agent) in enumerate(assignments):
            result = self._run_worker(subtask, agent, context)
            results.append(result)
            progress = 0.2 + (0.6 * (i + 1) / total)
            if progress_callback:
                progress_callback(
                    f"worker_{agent.name}_{'done' if result.success else 'failed'}",
                    round(progress, 2),
                )

        synthesis = self._synthesize(task, results)
        if progress_callback:
            progress_callback("synthesized", 1.0)

        successful = sum(1 for r in results if r.success)
        return OrchestratorReport(
            task=task,
            total_workers=len(results),
            successful=successful,
            failed=len(results) - successful,
            retried=0,
            total_duration_seconds=sum(r.duration_seconds for r in results),
            worker_results=results,
            synthesis=synthesis,
        )
