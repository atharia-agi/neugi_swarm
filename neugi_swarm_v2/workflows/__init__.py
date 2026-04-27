"""NEUGI v2 Graph Workflow Engine.

A production-ready workflow engine combining LangGraph-style state graphs
with CrewAI Flows patterns for durable, human-in-the-loop execution.

Public API:
    - StateGraph: Define and compile workflow graphs
    - WorkflowExecutor: Execute graphs with error handling and parallelism
    - CheckpointManager: Durable execution with SQLite persistence
    - HumanInTheLoop: Human approval and intervention system
"""

from .state_graph import (
    StateGraph,
    StateDefinition,
    NodeDefinition,
    EdgeDefinition,
    ConditionalEdge,
    GraphCompilationResult,
    ExecutionContext,
)
from .executor import (
    WorkflowExecutor,
    ExecutionResult,
    ExecutionStatus,
    NodeExecutionRecord,
    ExecutionConfig,
    RetryPolicy,
)
from .checkpoint import (
    CheckpointManager,
    Checkpoint,
    CheckpointDiff,
    CheckpointStorage,
    SQLiteCheckpointStorage,
)
from .human_in_loop import (
    HumanInTheLoop,
    ApprovalRequest,
    ApprovalStatus,
    PausePoint,
    HumanResponse,
    NotificationHandler,
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
