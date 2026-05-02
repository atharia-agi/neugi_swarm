"""
Autonomous Security Harness Plugin for NEUGI Swarm.
"""
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from plugins.plugin_sdk import (
    PluginBase, PluginContext, PluginCapability,
    register_tool, register_skill, register_hook,
)

logger = logging.getLogger(__name__)

# Lazy-loaded components
_app = None
_tool_executor = None
_knowledge_indexer = None
_knowledge_searcher = None
_scope_validator = None
_auth_gate = None
_audit_logger = None


class AutonomousSecurityHarnessPlugin(PluginBase):
    """Advanced LangGraph-based autonomous security assessment harness."""

    def __init__(self):
        super().__init__()
        self.event_bus = None  # Will be set in on_load
        self._config = None

    @property
    def name(self) -> str:
        return "Autonomous Security Harness"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "LangGraph-based security assessment with Docker sandbox, safety middleware, and audit logging"

    def on_load(self, ctx: PluginContext) -> None:
        """Register tools, skills, and hooks."""
        logger.info("Loading Autonomous Security Harness plugin...")
        # Note: Event bus integration skipped for now; can be added later if needed
        self.event_bus = None
        self._config = ctx.get_config("autonomous_security_harness", {})

        # Initialize components
        self._initialize_components()

        # Register tools
        register_tool("security_assessment", self.tool_security_assessment,
                      "Run autonomous security assessment on targets")
        register_tool("harness_status", self.tool_harness_status,
                      "Get status of the security harness")
        register_tool("workflow_history", self.tool_workflow_history,
                      "Get history of workflow executions")

        # Register skill
        register_skill("autonomous_security_assessment", self)

        # Register hooks
        register_hook("post_init", self._on_post_init)
        register_hook("pre_tool", self._on_pre_tool)

        # Subscribe to events (skipped for now)
        # if self.event_bus:
        #     self.event_bus.subscribe("tool_execution_success", self._on_tool_success)
        #     self.event_bus.subscribe("tool_execution_failure", self._on_tool_failure)
        #     self.event_bus.subscribe("memory_warning", self._on_memory_warning)

        logger.info("Autonomous Security Harness plugin loaded successfully")

    def _initialize_components(self) -> None:
        """Initialize the core components of the harness."""
        global _app, _tool_executor, _knowledge_indexer, _knowledge_searcher
        global _scope_validator, _auth_gate, _audit_logger

        # Initialize knowledge base
        kb_path = self._config.get("kb_path", str(Path.home() / ".neugi" / "knowledge"))
        index_path = self._config.get("index_path", str(Path.home() / ".neugi" / "data" / "kb_index"))
        use_vectors = self._config.get("use_vectors", True)

        # Import and initialize knowledge indexer and searcher
        try:
            from .core.knowledge.indexer import KnowledgeIndexer
            from .core.knowledge.searcher import KnowledgeSearcher
            _knowledge_indexer = KnowledgeIndexer(kb_path, index_path)
            # Build index if not exists
            if not any(Path(index_path).glob('*.idx')):
                logger.info("Building knowledge index...")
                _knowledge_indexer.build_index()
            _knowledge_searcher = KnowledgeSearcher(index_path)
            logger.info("Knowledge base initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize knowledge base: {e}")

        # Initialize tool executor (Docker sandbox)
        try:
            from .core.tools.executor import ToolExecutor
            _tool_executor = ToolExecutor()
            logger.info("Tool executor initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize tool executor: {e}")

        # Initialize security components
        try:
            scope_config = self._config.get("scope", {
                "allowed_targets": [],
                "allow_private_ips": False,
                "allowed_ports": list(range(1, 65536))
            })
            _scope_validator = ScopeValidator(scope_config)
            logger.info("Scope validator initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize scope validator: {e}")

        try:
            # Auth gate would need a database session, we'll skip for now in this example
            # In a real implementation, we would connect to a database
            _auth_gate = None  # Placeholder
            logger.info("Auth gate initialized (placeholder)")
        except Exception as e:
            logger.warning(f"Failed to initialize auth gate: {e}")

        try:
            log_path = self._config.get("audit_log_path", str(Path.home() / ".neugi" / "data" / "logs" / "audit.jsonl"))
            _audit_logger = ImmutableAuditLogger(log_path)
            logger.info("Audit logger initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize audit logger: {e}")

        # Initialize the LangGraph application
        try:
            from .core.workflow import create_security_workflow
            _app = create_security_workflow(
                tool_executor=_tool_executor,
                knowledge_searcher=_knowledge_searcher,
                scope_validator=_scope_validator,
                auth_gate=_auth_gate,
                audit_logger=_audit_logger
            )
            logger.info("LangGraph workflow initialized")
        except Exception as e:
            logger.warning(f"Failed to initialize workflow: {e}")

    def _on_post_init(self, ctx):
        """Perform post-initialization tasks."""
        logger.info("Autonomous Security Harness post-initialization complete")

    def _on_pre_tool(self, ctx):
        """Validate tool execution scope before running."""
        tool_name = ctx.get("tool_name", "")
        params = ctx.get("params", {})
        targets = params.get("targets", [])
        if targets and _scope_validator:
            # Validate each target
            for target in targets:
                if not _scope_validator.validate_target(target, tool_name):
                    ctx["blocked"] = True
                    ctx["block_reason"] = f"Target {target} not in allowed scope"
                    logger.warning(f"Blocked tool {tool_name} on target {target}: scope violation")
                    return

    def _on_tool_success(self, event) -> None:
        """Handle successful tool execution."""
        # Log to audit trail
        if _audit_logger:
            _audit_logger.log({
                'event': 'tool_execution_success',
                'tool': event.payload.get('tool'),
                'task_id': event.payload.get('task_id'),
                'duration_ms': event.payload.get('duration_ms')
            })

    def _on_tool_failure(self, event) -> None:
        """Handle failed tool execution."""
        # Log to audit trail
        if _audit_logger:
            _audit_logger.log({
                'event': 'tool_execution_failure',
                'tool': event.payload.get('tool'),
                'task_id': event.payload.get('task_id'),
                'error': event.payload.get('error')
            })

    def _on_memory_warning(self, event) -> None:
        """Handle memory warning."""
        logger.info("Memory warning received in Autonomous Security Harness")
        if _audit_logger:
            _audit_logger.log({
                'event': 'memory_warning',
                'details': event.payload
            })

    # -- Tool implementations ---------------------------------------------------

    def tool_security_assessment(self, targets: List[str], options: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Run autonomous security assessment on targets via LangGraph workflow.

        Args:
            targets: List of target domains/IPs
            options: Optional configuration (scope, depth, etc.)

        Returns:
            Assessment results
        """
        if not _app:
            return {"error": "Security harness not initialized"}

        # Merge options with default config
        config = self._config.copy()
        if options:
            config.update(options)

        # Prepare initial state
        initial_state = {
            "task_id": f"assessment_{len(targets)}targets_{int(time.time())}",
            "user_id": config.get("user_id", "system"),
            "targets": targets,
            "scope": config.get("scope", {}),
            "findings": [],
            "audit_trail": [],
            "compliance_tags": [],
            "error": None,
            "next": "recon"  # Start at recon node
        }

        # Configure LangGraph
        langgraph_config = {"configurable": {"thread_id": initial_state["task_id"]}}

        try:
            # Execute the workflow
            result = _app.ainvoke(initial_state, config=langgraph_config)
            return result
        except Exception as e:
            logger.error(f"Security assessment failed: {e}")
            return {"error": str(e), "task_id": initial_state["task_id"]}

    def tool_harness_status(self) -> Dict[str, Any]:
        """Get status of the security harness."""
        return {
            "plugin": "autonomous_security_harness",
            "status": "loaded",
            "components": {
                "knowledge_base": _knowledge_searcher is not None,
                "tool_executor": _tool_executor is not None,
                "scope_validator": _scope_validator is not None,
                "auth_gate": _auth_gate is not None,
                "audit_logger": _audit_logger is not None,
                "workflow_app": _app is not None
            }
        }

    def tool_workflow_history(self, limit: int = 10) -> Dict[str, Any]:
        """Get history of workflow executions from audit log."""
        if not _audit_logger:
            return {"error": "Audit logger not initialized"}
        
        # In a real implementation, we would query the audit log
        # For now, return placeholder
        return {
            "history": [],
            "count": 0,
            "note": "Workflow history not implemented in this example"
        }


def activate() -> AutonomousSecurityHarnessPlugin:
    """Entry point for the plugin system."""
    return AutonomousSecurityHarnessPlugin()