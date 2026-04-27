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

from .agent import Agent, AgentRole, AgentStatus, AgentState
from .agent_manager import AgentManager
from .orchestrator import Orchestrator, WorkerResult, OrchestratorReport
from .evaluator_optimizer import EvaluatorOptimizer, EvaluationResult, EvaluationCriteria
from .processes import (
    Process,
    SequentialProcess,
    HierarchicalProcess,
    ParallelProcess,
    ConsensusProcess,
    ProcessStatus,
    ProcessStep,
    ProcessResult,
)
from .message_bus import (
    MessageBus,
    Message,
    MessageType,
    MessagePriority,
    DeadLetterQueue,
)

__all__ = [
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
]
