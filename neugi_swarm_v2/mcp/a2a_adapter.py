"""
A2A-MCP Adapter - Bridges Agent-to-Agent Protocol with MCP Server
=================================================================

Enables MCP clients to participate in NEUGI's agent mesh networking
through the A2A (Agent-to-Agent) protocol. Allows:
- MCP clients to register as agents in the mesh
- Task delegation between MCP clients and NEUGI agents
- Capability discovery across the agent network
- Heartbeat monitoring for connected MCP agents
"""

from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, List, Optional

from a2a import (
    A2AProtocol,
    A2AMessage,
    A2AMessageType,
    A2APriority,
    AgentCapability,
    AgentRegistration,
)
from neugi_swarm_v2.mcp.messages import (
    CallToolResult,
    RequestMessage,
    ResponseMessage,
    NotificationMessage,
)

logger = logging.getLogger(__name__)


class A2AMCPAgent:
    """Represents an MCP client as an A2A agent in the mesh."""

    def __init__(
        self,
        agent_id: str,
        name: str,
        capabilities: List[AgentCapability] | None = None,
        metadata: Dict[str, Any] | None = None,
    ):
        self.agent_id = agent_id
        self.name = name
        self.capabilities = capabilities or []
        self.metadata = metadata or {}
        self._last_heartbeat = 0.0
        self._message_queue: List[A2AMessage] = []

    def to_registration(self) -> AgentRegistration:
        return AgentRegistration(
            agent_id=self.agent_id,
            name=self.name,
            capabilities=self.capabilities,
            metadata={**self.metadata, "source": "mcp_client"},
        )

    def heartbeat(self) -> None:
        import time
        self._last_heartbeat = time.time()

    @property
    def is_alive(self, timeout_seconds: int = 60) -> bool:
        import time
        return (time.time() - self._last_heartbeat) < timeout_seconds

    def to_dict(self) -> dict:
        import time as _time
        return {
            "agent_id": self.agent_id,
            "name": self.name,
            "capabilities": [c.to_dict() for c in self.capabilities],
            "metadata": self.metadata,
            "last_heartbeat": self._last_heartbeat,
            "is_alive": self.is_alive,
            "queued_messages": len(self._message_queue),
        }


