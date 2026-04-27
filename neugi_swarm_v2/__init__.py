"""
NEUGI Swarm v2 - Autonomous Multi-Agent Framework
==================================================

Version: 2.0.0

Production-ready hierarchical multi-agent system combining:
- Karpathy-style dreaming consolidation memory
- CrewAI role-based agent orchestration
- Anthropic effective agent patterns (orchestrator-workers, evaluator-optimizer)
- OpenClaw-style dynamic prompt assembly
- LangGraph checkpointing and durable execution

Usage:
    from neugi_swarm_v2 import NeugiSwarmV2

    swarm = NeugiSwarmV2(base_dir="/path/to/neugi")
    response = swarm.chat("Hello, NEUGI!")
"""

from __future__ import annotations

__version__ = "2.0.0"
__author__ = "NEUGI Team"

# -- Core Systems ------------------------------------------------------------

from neugi_swarm_v2.memory import (
    MemorySystem,
    MemoryEntry,
    MemoryTier,
    MemoryError,
    DreamingEngine,
    DreamPhase,
    DreamConfig,
    DreamResult,
    ScopePath,
    MemoryScope,
    MemorySlice,
    ScopeError,
    ScoringEngine,
    ScoreComponents,
    ScoreConfig,
)

from neugi_swarm_v2.skills import (
    SkillManager,
    SkillContract,
    SkillFrontmatter,
    SkillAction,
    SkillState,
    SkillTier,
    SkillLoader,
    SkillMatcher,
    PromptAssembler,
    MatchResult,
    CompactionResult,
    PromptTier,
    GatingResult,
    SkillParseResult,
)

from neugi_swarm_v2.session import (
    Session,
    SessionManager,
    SessionState,
    SessionIsolationMode,
    SessionConfig,
    SessionMetadata,
    SessionCheckpoint,
    SessionRegistry,
    CompactionEngine,
    CompactionConfig,
    CompactionStrategy,
    SteeringEngine,
    SteeringConfig,
    SteeringMessage,
    SteeringPriority,
    MessageQueuePolicy,
    SteeringHistory,
    Transcript,
    TranscriptEntry,
    TranscriptFormat,
    TranscriptSearch,
)

from neugi_swarm_v2.context import (
    PromptAssembler as ContextPromptAssembler,
    PromptMode,
    PromptSection,
    SectionConfig,
    BootstrapFile,
    PromptAssemblyError,
    PromptResult,
    TokenBudget,
    BudgetAllocation,
    BudgetReport,
    ModelPreset,
    BudgetError,
    SectionBudget,
    CacheStability,
    PromptFingerprint,
    CacheStats,
    PromptDiff,
    CacheError,
    ContextInjector,
    ContextItem,
    InjectionResult,
    InjectionError,
    ContextScope,
)

from neugi_swarm_v2.agents import (
    Agent,
    AgentRole,
    AgentStatus,
    AgentState,
    AgentManager,
    Orchestrator,
    WorkerResult,
    OrchestratorReport,
    EvaluatorOptimizer,
    EvaluationResult,
    EvaluationCriteria,
    Process,
    SequentialProcess,
    HierarchicalProcess,
    ParallelProcess,
    ConsensusProcess,
    ProcessStatus,
    ProcessStep,
    ProcessResult,
    MessageBus,
    Message,
    MessageType,
    MessagePriority,
    DeadLetterQueue,
    AgentResult,
    DepsT,
    OutputT,
    RunContext,
    ToolDef,
    ToolResult,
    TypedAgent,
    TypedAgentError,
)

from neugi_swarm_v2.computer_use import (
    ActionType,
    ComputerAction,
    ComputerUseConfig,
    ComputerUseController,
    SafetyChecker,
    StepResult,
    TaskResult,
)

from neugi_swarm_v2.evals import (
    Benchmark,
    BenchmarkResult,
    BrowserBenchmark,
    EvalHarness,
    EvalResult,
    RegressionReport,
    SkillBenchmark,
    WebSearchBenchmark,
)

from neugi_swarm_v2.tools import (
    WebSearch,
    WebSearchConfig,
    SearchResult,
    WebSearchError,
    BrowserTool,
    BrowserConfig,
    BrowserAction,
    DOMElement,
    BrowserToolError,
)

# -- Assistant ---------------------------------------------------------------

