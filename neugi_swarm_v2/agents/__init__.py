"""
NEUGI v2 Agent System
=====================

Production-grade multi-agent framework combining:
- CrewAI: Role-based agents, sequential/hierarchical processes, structured state
- Anthropic Building Effective Agents: Orchestrator-workers, evaluator-optimizer, routing
- Paperclip: Goal-aware execution, heartbeat scheduling, atomic task checkout
- AutoGen: Actor model, event-driven messaging

Default agents:
    Aurora  - Researcher
    Cipher  - Coder
    Nova    - Creator
    Pulse   - Analyst
    Quark   - Strategist
    Shield  - Security
    Spark   - Social
    Ink     - Writer
    Nexus   - Manager/Orchestrator
"""

from agents.agent import Agent, AgentRole, AgentState, AgentStatus
from agents.agent_manager import AgentManager
from agents.evaluator_optimizer import EvaluationCriteria, EvaluationResult, EvaluatorOptimizer
from agents.message_bus import (
    DeadLetterQueue,
    Message,
    MessageBus,
    MessagePriority,
    MessageType,
)
from agents.orchestrator import Orchestrator, OrchestratorReport, WorkerResult
from agents.processes import (
    ConsensusProcess,
    HierarchicalProcess,
    ParallelProcess,
    Process,
    ProcessResult,
    ProcessStatus,
    ProcessStep,
    SequentialProcess,
)
from agents.typed import (
    AgentResult,
    DepsT,
    OutputT,
    RunContext,
    ToolDef,
    ToolResult,
    TypedAgent,
    TypedAgentError,
)

__all__ = [
    # Core Agent System
    "Agent",
    "AgentRole",
    "AgentStatus",
    "AgentState",
    "AgentManager",
    "Orchestrator",
    "WorkerResult",
    "OrchestratorReport",
    "EvaluatorOptimizer",
    "EvaluationResult",
    "EvaluationCriteria",
    "Process",
    "SequentialProcess",
    "HierarchicalProcess",
    "ParallelProcess",
    "ConsensusProcess",
    "ProcessStatus",
    "ProcessStep",
    "ProcessResult",
    "MessageBus",
    "Message",
    "MessageType",
    "MessagePriority",
    "DeadLetterQueue",
    # Typed Agent (Pydantic AI-inspired)
    "AgentResult",
    "DepsT",
    "OutputT",
    "RunContext",
    "ToolDef",
    "ToolResult",
    "TypedAgent",
    "TypedAgentError",
]
