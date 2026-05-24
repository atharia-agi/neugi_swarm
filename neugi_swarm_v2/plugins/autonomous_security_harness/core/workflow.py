"""
LangGraph workflow for Autonomous Security Harness.
"""
from __future__ import annotations

from typing import TypedDict

try:
    from langgraph.graph import END, StateGraph
except ImportError:
    StateGraph = None  # type: ignore[misc,assignment]
    END = None  # type: ignore[assignment]

# Import node functions
from plugins.autonomous_security_harness.core.knowledge.indexer import KnowledgeSearcher
from plugins.autonomous_security_harness.core.nodes.compliance_node import compliance_node
from plugins.autonomous_security_harness.core.nodes.network_scan_node import network_scan_node
from plugins.autonomous_security_harness.core.nodes.recon_node import recon_node
from plugins.autonomous_security_harness.core.nodes.report_node import report_node
from plugins.autonomous_security_harness.core.nodes.router import route_after_recon
from plugins.autonomous_security_harness.core.nodes.web_scan_node import web_scan_node
from plugins.autonomous_security_harness.core.security.audit_logger import ImmutableAuditLogger
from plugins.autonomous_security_harness.core.security.auth_gate import AuthGate
from plugins.autonomous_security_harness.core.security.scope_validator import ScopeValidator

# Import components that will be passed in
from plugins.autonomous_security_harness.core.tools.executor import ToolExecutor


class AgentState(TypedDict):
    """State shared across nodes in the LangGraph workflow."""
    task_id: str
    user_id: str
    targets: list[str]
    scope: dict  # allowed targets, risk level
    findings: list[dict]  # appended by nodes
    audit_trail: list[dict]  # immutable log
    compliance_tags: list[str]
    error: str | None
    next: str  # routing


def create_security_workflow(
    tool_executor: ToolExecutor,
    knowledge_searcher: KnowledgeSearcher,
    scope_validator: ScopeValidator,
    auth_gate: AuthGate | None,
    audit_logger: ImmutableAuditLogger
) -> StateGraph:
    """
    Create and compile the LangGraph workflow for security assessment.

    Args:
        tool_executor: ToolExecutor instance for running security tools
        knowledge_searcher: KnowledgeSearcher for consulting security knowledge
        scope_validator: ScopeValidator for checking targets
        auth_gate: AuthGate for high-risk tool approvals (can be None)
        audit_logger: ImmutableAuditLogger for audit trail

    Returns:
        Compiled LangGraph application
    """
    # We'll create a wrapper for each node that injects the dependencies
    # In a real implementation, we might use dependency injection or partial functions

    # For now, we'll assume the nodes are designed to accept these as parameters
    # But since LangGraph nodes must accept only the state, we need to bind the dependencies.
    # We'll create a closure or a class for each node that holds the dependencies.

    # However, to keep it simple and aligned with the user's example, we'll assume
    # the nodes are implemented as methods of a class that holds the dependencies.
    # But the user's example shows standalone functions.

    # Given the complexity, we'll create a simple version where the nodes are
    # defined inside this function and have access to the dependencies via closure.

    # Define the nodes with access to the dependencies
    def recon_node_wrapper(state: AgentState) -> AgentState:
        return recon_node(state, tool_executor, knowledge_searcher, scope_validator, auth_gate, audit_logger)

    def web_scan_node_wrapper(state: AgentState) -> AgentState:
        return web_scan_node(state, tool_executor, knowledge_searcher, scope_validator, auth_gate, audit_logger)

    def network_scan_node_wrapper(state: AgentState) -> AgentState:
        return network_scan_node(state, tool_executor, knowledge_searcher, scope_validator, auth_gate, audit_logger)

    def compliance_node_wrapper(state: AgentState) -> AgentState:
        return compliance_node(state, tool_executor, knowledge_searcher, scope_validator, auth_gate, audit_logger)

    def report_node_wrapper(state: AgentState) -> AgentState:
        return report_node(state, tool_executor, knowledge_searcher, scope_validator, auth_gate, audit_logger)

    # Build the graph
    workflow = StateGraph(AgentState)

    # Add nodes
    workflow.add_node("recon", recon_node_wrapper)
    workflow.add_node("web_scan", web_scan_node_wrapper)
    workflow.add_node("network_scan", network_scan_node_wrapper)
    workflow.add_node("compliance", compliance_node_wrapper)
    workflow.add_node("report", report_node_wrapper)

    # Set entry point
    workflow.set_entry_point("recon")

    # Add conditional edges after recon
    workflow.add_conditional_edges(
        "recon",
        route_after_recon,  # This function should return either "web_scan" or "network_scan"
        {
            "web_scan": "web_scan",
            "network_scan": "network_scan"
        }
    )

    # Add edges
    workflow.add_edge("web_scan", "compliance")
    workflow.add_edge("network_scan", "compliance")
    workflow.add_edge("compliance", "report")
    workflow.add_edge("report", END)

    # Note: We are not adding a checkpointer here because the user's example
    # shows adding it at compile time. We'll leave it to the caller to compile
    # with a checkpointer if desired, or we can add a default one.
    # However, the user's example includes:
    #   checkpointer = PostgresSaver.from_conn_string(DB_URL)
    #   app = graph.compile(checkpointer=checkpointer)
    #
    # We'll return the StateGraph and let the caller compile it with a checkpointer.
    # But the plugin's __init__.py expects an compiled app. So we need to compile it.
    #
    # Since we don't have a Postgres connection string in this example, we'll
    # use a simple in-memory checkpointer for demonstration, or we can leave it
    # without a checkpointer and note that it's required for production.
    #
    # For the purpose of this example, we'll compile without a checkpointer and
    # note that in production, a checkpointer should be used.
    #
    # However, the user's example in the plugin's __init__.py does not show
    # compiling the graph. It shows:
    #   from .core.workflow import create_security_workflow
    #   _app = create_security_workflow(...)
    #
    # So we'll return the compiled graph. We'll use a MemorySaver for simplicity
    # in this example, but note that for production, PostgresSaver should be used.
    #
    # Let's try to import MemorySaver from langgraph.checkpoint.memory
    try:
        from langgraph.checkpoint.memory import MemorySaver
        checkpointer = MemorySaver()
        app = workflow.compile(checkpointer=checkpointer)
    except ImportError:
        # If MemorySaver is not available, compile without checkpointer
        app = workflow.compile()

    return app