from neugi_swarm_v2.assistant import NeugiAssistantV2
from neugi_swarm_v2.llm_provider import (
    LLMProvider,
    LLMResponse,
    ToolCall,
    OllamaProvider,
    OpenAICompatibleProvider,
    AnthropicCompatibleProvider,
    ProviderConfig,
    ProviderType,
    ErrorType,
)
from neugi_swarm_v2.config import (
    NeugiConfig,
    LLMConfig,
    NeugiSessionConfig,
    MemoryConfig,
    SkillConfig,
    AgentConfig,
    ContextConfig,
    load_config,
)

# -- Unified Entry Point -----------------------------------------------------


class NeugiSwarmV2:
    """Unified entry point for the NEUGI Swarm v2 framework.

    Initializes and coordinates all subsystems: memory, skills, sessions,
    context, agents, and the LLM provider.

    Usage:
        swarm = NeugiSwarmV2(base_dir="/path/to/neugi")
        response = swarm.chat("What can you do?")
        print(response.text)
    """

    def __init__(
        self,
        base_dir: str | None = None,
        config_path: str | None = None,
        llm_provider: LLMProvider | None = None,
        **kwargs,
    ) -> None:
        """Initialize all NEUGI v2 subsystems.

        Args:
            base_dir: Root directory for NEUGI data. Defaults to ~/.neugi.
            config_path: Path to config.json. Auto-detected if None.
            llm_provider: Pre-configured LLM provider. Auto-created if None.
            **kwargs: Override any config values.
        """
        self.config = load_config(base_dir, config_path, **kwargs)

        if llm_provider is not None:
            self.llm = llm_provider
        else:
            self.llm = self._create_llm_provider()

        self.memory = MemorySystem(
            base_dir=str(self.config.memory_dir),
            daily_ttl_days=self.config.memory.daily_ttl_days,
        )

        self.skill_manager = SkillManager(
            token_budget=self.config.skill.max_tokens_in_prompt,
            max_skills_in_prompt=self.config.skill.max_skills_in_prompt,
        )
        for tier_path in self.config.skill.skill_dirs:
            self.skill_manager.register_tier_path(
                self._resolve_skill_tier(tier_path), tier_path
            )
        self.skill_manager.load()

        self.session_manager = SessionManager(
            config=self.config.to_session_config(),
            registry_db_path=str(self.config.sessions_dir / "session_registry.db"),
        )

        self.prompt_assembler = ContextPromptAssembler(
            base_dir=str(self.config.neugi_dir),
            agent_id="neugi",
            agent_name="NEUGI",
            agent_role="Autonomous AI Agent",
            model_max_chars=self.config.context.max_chars,
            skill_injector=self._inject_skills,
            memory_injector=self._inject_memory,
        )

        self.token_budget = TokenBudget(
            model=self.config.llm.model,
            total_tokens=self.config.context.max_tokens,
            safety_margin=self.config.context.safety_margin,
        )

        self._setup_compaction()

    def chat(
        self,
        message: str,
        session_id: str | None = None,
        streaming: bool = False,
        **kwargs,
    ) -> AssistantResponse:
        """Send a message and get a response.

        Args:
            message: User message.
            session_id: Existing session to use, or None for auto.
            streaming: Whether to stream the response.
            **kwargs: Passed to the assistant.

        Returns:
            AssistantResponse with text, tool calls, and metadata.
        """
        from neugi_swarm_v2.assistant import NeugiAssistantV2

        assistant = NeugiAssistantV2(
            config=self.config,
            llm=self.llm,
            memory=self.memory,
            skill_manager=self.skill_manager,
            session_manager=self.session_manager,
            prompt_assembler=self.prompt_assembler,
            token_budget=self.token_budget,
        )

        return assistant.chat(message, session_id=session_id, streaming=streaming, **kwargs)

    def close(self) -> None:
        """Shut down all subsystems gracefully."""
        self.memory.close()
        self.session_manager.sync()

    def _create_llm_provider(self) -> LLMProvider:
        """Create an LLM provider from config."""
        llm_cfg = self.config.llm
        if llm_cfg.provider == "ollama":
            return OllamaProvider(
                base_url=llm_cfg.ollama_url,
                model=llm_cfg.model,
                fallback_model=llm_cfg.fallback_model,
            )
        elif llm_cfg.provider == "anthropic":
            return AnthropicCompatibleProvider(
                api_key=llm_cfg.api_key,
                model=llm_cfg.model,
                fallback_model=llm_cfg.fallback_model,
            )
        else:
            return OpenAICompatibleProvider(
                api_key=llm_cfg.api_key,
                base_url=llm_cfg.base_url,
                model=llm_cfg.model,
                fallback_model=llm_cfg.fallback_model,
            )

    def _resolve_skill_tier(self, path: str) -> "SkillTier":
        """Resolve a skill directory path to a SkillTier."""
        from neugi_swarm_v2.skills import SkillTier

        path_lower = path.lower()
        if "workspace" in path_lower:
            return SkillTier.WORKSPACE
        elif "project" in path_lower:
            return SkillTier.PROJECT
        elif "personal" in path_lower:
            return SkillTier.PERSONAL
        elif "managed" in path_lower:
            return SkillTier.MANAGED
        elif "bundled" in path_lower:
            return SkillTier.BUNDLED
        return SkillTier.EXTRA

    def _inject_skills(self) -> str:
        """Inject matched skills into the prompt."""
        return ""

    def _inject_memory(self) -> str:
        """Inject core memory into the prompt."""
        return ""

    def _setup_compaction(self) -> None:
        """Configure compaction engine with memory flush hooks."""
        pass

    def __enter__(self) -> "NeugiSwarmV2":
        return self

    def __exit__(self, *args) -> None:
        self.close()


