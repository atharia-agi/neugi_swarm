"""WorkflowExecutor: Execute compiled workflow graphs.

Provides step-by-step execution with state tracking, conditional routing,
parallel execution, error handling, timeouts, and progress callbacks.
"""

from __future__ import annotations

import asyncio
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Union,
)

from .state_graph import (
    ConditionalEdge,
    EdgeDefinition,
    ExecutionContext,
    GraphCompilationResult,
    NodeDefinition,
    NodeStatus,
    StateDefinition,
    StateGraph,
)


class ExecutionStatus(Enum):
    """Status of workflow execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    PAUSED = "paused"


@dataclass
class RetryPolicy:
    """Configuration for node retry behavior.

    Attributes:
        max_retries: Maximum number of retry attempts.
        delay: Initial delay between retries in seconds.
        backoff_factor: Multiplier for delay after each retry.
        max_delay: Maximum delay between retries in seconds.
        retryable_exceptions: Exception types that trigger retry.
    """

    max_retries: int = 3
    delay: float = 1.0
    backoff_factor: float = 2.0
    max_delay: float = 60.0
    retryable_exceptions: tuple = (Exception,)

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for a given retry attempt.

        Args:
            attempt: Zero-based attempt number.

        Returns:
            Delay in seconds for this attempt.
        """
        delay = self.delay * (self.backoff_factor ** attempt)
        return min(delay, self.max_delay)


class ErrorHandling(Enum):
    """Error handling strategy for node failures."""
    ABORT = "abort"
    RETRY = "retry"
    SKIP = "skip"


