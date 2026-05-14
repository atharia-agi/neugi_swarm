"""
NEUGI Swarm v2 - Autonomous Multi-Agent Framework
==================================================

Version: 2.1.3

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

import logging
import os
import sys

logger = logging.getLogger(__name__)

# Ensure package submodules are importable when running as `python -m neugi_swarm_v2.*`
_PACKAGE_DIR = os.path.dirname(os.path.abspath(__file__))
if _PACKAGE_DIR not in sys.path:
    sys.path.insert(0, _PACKAGE_DIR)

__version__ = "2.1.3"
__author__ = "NEUGI Team"

# -- Core Systems ------------------------------------------------------------

from neugi_swarm_v2.a2a import (
    A2AChannel,
    A2AError,
    A2AMessage,
    A2AMessageType,
    A2APriority,
    A2AProtocol,
    AgentCapability,
    AgentNotFoundError,
    AgentRegistration,
    MessageExpiredError,
)
from neugi_swarm_v2.agents import (
    Agent,
    AgentManager,
    AgentResult,
    AgentRole,
    AgentState,
    AgentStatus,
    ConsensusProcess,
    DeadLetterQueue,
    DepsT,
    EvaluationCriteria,
    EvaluationResult,
    EvaluatorOptimizer,
    HierarchicalProcess,
    Message,
    MessageBus,
    MessagePriority,
    MessageType,
    Orchestrator,
    OrchestratorReport,
    OutputT,
    ParallelProcess,
    Process,
    ProcessResult,
    ProcessStatus,
    ProcessStep,
    RunContext,
    SequentialProcess,
    ToolDef,
    ToolResult,
    TypedAgent,
    TypedAgentError,
    WorkerResult,
)
from neugi_swarm_v2.assistant import NeugiAssistantV2
from neugi_swarm_v2.autonomous import (
    ActionResult,
    ActivityPriority,
    ActivityReport,
    ActivityReporter,
    ActivityStatus,
    ActivityType,
    AutonomousActivity,
    AutonomousLoop,
    Decision,
    DecisionCriteria,
    DecisionOutcome,
    DecisionType,
    ExecutionContext,
    ExecutionResult,
    ExecutionType,
    IdleObserver,
    LoopConfig,
    LoopError,
    LoopResult,
    LoopState,
    Observation,
    ObservationType,
    ProactiveDecisionEngine,
    ReportChannel,
    ReportSeverity,
    RiskAssessment,
    SelfDirectedExecutor,
    ValueAssessment,
)
from neugi_swarm_v2.cli.rescue_wizard import (
    RescueWizard,
    WizardError,
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
from neugi_swarm_v2.config import (
    AgentConfig,
    ContextConfig,
    LLMConfig,
    MemoryConfig,
    NeugiConfig,
    NeugiSessionConfig,
    SkillConfig,
    load_config,
)
from neugi_swarm_v2.context import (
    BootstrapFile,
    BudgetAllocation,
    BudgetError,
    BudgetReport,
    CacheError,
    CacheStability,
    CacheStats,
    ContextInjector,
    ContextItem,
    ContextScope,
    InjectionError,
    InjectionResult,
    ModelPreset,
    PromptAssemblyError,
    PromptDiff,
    PromptFingerprint,
    PromptMode,
    PromptResult,
    PromptSection,
    SectionBudget,
    SectionConfig,
    TokenBudget,
)
from neugi_swarm_v2.context import (
    PromptAssembler as ContextPromptAssembler,
)
from neugi_swarm_v2.context.soul_engine import SoulEngine
from neugi_swarm_v2.dashboard.websocket import (
    WebSocketError,
    WebSocketHandler,
    WebSocketServer,
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
from neugi_swarm_v2.llm_multimodal import (
    ImageMessage,
    MultimodalProvider,
    VisionComputerUse,
)
from neugi_swarm_v2.llm_provider import (
    AnthropicCompatibleProvider,
    ErrorType,
    LLMProvider,
    LLMResponse,
    OllamaProvider,
    OpenAICompatibleProvider,
    ProviderConfig,
    ProviderType,
    ToolCall,
)
from neugi_swarm_v2.memory import (
    DreamConfig,
    DreamingEngine,
    DreamPhase,
    DreamResult,
    MemoryEntry,
    MemoryError,
    MemoryScope,
    MemorySlice,
    MemorySystem,
    MemoryTier,
    ScopeError,
    ScopePath,
    ScoreComponents,
    ScoreConfig,
    ScoringEngine,
)
from neugi_swarm_v2.memory.embeddings import (
    EmbeddingEngine,
    VectorMemoryIndex,
)
from neugi_swarm_v2.model_capability_router import (
    CapabilityProfile,
    CapabilityProfileBuilder,
    CapabilityRouter,
    ModelTier,
    TaskComplexity,
)
from neugi_swarm_v2.model_registry import ModelCapabilities, ModelCapabilityDetector
from neugi_swarm_v2.response_format import (
    Citation,
    CodeBlock,
    ResponseFormatter,
    ResponseMetadata,
    ResponseSection,
    StructuredResponse,
    ThinkingBlock,
)
from neugi_swarm_v2.session import (
    CompactionConfig,
    CompactionEngine,
    CompactionStrategy,
    MessageQueuePolicy,
    Session,
    SessionCheckpoint,
    SessionConfig,
    SessionIsolationMode,
    SessionManager,
    SessionMetadata,
    SessionRegistry,
    SessionState,
    SteeringConfig,
    SteeringEngine,
    SteeringHistory,
    SteeringMessage,
    SteeringPriority,
    Transcript,
    TranscriptEntry,
    TranscriptFormat,
    TranscriptSearch,
)
from neugi_swarm_v2.skills import (
    CompactionResult,
    GatingResult,
    MatchResult,
    PromptAssembler,
    PromptTier,
    SkillAction,
    SkillContract,
    SkillFrontmatter,
    SkillLoader,
    SkillManager,
    SkillMatcher,
    SkillParseResult,
    SkillState,
    SkillTier,
)
from neugi_swarm_v2.tools import (
    BrowserAction,
    BrowserConfig,
    BrowserTool,
    BrowserToolError,
    DOMElement,
    SearchResult,
    WebSearch,
    WebSearchConfig,
    WebSearchError,
)
from neugi_swarm_v2.tools.stealth_browser import (
    BrowserFingerprint,
    StealthBrowser,
    StealthConfig,
)

# -- Observability -----------------------------------------------------------
from neugi_swarm_v2.observability import (
    EventBus,
    Event,
    get_event_bus,
    setup_event_bus_persistence,
)

# -- MCP Server ---------------------------------------------------------------
from neugi_swarm_v2.mcp import (
    MCPServer,
    StdioTransport,
    HTTPTransport,
    SSEConnection,
    ToolManager,
    ResourceManager,
    PromptManager,
    MCPBridge,
    create_bridge,
)
from neugi_swarm_v2.mcp.messages import (
    InitializeParams,
    InitializeResult,
    ListPromptsResult,
    ListResourcesResult,
    ListToolsResult,
    CallToolResult,
    ReadResourceResult,
    GetPromptResult,
)
from neugi_swarm_v2.mcp.checkpoint import (
    CheckpointData,
    CheckpointStore,
    ExecutionThread,
    ResilientMCPExecutor,
)
from neugi_swarm_v2.mcp.sse_forwarder import (
    SSEEventForwarder,
    get_sse_forwarder,
    setup_sse_forwarding,
)
from neugi_swarm_v2.mcp.a2a_adapter import (
    MCPA2AAdapter,
    A2AMCPAgent,
    create_a2a_adapter,
)
from neugi_swarm_v2.mcp.cli_ext import (
    MCPCliExtension,
    extend_cli,
)

# -- Unified Entry Point -----------------------------------------------------


class NeugiSwarmV2:
    """Unified entry point for the NEUGI Swarm v2 framework.

    Initializes and coordinates all subsystems: memory, skills, sessions,
    context, agents, the MCP server, and the LLM provider.

    Usage:
        swarm = NeugiSwarmV2(base_dir="/path/to/neugi")
        response = swarm.chat("Hello, NEUGI!")
        print(response.text)
    """

    def __init__(
        self,
        base_dir: str | None = None,
        config_path: str | None = None,
        llm_provider: LLMProvider | None = None,
        enable_mcp: bool = True,
        enable_mcp_bridge: bool = True,
        enable_mcp_sse: bool = True,
        mcp_port: int = 17902,
        **kwargs,
    ) -> None:
        """Initialize all NEUGI v2 subsystems.

        Args:
            base_dir: Root directory for NEUGI data. Defaults to ~/.neugi.
            config_path: Path to config.json. Auto-detected if None.
            llm_provider: Pre-configured LLM provider. Auto-created if None.
            enable_mcp: Enable MCP server (default: True).
            enable_mcp_bridge: Connect MCP to NEUGI subsystems (default: True).
            enable_mcp_sse: Enable SSE for browser clients (default: True).
            mcp_port: Port for MCP HTTP/SSE server (default: 17902).
            **kwargs: Override any config values.
        """
        self.config = load_config(base_dir, config_path, **kwargs)

        if llm_provider is not None:
            self.llm = llm_provider
        else:
            self.llm = self._create_llm_provider()

        # Build capability profile from config or auto-detect from model
        self.capability_profile = self._build_capability_profile()

        # Multi-model routing (optional — configured in config.json)
        self.model_router = self._init_model_router()

        self.memory = MemorySystem(
            base_dir=str(self.config.memory_dir),
            daily_ttl_days=self.config.memory.daily_ttl_days,
            enable_vec=True,
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

        # Soul / identity engine (SOUL.md pattern)
        self.soul = SoulEngine(
            base_dir=str(self.config.neugi_dir),
            memory_system=self.memory,
        )
        if not self.soul.exists():
            self.soul.init_defaults()

        self.prompt_assembler = ContextPromptAssembler(
            base_dir=str(self.config.neugi_dir),
            agent_id="neugi",
            agent_name="NEUGI",
            agent_role="Autonomous AI Agent",
            model_max_chars=self.config.context.max_chars,
            skill_injector=self._inject_skills,
            memory_injector=self._inject_memory,
            soul_engine=self.soul,
            capability_profile=self.capability_profile,
        )

        self.token_budget = TokenBudget(
            model=self.config.llm.model,
            total_tokens=self.config.context.max_tokens,
            safety_margin=self.config.context.safety_margin,
        )

        self._setup_compaction()

        # Observability: event bus persistence
        self._init_event_bus_persistence()

        # Observability: memory leak monitor
        self._memory_monitor = None
        self._init_memory_monitor()

        # Autonomous loop (pro-active behavior during idle)
        self.autonomous_loop: AutonomousLoop | None = None
        self._init_autonomous_loop(
            enabled=kwargs.get("autonomous", True),
            autostart=kwargs.get("autostart", True),
        )

        # MCP Server (opt-in, default enabled)
        self.mcp_server: MCPServer | None = None
        self.mcp_bridge: MCPBridge | None = None
        self.mcp_sse_forwarder: SSEEventForwarder | None = None
        if enable_mcp:
            self._init_mcp_server(port=mcp_port, enable_sse=enable_mcp_sse)
            if enable_mcp_bridge:
                self._init_mcp_bridge()

    def _init_mcp_server(self, port: int = 17902, enable_sse: bool = True) -> None:
        """Initialize the MCP server with HTTP transport and SSE support."""
        try:
            from neugi_swarm_v2.mcp.server import MCPServer
            from neugi_swarm_v2.mcp.transport import HTTPTransport

            transport = HTTPTransport(
                host="127.0.0.1",
                port=port,
                enable_sse=enable_sse,
            )
            self.mcp_server = MCPServer(transport=transport)
            logger.info("MCP server initialized on port %d (sse=%s)", port, enable_sse)
        except Exception as e:
            logger.warning("MCP server initialization skipped: %s", e)
            self.mcp_server = None

    def _init_mcp_bridge(self) -> None:
        """Connect the MCP server to NEUGI subsystems via bridge."""
        if not self.mcp_server:
            return
        try:
            from neugi_swarm_v2.mcp.bridge import MCPBridge, create_bridge

            self.mcp_bridge = create_bridge(self.mcp_server, self)

            # Set backward reference
            self.mcp_server.set_neugi(self)
            self.mcp_server.set_bridge(self.mcp_bridge)

            # Set up SSE forwarding
            if isinstance(self.mcp_server.transport, HTTPTransport):
                from neugi_swarm_v2.mcp.sse_forwarder import setup_sse_forwarding
                self.mcp_sse_forwarder = setup_sse_forwarding(
                    self.mcp_server.transport
                )
                # Subscribe to core events
                bus = get_event_bus()
                for event_name in ["tool_execution_success", "tool_execution_failure"]:
                    bus.subscribe(event_name, self._on_tool_event)

            logger.info("MCP bridge connected to NEUGI subsystems")
        except Exception as e:
            logger.warning("MCP bridge initialization failed: %s", e)

    def _on_tool_event(self, event: Event) -> None:
        """Forward tool events to MCP SSE clients."""
        if not self.mcp_sse_forwarder:
            return
        try:
            self.mcp_sse_forwarder.transport.publish_sse_event(
                event.name,
                {
                    "payload": event.payload,
                    "source": event.source,
                    "timestamp": event.timestamp.isoformat(),
                },
            )
        except Exception:
            pass

    def _init_autonomous_loop(self, enabled: bool = True, autostart: bool = True) -> None:
        """Initialize the autonomous loop for pro-active behavior."""
        if not enabled:
            logger.info("AutonomousLoop disabled by user")
            return
        try:
            config = LoopConfig(enabled=True, autostart=autostart)
            self.autonomous_loop = AutonomousLoop(swarm=self, config=config)
            logger.info("AutonomousLoop initialized and auto-started")
        except Exception as e:
            logger.warning("Failed to initialize AutonomousLoop: %s", e)
            self.autonomous_loop = None

    def _init_event_bus_persistence(self) -> None:
        """Wire event bus persistence from config."""
        try:
            from neugi_swarm_v2.observability.event_bus import setup_event_bus_persistence
            obs = self.config.observability
            if obs.enabled:
                db_path = str(self.config.data_dir / "events.db")
                setup_event_bus_persistence(db_path)
                logger.info("Event bus persistence enabled: %s", db_path)
        except Exception as e:
            logger.debug("Event bus persistence skipped: %s", e)

    def _init_memory_monitor(self) -> None:
        """Start memory leak detector if observability enabled."""
        try:
            obs = self.config.observability
            if obs.enabled:
                from neugi_swarm_v2.observability.memory_monitor import setup_memory_monitor
                self._memory_monitor = setup_memory_monitor(
                    compaction_callback=self._on_memory_critical,
                )
                logger.info("Memory leak monitor started")
        except Exception as e:
            logger.debug("Memory monitor skipped: %s", e)
            self._memory_monitor = None

    def _on_memory_critical(self) -> None:
        """Callback when memory monitor detects critical usage."""
        logger.warning("Critical memory usage - triggering compaction")
        try:
            if hasattr(self.memory, "consolidate"):
                self.memory.consolidate()
            self._setup_compaction()
        except Exception as e:
            logger.error("Memory compaction failed: %s", e)

    def start_autonomous(self) -> bool:
        """Explicitly start the autonomous loop (idempotent)."""
        if self.autonomous_loop is None:
            self._init_autonomous_loop()
        if self.autonomous_loop:
            self.autonomous_loop.start()
            return True
        return False

    def stop_autonomous(self) -> None:
        """Stop the autonomous loop."""
        if self.autonomous_loop:
            self.autonomous_loop.stop()

    @property
    def is_autonomous_running(self) -> bool:
        """Whether the autonomous loop is currently running."""
        if self.autonomous_loop:
            return self.autonomous_loop.state == LoopState.RUNNING
        return False

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

        # Touch autonomous loop to reset idle timer
        if self.autonomous_loop:
            self.autonomous_loop.touch()

        # Log model routing decision
        if self.model_router is not None:
            route = self.model_router.pick_model(message)
            if route is not None:
                logger.info(
                    "Model routing: task -> %s (provider=%s, model=%s, tier=%s)",
                    route.name,
                    route.provider,
                    route.model,
                    route.tier,
                )

        assistant = NeugiAssistantV2(
            config=self.config,
            llm=self.llm,
            memory=self.memory,
            skill_manager=self.skill_manager,
            session_manager=self.session_manager,
            prompt_assembler=self.prompt_assembler,
            token_budget=self.token_budget,
            on_user_interaction=(
                self.autonomous_loop.touch if self.autonomous_loop else None
            ),
        )

        return assistant.chat(message, session_id=session_id, streaming=streaming, **kwargs)

    def start_mcp_server(self, port: int = 17902, enable_sse: bool = True) -> None:
        """Start the MCP server if initialized.

        This method starts the MCP server in a background thread.

        Args:
            port: Port to listen on.
            enable_sse: Enable SSE support.
        """
        if not self.mcp_server:
            self._init_mcp_server(port=port, enable_sse=enable_sse)
            if not self.mcp_bridge and self.mcp_server:
                self._init_mcp_bridge()

        if self.mcp_server:
            import threading
            if isinstance(self.mcp_server.transport, HTTPTransport):
                thread = threading.Thread(
                    target=lambda: asyncio.run(
                        self.mcp_server.run_http(
                            host="127.0.0.1",
                            port=port,
                            enable_sse=enable_sse,
                        )
                    ),
                    daemon=True,
                    name="mcp-server",
                )
                thread.start()
                logger.info("MCP server started in background thread")

    def close(self) -> None:
        """Shut down all subsystems gracefully."""
        if self.autonomous_loop:
            self.autonomous_loop.stop()
        if self.mcp_bridge:
            self.mcp_bridge.disconnect()
        if self.mcp_sse_forwarder:
            self.mcp_sse_forwarder.stop()
        self.memory.close()
        self.session_manager.sync()

    def remember(self, note: str, category: str = "Recent Events") -> None:
        """Persist a continuity note to the agent's soul memory."""
        if hasattr(self, "soul"):
            self.soul.append_memory(note, category=category)

    def _init_model_router(self) -> Any:
        """Initialize multi-model router from config if routing is configured."""
        try:
            from neugi_swarm_v2.multi_model_router import MultiModelRouter
            config_path = self.config.neugi_dir / "config.json"
            if config_path.exists():
                import json
                with open(config_path, encoding="utf-8") as f:
                    raw = json.load(f)
                if raw.get("routing", {}).get("enabled", False):
                    return MultiModelRouter.from_config(raw)
        except Exception:
            pass
        return None

    def _build_capability_profile(self) -> CapabilityProfile:
        """Build capability profile from config or auto-detect from model."""
        cp_cfg = self.config.capability_profile
        if cp_cfg.name:
            return CapabilityProfile(
                name=cp_cfg.name,
                provider=cp_cfg.provider,
                tier=ModelTier(cp_cfg.tier)
                if cp_cfg.tier in ("local", "medium", "cloud")
                else ModelTier.MEDIUM,
                context_length=cp_cfg.context_length,
                supports_tools=cp_cfg.supports_tools,
                supports_vision=cp_cfg.supports_vision,
                supports_json_mode=cp_cfg.supports_json_mode,
                max_tools_per_call=cp_cfg.max_tools_per_call,
                effective_context_ratio=cp_cfg.effective_context_ratio,
                max_memory_entries=cp_cfg.max_memory_entries,
                recommended_prompt_tier=PromptTier(cp_cfg.recommended_prompt_tier)
                if cp_cfg.recommended_prompt_tier in ("minimal", "standard", "maximal")
                else PromptTier.STANDARD,
            )

        llm_cfg = self.config.llm
        detector = ModelCapabilityDetector()
        caps = detector.detect(
            model_name=llm_cfg.model,
            provider=llm_cfg.provider,
        )
        return CapabilityProfileBuilder.build(caps)

    def _resolve_api_key(self) -> str:
        """Resolve API key from env var, SecretManager, or config."""
        env_key = os.environ.get("NEUGI_LLM_API_KEY", "")
        if env_key:
            return env_key

        try:
            from security.secret_manager import SecretManager
            secrets_db = self.config.neugi_dir / "secrets.db"
            if secrets_db.exists():
                manager = SecretManager(db_path=str(secrets_db))
                entry = manager.get_secret("llm_api_key")
                if entry and entry.value:
                    return entry.value
        except Exception:
            pass

        return self.config.llm.api_key

    def _create_llm_provider(self) -> LLMProvider:
        """Create an LLM provider from config."""
        from neugi_swarm_v2.llm_provider import (
            AnthropicCompatibleProvider,
            OllamaProvider,
            OpenAICompatibleProvider,
            ProviderConfig,
            ProviderType,
        )

        llm_cfg = self.config.llm
        provider_type_map = {
            "ollama": ProviderType.OLLAMA,
            "openai": ProviderType.OPENAI_COMPATIBLE,
            "anthropic": ProviderType.ANTHROPIC_COMPATIBLE,
            "gemini": ProviderType.OPENAI_COMPATIBLE,
            "grok": ProviderType.OPENAI_COMPATIBLE,
            "deepseek": ProviderType.OPENAI_COMPATIBLE,
            "groq": ProviderType.OPENAI_COMPATIBLE,
            "mistral": ProviderType.OPENAI_COMPATIBLE,
            "cohere": ProviderType.OPENAI_COMPATIBLE,
            "perplexity": ProviderType.OPENAI_COMPATIBLE,
            "together": ProviderType.OPENAI_COMPATIBLE,
            "fireworks": ProviderType.OPENAI_COMPATIBLE,
            "moonshot": ProviderType.OPENAI_COMPATIBLE,
            "alibaba": ProviderType.OPENAI_COMPATIBLE,
            "zhipu": ProviderType.OPENAI_COMPATIBLE,
            "stepfun": ProviderType.OPENAI_COMPATIBLE,
            "baidu": ProviderType.OPENAI_COMPATIBLE,
            "iflytek": ProviderType.OPENAI_COMPATIBLE,
            "minimax": ProviderType.OPENAI_COMPATIBLE,
            "nvidia": ProviderType.OPENAI_COMPATIBLE,
        }
        ptype = provider_type_map.get(llm_cfg.provider, ProviderType.OPENAI_COMPATIBLE)
        api_key = self._resolve_api_key()
        cfg = ProviderConfig(
            provider_type=ptype,
            base_url=llm_cfg.ollama_url or llm_cfg.base_url or "http://localhost:11434",
            api_key=api_key,
            default_model=llm_cfg.model,
            fallback_model=llm_cfg.fallback_model,
            timeout=int(llm_cfg.timeout_seconds),
            max_retries=llm_cfg.max_retries,
        )
        if ptype == ProviderType.OLLAMA:
            return OllamaProvider(cfg)
        elif ptype == ProviderType.ANTHROPIC_COMPATIBLE:
            return AnthropicCompatibleProvider(cfg)
        else:
            return OpenAICompatibleProvider(cfg)

    def _resolve_skill_tier(self, path: str) -> SkillTier:
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
        try:
            if hasattr(self.session_manager, "register_pre_compact_hook"):
                self.session_manager.register_pre_compact_hook(
                    lambda: self.memory.sync() if hasattr(self.memory, "sync") else None
                )
        except Exception as e:
            logger.debug("Compaction setup skipped: %s", e)

    def __enter__(self) -> NeugiSwarmV2:
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
    "SoulEngine",
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
    "AgentResult",
    "DepsT",
    "OutputT",
    "RunContext",
    "ToolDef",
    "ToolResult",
    "TypedAgent",
    "TypedAgentError",
    "ActionType",
    "ComputerAction",
    "ComputerUseConfig",
    "ComputerUseController",
    "SafetyChecker",
    "StepResult",
    "TaskResult",
    "Benchmark",
    "BenchmarkResult",
    "BrowserBenchmark",
    "EvalHarness",
    "EvalResult",
    "RegressionReport",
    "SkillBenchmark",
    "WebSearchBenchmark",
    "WebSearch",
    "WebSearchConfig",
    "SearchResult",
    "WebSearchError",
    "BrowserTool",
    "BrowserConfig",
    "BrowserAction",
    "DOMElement",
    "BrowserToolError",
    "ImageMessage",
    "MultimodalProvider",
    "VisionComputerUse",
    "StealthBrowser",
    "StealthConfig",
    "BrowserFingerprint",
    "A2AChannel",
    "A2AError",
    "A2AMessage",
    "A2AMessageType",
    "A2APriority",
    "A2AProtocol",
    "AgentCapability",
    "AgentNotFoundError",
    "AgentRegistration",
    "MessageExpiredError",
    "EmbeddingEngine",
    "VectorMemoryIndex",
    "WebSocketError",
    "WebSocketHandler",
    "WebSocketServer",
    "CodeBlock",
    "Citation",
    "ResponseFormatter",
    "ResponseMetadata",
    "ResponseSection",
    "StructuredResponse",
    "ThinkingBlock",
    "AutonomousLoop",
    "LoopConfig",
    "LoopState",
    "LoopError",
    "LoopResult",
    "AutonomousActivity",
    "ActivityType",
    "ActivityPriority",
    "ActivityStatus",
    "IdleObserver",
    "Observation",
    "ObservationType",
    "ProactiveDecisionEngine",
    "Decision",
    "DecisionType",
    "DecisionOutcome",
    "DecisionCriteria",
    "RiskAssessment",
    "ValueAssessment",
    "SelfDirectedExecutor",
    "ExecutionResult",
    "ExecutionType",
    "ExecutionContext",
    "ActionResult",
    "ActivityReporter",
    "ActivityReport",
    "ReportChannel",
    "ReportSeverity",
    "RescueWizard",
    "WizardError",
    "EventBus",
    "Event",
    "get_event_bus",
    "setup_event_bus_persistence",
    # MCP Server
    "MCPServer",
    "StdioTransport",
    "HTTPTransport",
    "SSEConnection",
    "ToolManager",
    "ResourceManager",
    "PromptManager",
    "MCPBridge",
    "create_bridge",
    "InitializeParams",
    "InitializeResult",
    "ListPromptsResult",
    "ListResourcesResult",
    "ListToolsResult",
    "CallToolResult",
    "ReadResourceResult",
    "GetPromptResult",
    # MCP Checkpoint
    "CheckpointData",
    "CheckpointStore",
    "ExecutionThread",
    "ResilientMCPExecutor",
    # SSE Forwarder
    "SSEEventForwarder",
    "get_sse_forwarder",
    "setup_sse_forwarding",
    # A2A Adapter
    "MCPA2AAdapter",
    "A2AMCPAgent",
    "create_a2a_adapter",
    # CLI
    "MCPCliExtension",
    "extend_cli",
]