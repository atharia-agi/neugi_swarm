"""NEUGI v2 Graph Workflow Engine.

A production-ready workflow engine combining LangGraph-style state graphs
with CrewAI Flows patterns for durable, human-in-the-loop execution.

Public API:
    - StateGraph: Define and compile workflow graphs
    - WorkflowExecutor: Execute graphs with error handling and parallelism
    - CheckpointManager: Durable execution with SQLite persistence
    - HumanInTheLoop: Human approval and intervention system
"""

from .checkpoint import (
    Checkpoint,
    CheckpointDiff,
    CheckpointManager,
    CheckpointStorage,
    SQLiteCheckpointStorage,
)
from .executor import (
    ExecutionConfig,
    ExecutionResult,
    ExecutionStatus,
    NodeExecutionRecord,
    RetryPolicy,
    WorkflowExecutor,
)
from .human_in_loop import (
    ApprovalRequest,
    ApprovalStatus,
    HumanInTheLoop,
    HumanResponse,
    NotificationHandler,
    PausePoint,
)
from .state_graph import (
    ConditionalEdge,
    EdgeDefinition,
    ExecutionContext,
    GraphCompilationResult,
    NodeDefinition,
    StateDefinition,
    StateGraph,
)

__all__ = [
    # State Graph
    "StateGraph",
    "StateDefinition",
    "NodeDefinition",
    "EdgeDefinition",
    "ConditionalEdge",
    "GraphCompilationResult",
    "ExecutionContext",
    # Executor
    "WorkflowExecutor",
    "ExecutionResult",
    "ExecutionStatus",
    "NodeExecutionRecord",
    "ExecutionConfig",
    "RetryPolicy",
    # Checkpoint
    "CheckpointManager",
    "Checkpoint",
    "CheckpointDiff",
    "CheckpointStorage",
    "SQLiteCheckpointStorage",
    # Human in the Loop
    "HumanInTheLoop",
    "ApprovalRequest",
    "ApprovalStatus",
    "PausePoint",
    "HumanResponse",
    "NotificationHandler",
]