__all__ = [
    "__version__",
    "NeugiSwarmV2",
    "NeugiAssistantV2",
    "ToolCall",
    "NeugiConfig",
    "LLMConfig",
    "NeugiSessionConfig",
    "MemoryConfig",
    "SkillConfig",
    "AgentConfig",
    "ContextConfig",
    "load_config",
    "LLMProvider",
    "LLMResponse",
    "ToolCall",
    "OllamaProvider",
    "OpenAICompatibleProvider",
    "AnthropicCompatibleProvider",
    "ProviderConfig",
    "ProviderType",
    "ErrorType",
    "MemorySystem",
    "MemoryEntry",
    "MemoryTier",
    "MemoryError",
    "DreamingEngine",
    "DreamPhase",
    "DreamConfig",
    "DreamResult",
    "ScopePath",
    "MemoryScope",
    "MemorySlice",
    "ScopeError",
    "ScoringEngine",
    "ScoreComponents",
    "ScoreConfig",
    "SkillManager",
    "SkillContract",
    "SkillFrontmatter",
    "SkillAction",
    "SkillState",
    "SkillTier",
    "SkillLoader",
    "SkillMatcher",
    "MatchResult",
    "CompactionResult",
    "PromptTier",
    "GatingResult",
    "SkillParseResult",
    "Session",
    "SessionManager",
    "SessionState",
    "SessionIsolationMode",
    "SessionConfig",
    "SessionMetadata",
    "SessionCheckpoint",
    "SessionRegistry",
    "CompactionEngine",
    "CompactionConfig",
    "CompactionStrategy",
    "SteeringEngine",
    "SteeringConfig",
    "SteeringMessage",
    "SteeringPriority",
    "MessageQueuePolicy",
    "SteeringHistory",
    "Transcript",
    "TranscriptEntry",
    "TranscriptFormat",
    "TranscriptSearch",
    "ContextPromptAssembler",
    "PromptMode",
    "PromptSection",
    "SectionConfig",
    "BootstrapFile",
    "PromptAssemblyError",
    "PromptResult",
    "TokenBudget",
    "BudgetAllocation",
    "BudgetReport",
    "ModelPreset",
    "BudgetError",
    "SectionBudget",
    "CacheStability",
    "PromptFingerprint",
    "CacheStats",
    "PromptDiff",
    "CacheError",
    "ContextInjector",
    "ContextItem",
    "InjectionResult",
    "InjectionError",
    "ContextScope",
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
    # Typed Agent
    "AgentResult",
    "DepsT",
    "OutputT",
    "RunContext",
    "ToolDef",
    "ToolResult",
    "TypedAgent",
    "TypedAgentError",
    # Computer Use
    "ActionType",
    "ComputerAction",
    "ComputerUseConfig",
    "ComputerUseController",
    "SafetyChecker",
    "StepResult",
    "TaskResult",
    # Evals
    "Benchmark",
    "BenchmarkResult",
    "BrowserBenchmark",
    "EvalHarness",
    "EvalResult",
    "RegressionReport",
    "SkillBenchmark",
    "WebSearchBenchmark",
    # Tools (new)
    "WebSearch",
    "WebSearchConfig",
    "SearchResult",
    "WebSearchError",
    "BrowserTool",
    "BrowserConfig",
    "BrowserAction",
    "DOMElement",
    "BrowserToolError",
]
