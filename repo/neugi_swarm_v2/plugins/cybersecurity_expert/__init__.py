"""
Cybersecurity Expert Plugin for NEUGI Swarm.

Enterprise-grade autonomous security assessment using NEUGI's native
plugin system, event bus, and ToolExecutor. No external FastAPI needed.
"""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

# Import observability using absolute path from package root
from observability.event_bus import Event, get_event_bus
# Import plugin SDK from parent plugins directory
from ..plugin_sdk import (
    PluginBase, PluginContext, PluginCapability,
    register_tool, register_skill, register_hook,
)

logger = logging.getLogger(__name__)

# Lazy-loaded components
_knowledge_searcher = None
_scope_validator = None


class CybersecurityExpertPlugin(PluginBase):
    """Main Cybersecurity Expert plugin - LLM-agnostic, tool-rich, compliance-aware."""

    def __init__(self):
        super().__init__()
        self.event_bus = get_event_bus()
        self._kb_path = None
        self._index_path = None
        self.scan_count = 0
        self.vuln_count = 0

    @property
    def name(self) -> str:
        return "Cybersecurity Expert"

    @property
    def version(self) -> str:
        return "1.0.0"

    @property
    def description(self) -> str:
        return "Security assessment agent with OWASP/MITRE/NIST knowledge base"

    def on_load(self, ctx: PluginContext) -> None:
        """Register tools, skills, and hooks."""
        logger.info("Loading Cybersecurity Expert plugin...")

        global _kbs, _scop

        # Resolve paths
        config = ctx.get_config("cybersecurity", {})
        kb_root = config.get("kb_path", str(Path.home() / ".neugi" / "knowledge"))
        index_dir = config.get("index_path", str(Path.home() / ".neugi" / "data" / "kb_index"))

        self._kb_path = Path(kb_root)
        self._index_path = Path(index_dir)
        self._index_path.mkdir(parents=True, exist_ok=True)

        # Register tools
        register_tool("security_scan", self.tool_security_scan,
                      "Run security tools (nmap, nuclei, sqlmap, etc.) on targets")
        register_tool("knowledge_search", self.tool_knowledge_search,
                      "Search the cybersecurity knowledge base (OWASP, MITRE, NIST, CVEs)")
        register_tool("compliance_check", self.tool_compliance_check,
                      "Check targets against compliance frameworks (ISO 27001, GDPR, NIST)")
        register_tool("scope_validate", self.tool_scope_validate,
                      "Validate targets are within authorized scope before scanning")

        # Register skill
        register_skill("cybersecurity_assessment", self)

        # Register hooks
        register_hook("post_init", self._on_post_init)
        register_hook("pre_tool", self._on_pre_tool)

        # Subscribe to events
        self.event_bus.subscribe("tool_execution_success", self._on_tool_success)
        self.event_bus.subscribe("tool_execution_failure", self._on_tool_failure)
        self.event_bus.subscribe("memory_warning", self._on_memory_warning)

        logger.info("Cybersecurity Expert plugin loaded successfully")

    def _on_post_init(self, ctx):
        """Build knowledge index lazily after NEUGI fully initializes."""
        try:
            from .knowledge_indexer import build_knowledge_index
            # Check if we should use vectors (based on availability and config)
            use_vectors = True  # Default to using vectors if available
            config = ctx.get_config("cybersecurity", {})
            if "use_vectors" in config:
                use_vectors = config["use_vectors"]
            
            if not any(self._index_path.glob("*.idx")):
                logger.info("Building knowledge index from %s... (vectors: %s)", self._kb_path, use_vectors)
                build_knowledge_index(str(self._kb_path), str(self._index_path), use_vectors=use_vectors)
                logger.info("Knowledge index ready")
        except Exception as e:
            logger.warning("Knowledge index build deferred: %s", e)

    def _on_pre_tool(self, ctx):
        """Validate tool execution scope before running."""
        tool_name = ctx.get("tool_name", "")
        params = ctx.get("params", {})
        targets = params.get("targets", [])
        if targets:
            from .scope_validator import validate_targets
            result = validate_targets(targets)
            if not result["valid"]:
                ctx["blocked"] = True
                ctx["block_reason"] = result["reason"]
                logger.warning("Blocked tool %s on targets: %s", tool_name, result["reason"])

    def _on_tool_success(self, event: Event) -> None:
        self.scan_count += 1
        payload = event.payload or {}
        vulns = payload.get("vulnerabilities_found", [])
        self.vuln_count += len(vulns)

    def _on_tool_failure(self, event: Event) -> None:
        payload = event.payload or {}
        tool = payload.get("tool", "unknown")
        error = payload.get("error", "unknown")
        logger.warning("Security tool %s failed: %s", tool, error)

    def _on_memory_warning(self, event: Event) -> None:
        logger.info("Memory warning received, consider reducing scan concurrency")

    # -- Tool implementations ---------------------------------------------------

    def tool_security_scan(self, targets: List[str], tools: Optional[List[str]] = None,
                           depth: str = "standard") -> Dict[str, Any]:
        """Execute security tools on targets via NEUGI's ToolExecutor.

        Args:
            targets: List of target domains/IPs
            tools: Tools to run (default: nmap, nuclei)
            depth: scan depth (basic, standard, deep)

        Returns:
            Scan results with vulnerabilities
        """
        from .tool_executor import run_security_tools
        return run_security_tools(targets, tools or ["nmap", "nuclei"], depth)

    def tool_knowledge_search(self, query: str, category: Optional[str] = None,
                               limit: int = 10) -> Dict[str, Any]:
        """Search the cybersecurity knowledge base.

        Args:
            query: Search query (e.g. "SQL injection prevention")
            category: Filter by folder (frameworks, tools, vulns)
            limit: Max results

        Returns:
            Search results with relevance scores
        """
        from .knowledge_searcher import search_knowledge
        return search_knowledge(str(self._index_path), query, category, limit)

    def tool_compliance_check(self, targets: List[str],
                               frameworks: Optional[List[str]] = None) -> Dict[str, Any]:
        """Check targets against compliance frameworks.

        Args:
            targets: List of targets
            frameworks: Compliance frameworks (ISO27001, GDPR, NIST)

        Returns:
            Compliance assessment results
        """
        from .compliance_checker import check_compliance
        return check_compliance(targets, frameworks or ["NIST", "ISO27001"])

    def tool_scope_validate(self, targets: List[str]) -> Dict[str, Any]:
        """Validate targets before scanning.

        Args:
            targets: List of target domains/IPs

        Returns:
            Validation result with any warnings
        """
        from .scope_validator import validate_targets
        return validate_targets(targets)


def activate() -> CybersecurityExpertPlugin:
    """Entry point for the plugin system."""
    return CybersecurityExpertPlugin()