@dataclass
class NodeExecutionRecord:
    """Record of a single node execution.

    Tracks timing, status, errors, and state changes.
    """

    node_name: str
    status: NodeStatus
    start_time: float
    end_time: float = 0.0
    error: Optional[str] = None
    error_traceback: Optional[str] = None
    input_state: Optional[Dict[str, Any]] = None
    output_state: Optional[Dict[str, Any]] = None
    retries: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        """Get execution duration in seconds."""
        if self.end_time > 0:
            return self.end_time - self.start_time
        return 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to dictionary for serialization."""
        return {
            "node_name": self.node_name,
            "status": self.status.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "error": self.error,
            "retries": self.retries,
        }


@dataclass
class ExecutionResult:
    """Result of workflow execution.

    Contains final state, execution history, and status.
    """

    status: ExecutionStatus
    final_state: Optional[StateDefinition]
    history: List[NodeExecutionRecord]
    start_time: float
    end_time: float = 0.0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def duration(self) -> float:
        """Get total execution duration in seconds."""
        if self.end_time > 0:
            return self.end_time - self.start_time
        return 0.0

    @property
    def successful_nodes(self) -> List[NodeExecutionRecord]:
        """Get list of successfully executed nodes."""
        return [r for r in self.history if r.status == NodeStatus.COMPLETED]

    @property
    def failed_nodes(self) -> List[NodeExecutionRecord]:
        """Get list of failed nodes."""
        return [r for r in self.history if r.status == NodeStatus.FAILED]

    def to_dict(self) -> Dict[str, Any]:
        """Convert result to dictionary for serialization."""
        return {
            "status": self.status.value,
            "duration": self.duration,
            "error": self.error,
            "history": [r.to_dict() for r in self.history],
            "successful_nodes": len(self.successful_nodes),
            "failed_nodes": len(self.failed_nodes),
        }


@dataclass
class ExecutionConfig:
    """Configuration for workflow execution.

    Attributes:
        timeout: Maximum execution time in seconds.
        retry_policy: Default retry policy for nodes.
        error_handling: Default error handling strategy.
        max_parallel: Maximum number of parallel nodes.
        enable_callbacks: Whether to invoke progress callbacks.
        metadata: Arbitrary metadata for the execution.
    """

    timeout: Optional[float] = 300.0
    retry_policy: Optional[RetryPolicy] = None
    error_handling: ErrorHandling = ErrorHandling.RETRY
    max_parallel: int = 4
    enable_callbacks: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


# Type alias for progress callback
ProgressCallback = Callable[[str, NodeStatus, Dict[str, Any]], None]


class WorkflowExecutor:
    """Execute compiled workflow graphs with full lifecycle management.

    Supports sequential and parallel execution, conditional routing,
    error handling with retries, timeouts, and progress callbacks.

    Example:
        executor = WorkflowExecutor(compiled_graph)
        result = executor.execute(initial_state)
    """

    def __init__(
        self,
        compiled: GraphCompilationResult,
        config: Optional[ExecutionConfig] = None,
    ) -> None:
        """Initialize the executor.

        Args:
            compiled: Compiled graph result from StateGraph.compile().
            config: Optional execution configuration.

        Raises:
            ValueError: If graph is not valid.
        """
        if not compiled.is_valid:
            raise ValueError(f"Cannot execute invalid graph: {compiled.errors}")

        self.compiled = compiled
        self.config = config or ExecutionConfig()
        self._history: List[NodeExecutionRecord] = []
        self._callbacks: List[ProgressCallback] = []
        self._cancelled = False
        self._node_error_handlers: Dict[str, ErrorHandling] = {}
        self._node_retry_policies: Dict[str, RetryPolicy] = {}

    def add_callback(self, callback: ProgressCallback) -> "WorkflowExecutor":
        """Add a progress callback.

        Args:
            callback: Function called with (node_name, status, metadata).

        Returns:
            Self for method chaining.
        """
        self._callbacks.append(callback)
        return self

    def set_node_error_handling(
        self,
        node_name: str,
        handling: ErrorHandling,
    ) -> "WorkflowExecutor":
        """Set error handling for a specific node.

        Args:
            node_name: Node to configure.
            handling: Error handling strategy.

        Returns:
            Self for method chaining.
        """
        self._node_error_handlers[node_name] = handling
        return self

    def set_node_retry_policy(
        self,
        node_name: str,
        policy: RetryPolicy,
    ) -> "WorkflowExecutor":
        """Set retry policy for a specific node.

        Args:
            node_name: Node to configure.
            policy: Retry policy to apply.

        Returns:
            Self for method chaining.
        """
        self._node_retry_policies[node_name] = policy
        return self

    def cancel(self) -> None:
        """Cancel the current execution."""
        self._cancelled = True

    def execute(
        self,
        initial_state: StateDefinition,
        context: Optional[ExecutionContext] = None,
    ) -> ExecutionResult:
        """Execute the workflow from the given initial state.

        Args:
            initial_state: Starting state for the workflow.
            context: Optional execution context for subgraph execution.

        Returns:
            ExecutionResult with final state and history.
        """
        self._cancelled = False
        self._history = []
        start_time = time.time()

        exec_context = context or ExecutionContext(
            state=initial_state,
            path=[],
        )

        try:
            self._execute_from_entry(exec_context)
            status = ExecutionStatus.FAILED if self._has_failures() else ExecutionStatus.COMPLETED
        except ExecutionTimeoutError:
            status = ExecutionStatus.TIMEOUT
        except ExecutionCancelledError:
            status = ExecutionStatus.CANCELLED
        except Exception as e:
            status = ExecutionStatus.FAILED
            self._record_error("workflow", str(e), traceback.format_exc())

        end_time = time.time()

        return ExecutionResult(
            status=status,
            final_state=exec_context.state,
            history=list(self._history),
            start_time=start_time,
            end_time=end_time,
            error=self._get_error_summary(),
            metadata=dict(self.config.metadata),
        )

    def _execute_from_entry(self, context: ExecutionContext) -> None:
        """Execute the graph starting from entry points.

        Args:
            context: Current execution context.
        """
        # Execute by levels for parallel execution
        for level in self.compiled.execution_order:
            if self._cancelled:
                raise ExecutionCancelledError("Execution was cancelled")

            if len(level) == 1:
                # Sequential execution
                self._execute_node(level[0], context)
            else:
                # Parallel execution
                self._execute_parallel(level, context)

            # Check timeout
            if self.config.timeout:
                elapsed = time.time() - context.metadata.get("start_time", time.time())
                if elapsed > self.config.timeout:
                    raise ExecutionTimeoutError(f"Execution exceeded {self.config.timeout}s timeout")

    def _execute_node(self, node_name: str, context: ExecutionContext) -> None:
        """Execute a single node with error handling and retries.

        Args:
            node_name: Name of the node to execute.
            context: Current execution context.
        """
        node = self.compiled.nodes.get(node_name)
        if not node:
            return

        # Create node context
        node_context = context.child_context(node_name)
        node_context.metadata["start_time"] = time.time()

        # Record start
        record = NodeExecutionRecord(
            node_name=node_name,
            status=NodeStatus.RUNNING,
            start_time=time.time(),
            input_state=node_context.state.get_fields(),
        )

        self._notify_callback(node_name, NodeStatus.RUNNING, {"attempt": 0})

        # Execute with retries
        retry_policy = self._node_retry_policies.get(
            node_name, self.config.retry_policy or RetryPolicy()
        )
        error_handling = self._node_error_handlers.get(
            node_name, self.config.error_handling
        )

        last_error = None
        for attempt in range(retry_policy.max_retries + 1):
            if self._cancelled:
                record.status = NodeStatus.SKIPPED
                record.end_time = time.time()
                self._history.append(record)
                return

            try:
                # Execute the node handler
                new_state = node.handler(node_context.state)
                record.status = NodeStatus.COMPLETED
                record.output_state = new_state.get_fields()
                record.end_time = time.time()
                record.retries = attempt

                # Update context state
                node_context.state = new_state
                context.state = new_state

                self._notify_callback(node_name, NodeStatus.COMPLETED, {
                    "duration": record.duration,
                    "retries": attempt,
                })
                break

            except Exception as e:
                last_error = e
                record.retries = attempt

                if attempt < retry_policy.max_retries:
                    if isinstance(e, retry_policy.retryable_exceptions):
                        delay = retry_policy.get_delay(attempt)
                        self._notify_callback(node_name, NodeStatus.RUNNING, {
                            "attempt": attempt + 1,
                            "retry_delay": delay,
                            "error": str(e),
                        })
                        time.sleep(delay)
                        continue

                # All retries exhausted or non-retryable error
                record.status = NodeStatus.FAILED
                record.error = str(e)
                record.error_traceback = traceback.format_exc()
                record.end_time = time.time()

                self._notify_callback(node_name, NodeStatus.FAILED, {
                    "error": str(e),
                    "retries": attempt,
                })

                # Handle based on error handling strategy
                if error_handling == ErrorHandling.ABORT:
                    self._history.append(record)
                    raise WorkflowExecutionError(f"Node '{node_name}' failed: {e}")
                elif error_handling == ErrorHandling.SKIP:
                    self._history.append(record)
                    return

        self._history.append(record)

        # Route to next node(s)
        self._route_from_node(node_name, context)

    def _execute_parallel(
        self,
        node_names: List[str],
        context: ExecutionContext,
    ) -> None:
        """Execute multiple nodes in parallel.

        Args:
            node_names: List of node names to execute.
            context: Current execution context.
        """
        results: Dict[str, StateDefinition] = {}
        errors: List[tuple] = []

        with ThreadPoolExecutor(max_workers=self.config.max_parallel) as executor:
            futures = {}
            for node_name in node_names:
                future = executor.submit(self._execute_node_isolated, node_name, context)
                futures[future] = node_name

            for future in as_completed(futures):
                node_name = futures[future]
                try:
                    state = future.result()
                    results[node_name] = state
                except Exception as e:
                    errors.append((node_name, e))

        # Merge results from parallel execution
        if results:
            merged_state = context.state
            for state in results.values():
                merged_state = merged_state.merge(state)
            context.state = merged_state

        # Handle errors
        if errors:
            for node_name, error in errors:
                self._record_error(node_name, str(error), traceback.format_exc())
            if self.config.error_handling == ErrorHandling.ABORT:
                raise WorkflowExecutionError(f"Parallel execution failed: {errors}")

    def _execute_node_isolated(
        self,
        node_name: str,
        context: ExecutionContext,
    ) -> StateDefinition:
        """Execute a node in isolation for parallel execution.

        Args:
            node_name: Node to execute.
            context: Parent execution context.

        Returns:
            Updated state from node execution.
        """
        node = self.compiled.nodes.get(node_name)
        if not node:
            return context.state

        node_context = context.child_context(node_name)

        record = NodeExecutionRecord(
            node_name=node_name,
            status=NodeStatus.RUNNING,
            start_time=time.time(),
            input_state=node_context.state.get_fields(),
        )

        try:
            new_state = node.handler(node_context.state)
            record.status = NodeStatus.COMPLETED
            record.output_state = new_state.get_fields()
            record.end_time = time.time()

            self._history.append(record)
            self._notify_callback(node_name, NodeStatus.COMPLETED, {})

            return new_state

        except Exception as e:
            record.status = NodeStatus.FAILED
            record.error = str(e)
            record.error_traceback = traceback.format_exc()
            record.end_time = time.time()

            self._history.append(record)
            self._notify_callback(node_name, NodeStatus.FAILED, {"error": str(e)})

            raise

    def _route_from_node(self, node_name: str, context: ExecutionContext) -> None:
        """Route execution from a completed node to next node(s).

        Handles both unconditional and conditional edges.

        Args:
            node_name: Completed node name.
            context: Current execution context.
        """
        # Check conditional edges first
        if node_name in self.compiled.conditional_edges:
            cond_edge = self.compiled.conditional_edges[node_name]
            target = cond_edge.router(context.state)

            if target in cond_edge.targets:
                self._execute_node(target, context)
            elif cond_edge.default:
                self._execute_node(cond_edge.default, context)
            return

        # Check unconditional edges
        if node_name in self.compiled.edges:
            edges = self.compiled.edges[node_name]
            for edge in edges:
                if edge.condition is None or edge.condition(context.state):
                    self._execute_node(edge.target, context)

    def _notify_callback(
        self,
        node_name: str,
        status: NodeStatus,
        metadata: Dict[str, Any],
    ) -> None:
        """Notify all registered callbacks of a status change.

        Args:
            node_name: Node that changed status.
            status: New status.
            metadata: Additional metadata.
        """
        if not self.config.enable_callbacks:
            return

        for callback in self._callbacks:
            try:
                callback(node_name, status, metadata)
            except Exception:
                pass  # Callbacks should not break execution

    def _record_error(
        self,
        node_name: str,
        error: str,
        tb: Optional[str] = None,
    ) -> None:
        """Record an error in the execution history.

        Args:
            node_name: Node where error occurred.
            error: Error message.
            tb: Optional traceback.
        """
        record = NodeExecutionRecord(
            node_name=node_name,
            status=NodeStatus.FAILED,
            start_time=time.time(),
            end_time=time.time(),
            error=error,
            error_traceback=tb,
        )
        self._history.append(record)

    def _has_failures(self) -> bool:
        """Check if any nodes failed during execution.

        Returns:
            True if any node failed.
        """
        return any(r.status == NodeStatus.FAILED for r in self._history)

    def _get_error_summary(self) -> Optional[str]:
        """Get a summary of all errors.

        Returns:
            Error summary string or None if no errors.
        """
        failures = [r for r in self._history if r.status == NodeStatus.FAILED]
        if not failures:
            return None

        errors = [f"{r.node_name}: {r.error}" for r in failures]
        return "; ".join(errors)

    def get_history(self) -> List[NodeExecutionRecord]:
        """Get the execution history.

        Returns:
            List of node execution records.
        """
        return list(self._history)

    def get_failed_nodes(self) -> List[str]:
        """Get list of failed node names.

        Returns:
            List of node names that failed.
        """
        return [r.node_name for r in self._history if r.status == NodeStatus.FAILED]

    def get_successful_nodes(self) -> List[str]:
        """Get list of successful node names.

        Returns:
            List of node names that completed successfully.
        """
        return [r.node_name for r in self._history if r.status == NodeStatus.COMPLETED]


class WorkflowExecutionError(Exception):
    """Error raised when workflow execution fails."""

    pass


class ExecutionTimeoutError(Exception):
    """Error raised when execution exceeds timeout."""

    pass


class ExecutionCancelledError(Exception):
    """Error raised when execution is cancelled."""

    pass