class MCPA2AAdapter:
    """Adapter that connects the MCP Server to NEUGI's A2A Protocol.

    This allows MCP clients to:
    1. Register as agents in the NEUGI agent mesh
    2. Send and receive messages through A2A
    3. Delegate tasks to other agents in the mesh
    4. Discover capabilities of other agents
    """

    def __init__(self, a2a_protocol: A2AProtocol, server: Any = None):
        self.a2a = a2a_protocol
        self.server = server
        self._mcp_agents: Dict[str, A2AMCPAgent] = {}
        self._callbacks: Dict[str, Callable] = {}
        self._running = False

    def register_mcp_agent(
        self,
        agent_id: str | None = None,
        name: str = "MCP Client",
        capabilities: List[AgentCapability] | None = None,
        metadata: Dict[str, Any] | None = None,
        message_handler: Callable | None = None,
    ) -> A2AMCPAgent:
        """Register an MCP client as an agent in the A2A mesh.

        Args:
            agent_id: Unique agent ID. Auto-generated if None.
            name: Human-readable agent name.
            capabilities: List of agent capabilities.
            metadata: Additional agent metadata.
            message_handler: Callback for incoming A2A messages.

        Returns:
            The registered A2AMCPAgent instance.
        """
        if agent_id is None:
            agent_id = f"mcp-{uuid.uuid4().hex[:8]}"

        if message_handler:
            self.a2a.register_agent(
                agent_id=agent_id,
                name=name,
                capabilities=capabilities,
                handler=message_handler,
                metadata=metadata,
            )
        else:
            self.a2a.register_agent(
                agent_id=agent_id,
                name=name,
                capabilities=capabilities,
                metadata=metadata,
            )

        agent = A2AMCPAgent(
            agent_id=agent_id,
            name=name,
            capabilities=capabilities,
            metadata=metadata,
        )
        self._mcp_agents[agent_id] = agent
        logger.info("Registered MCP agent: %s (%s)", agent_id, name)
        return agent

    def unregister_mcp_agent(self, agent_id: str) -> bool:
        """Unregister an MCP agent from the mesh."""
        if agent_id in self._mcp_agents:
            self.a2a.unregister_agent(agent_id)
            del self._mcp_agents[agent_id]
            logger.info("Unregistered MCP agent: %s", agent_id)
            return True
        return False

    def send_to_agent(
        self,
        sender_id: str,
        recipient_id: str,
        task: str,
        payload: Dict[str, Any] | None = None,
        priority: A2APriority = A2APriority.NORMAL,
        callback: Callable | None = None,
    ) -> A2AMessage | None:
        """Send a task message to another agent through A2A.

        Args:
            sender_id: Sending agent ID (must be registered)
            recipient_id: Target agent ID
            task: Task description
            payload: Task parameters
            priority: Message priority
            callback: Optional response callback

        Returns:
            Response message if synchronous, None if async
        """
        message = A2AMessage(
            msg_type=A2AMessageType.TASK,
            sender=sender_id,
            recipient=recipient_id,
            task=task,
            payload=payload or {},
            priority=priority,
        )
        return self.a2a.send(recipient_id, message, callback=callback)

    def delegate_task(
        self,
        task: str,
        payload: Dict[str, Any],
        required_capability: str,
        sender: str = "mcp-orchestrator",
    ) -> A2AMessage | None:
        """Delegate a task to the best available agent.

        Args:
            task: Task description
            payload: Task parameters
            required_capability: Capability to look for in agents
            sender: Sender agent ID

        Returns:
            Response from the selected agent
        """
        return self.a2a.delegate(
            task=task,
            payload=payload,
            required_capability=required_capability,
            sender=sender,
        )

    def broadcast(
        self,
        message: A2AMessage,
        capability_filter: str | None = None,
    ) -> Dict[str, Any]:
        """Broadcast a message to all agents.

        Args:
            message: The A2A message to broadcast
            capability_filter: Only send to agents with this capability

        Returns:
            Dict mapping agent IDs to responses
        """
        responses = self.a2a.broadcast(message, capability_filter)
        return {
            agent_id: resp.to_dict() if hasattr(resp, "to_dict") else resp
            for agent_id, resp in responses.items()
        }

    def discover_capabilities(self) -> Dict[str, List[str]]:
        """Discover all capabilities across the agent mesh."""
        return self.a2a.discover_capabilities()

    def get_mesh_status(self) -> Dict[str, Any]:
        """Get overall A2A mesh status."""
        mesh = self.a2a.get_mesh_status()
        mesh["mcp_agents"] = {
            aid: agent.to_dict() for aid, agent in self._mcp_agents.items()
        }
        return mesh

    def get_agent_status(self, agent_id: str) -> Dict[str, Any] | None:
        """Get status of a specific agent."""
        status = self.a2a.get_agent_status(agent_id)
        if status is None and agent_id in self._mcp_agents:
            status = self._mcp_agents[agent_id].to_dict()
        return status

    def register_capability(
        self,
        agent_id: str,
        capability_name: str,
        description: str = "",
        parameters: Dict[str, Any] | None = None,
    ) -> None:
        """Add a capability to a registered MCP agent."""
        cap = AgentCapability(
            name=capability_name,
            description=description,
            parameters=parameters or {},
        )
        if agent_id in self._mcp_agents:
            self._mcp_agents[agent_id].capabilities.append(cap)
            # Re-register with updated capabilities
            agent = self._mcp_agents[agent_id]
            self.a2a.unregister_agent(agent_id)
            self.a2a.register_agent(
                agent_id=agent_id,
                name=agent.name,
                capabilities=agent.capabilities,
                metadata=agent.metadata,
            )

    def process_queued_messages(self) -> int:
        """Process any queued messages in the A2A mesh.

        Returns:
            Number of messages processed.
        """
        return self.a2a.process_queued_messages()

    def start(self) -> None:
        """Start the adapter and begin heartbeat monitoring."""
        self._running = True
        self._heartbeat_loop()
        logger.info("A2A-MCP adapter started")

    def stop(self) -> None:
        """Stop the adapter and clean up."""
        self._running = False
        for agent_id in list(self._mcp_agents.keys()):
            self.unregister_mcp_agent(agent_id)
        logger.info("A2A-MCP adapter stopped")

    def _heartbeat_loop(self) -> None:
        """Send heartbeats for all registered MCP agents."""
        import time
        for agent in self._mcp_agents.values():
            agent.heartbeat()
            self.a2a.heartbeat(agent.agent_id)

    def to_dict(self) -> dict:
        """Get adapter status as a dictionary."""
        return {
            "running": self._running,
            "mcp_agent_count": len(self._mcp_agents),
            "mesh_status": self.get_mesh_status(),
        }


def create_a2a_adapter(
    a2a_protocol: A2AProtocol,
    server: Any = None,
) -> MCPA2AAdapter:
    """Convenience function to create an A2A-MCP adapter.

    Args:
        a2a_protocol: An initialized A2AProtocol instance
        server: Optional MCPServer instance

    Returns:
        MCPA2AAdapter ready for use
    """
    adapter = MCPA2AAdapter(a2a_protocol, server)
    adapter.start()
    return adapter