"""
A2A Protocol (Agent-to-Agent) for NEUGI v2
============================================
Standardized agent communication inspired by Pydantic AI's A2A pattern.

Features:
    - Structured message passing between agents
    - Capability advertisement and discovery
    - Task delegation with callbacks
    - Async agent mesh networking
    - Message routing and load balancing
    - Dead letter handling

Usage:
    from a2a import A2AProtocol, AgentCapability, A2AMessage
    
    protocol = A2AProtocol()
    
    # Register agent with capabilities
    protocol.register_agent("cipher", capabilities=[
        AgentCapability(name="code", description="Write and review code")
    ])
    
    # Send message to another agent
    protocol.send("cipher", A2AMessage(
        task="review this Python function",
        payload={"code": "def hello(): pass"}
    ))
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class A2AMessageType(str, Enum):
    """Types of A2A messages."""
    TASK = "task"
    RESPONSE = "response"
    HEARTBEAT = "heartbeat"
    CAPABILITY_ADVERT = "capability_advert"
    DELEGATION = "delegation"
    ERROR = "error"
    STREAM = "stream"


class A2APriority(int, Enum):
    """Message priority levels."""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class AgentCapability:
    """A capability that an agent can advertise."""
    name: str
    description: str = ""
    parameters: Dict[str, Any] = field(default_factory=dict)
    examples: List[str] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
            "examples": self.examples,
        }


@dataclass
class A2AMessage:
    """A message exchanged between agents."""
    msg_type: A2AMessageType
    sender: str = ""
    recipient: str = ""
    task: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    message_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    correlation_id: str = ""  # Links responses to original task
    priority: A2APriority = A2APriority.NORMAL
    timestamp: float = field(default_factory=time.time)
    ttl_seconds: int = 300  # Time-to-live
    
    def is_expired(self) -> bool:
        return time.time() - self.timestamp > self.ttl_seconds
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "msg_type": self.msg_type.value,
            "sender": self.sender,
            "recipient": self.recipient,
            "task": self.task,
            "payload": self.payload,
            "message_id": self.message_id,
            "correlation_id": self.correlation_id,
            "priority": self.priority.value,
            "timestamp": self.timestamp,
            "ttl_seconds": self.ttl_seconds,
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "A2AMessage":
        return cls(
            msg_type=A2AMessageType(data.get("msg_type", "task")),
            sender=data.get("sender", ""),
            recipient=data.get("recipient", ""),
            task=data.get("task", ""),
            payload=data.get("payload", {}),
            message_id=data.get("message_id", ""),
            correlation_id=data.get("correlation_id", ""),
            priority=A2APriority(data.get("priority", 2)),
            timestamp=data.get("timestamp", time.time()),
            ttl_seconds=data.get("ttl_seconds", 300),
        )


@dataclass
class AgentRegistration:
    """Registration info for an agent in the mesh."""
    agent_id: str
    name: str
    capabilities: List[AgentCapability] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    last_heartbeat: float = field(default_factory=time.time)
    status: str = "active"  # active, busy, offline, error
    task_count: int = 0
    success_rate: float = 1.0
    
    def is_alive(self, timeout_seconds: int = 60) -> bool:
        return time.time() - self.last_heartbeat < timeout_seconds
    
    def has_capability(self, name: str) -> bool:
        return any(c.name == name for c in self.capabilities)


class A2AError(Exception):
    """Base exception for A2A errors."""
    pass


class AgentNotFoundError(A2AError):
    """Agent not found in registry."""
    pass


class MessageExpiredError(A2AError):
    """Message has expired."""
    pass


class A2AProtocol:
    """
    Agent-to-Agent communication protocol.
    
    Implements:
    - Agent registry with capability discovery
    - Message routing and delivery
    - Task delegation with callbacks
    - Heartbeat monitoring
    - Load balancing for multi-agent tasks
    """
    
    def __init__(self):
        self._agents: Dict[str, AgentRegistration] = {}
        self._message_handlers: Dict[str, Callable[[A2AMessage], Optional[A2AMessage]]] = {}
        self._message_queue: List[A2AMessage] = []
        self._callbacks: Dict[str, Callable[[A2AMessage], None]] = {}
        self._delegation_history: List[Dict[str, Any]] = []
        self._dead_letters: List[A2AMessage] = []
    
    def register_agent(
        self,
        agent_id: str,
        name: str = "",
        capabilities: Optional[List[AgentCapability]] = None,
        handler: Optional[Callable[[A2AMessage], Optional[A2AMessage]]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> AgentRegistration:
        """
        Register an agent with the protocol.
        
        Args:
            agent_id: Unique agent identifier
            name: Human-readable name
            capabilities: List of capabilities this agent provides
            handler: Callback for incoming messages
            metadata: Additional agent metadata
            
        Returns:
            AgentRegistration object
        """
        registration = AgentRegistration(
            agent_id=agent_id,
            name=name or agent_id,
            capabilities=capabilities or [],
            metadata=metadata or {},
        )
        
        self._agents[agent_id] = registration
        
        if handler:
            self._message_handlers[agent_id] = handler
        
        logger.info(f"Agent registered: {agent_id} ({registration.name})")
        return registration
    
    def unregister_agent(self, agent_id: str) -> None:
        """Remove an agent from the registry."""
        if agent_id in self._agents:
            del self._agents[agent_id]
        if agent_id in self._message_handlers:
            del self._message_handlers[agent_id]
        logger.info(f"Agent unregistered: {agent_id}")
    
    def send(
        self,
        recipient_id: str,
        message: A2AMessage,
        callback: Optional[Callable[[A2AMessage], None]] = None,
    ) -> Optional[A2AMessage]:
        """
        Send a message to an agent.
        
        Args:
            recipient_id: Target agent ID
            message: Message to send
            callback: Optional callback for response
            
        Returns:
            Response message if synchronous, None if async
        """
        message.recipient = recipient_id
        
        # Validate recipient
        if recipient_id not in self._agents:
            error_msg = A2AMessage(
                msg_type=A2AMessageType.ERROR,
                sender="system",
                recipient=message.sender,
                task=f"Agent '{recipient_id}' not found",
                correlation_id=message.message_id,
            )
            return error_msg
        
        # Check if message expired
        if message.is_expired():
            raise MessageExpiredError(f"Message {message.message_id} has expired")
        
        # Store callback if provided
        if callback:
            self._callbacks[message.message_id] = callback
        
        # Route to handler
        handler = self._message_handlers.get(recipient_id)
        if handler:
            try:
                response = handler(message)
                
                # Track delegation
                self._delegation_history.append({
                    "timestamp": time.time(),
                    "sender": message.sender,
                    "recipient": recipient_id,
                    "task": message.task,
                    "message_id": message.message_id,
                    "status": "delivered" if response else "no_response",
                })
                
                return response
                
            except Exception as e:
                logger.error(f"Handler error for {recipient_id}: {e}")
                error_msg = A2AMessage(
                    msg_type=A2AMessageType.ERROR,
                    sender=recipient_id,
                    recipient=message.sender,
                    task=f"Handler error: {e}",
                    correlation_id=message.message_id,
                )
                return error_msg
        else:
            # Queue for later processing
            self._message_queue.append(message)
            logger.debug(f"Message queued for {recipient_id}")
            return None
    
    def broadcast(
        self,
        message: A2AMessage,
        capability_filter: Optional[str] = None,
    ) -> Dict[str, Optional[A2AMessage]]:
        """
        Broadcast message to all agents (or those with specific capability).
        
        Args:
            message: Message to broadcast
            capability_filter: Only send to agents with this capability
            
        Returns:
            Dict mapping agent_id to response
        """
        responses = {}
        
        for agent_id, registration in self._agents.items():
            if capability_filter and not registration.has_capability(capability_filter):
                continue
            
            msg_copy = A2AMessage.from_dict(message.to_dict())
            responses[agent_id] = self.send(agent_id, msg_copy)
        
        return responses
    
    def delegate(
        self,
        task: str,
        payload: Dict[str, Any],
        required_capability: str,
        sender: str = "orchestrator",
    ) -> Optional[A2AMessage]:
        """
        Delegate a task to the best agent with a capability.
        
        Args:
            task: Task description
            payload: Task payload
            required_capability: Required agent capability
            sender: Delegating agent ID
            
        Returns:
            Response from chosen agent
        """
        candidates = self.find_agents_by_capability(required_capability)
        
        if not candidates:
            logger.warning(f"No agents found with capability: {required_capability}")
            return None
        
        # Select best agent (load balancing: choose least busy)
        best_agent = min(candidates, key=lambda a: a.task_count)
        
        message = A2AMessage(
            msg_type=A2AMessageType.DELEGATION,
            sender=sender,
            recipient=best_agent.agent_id,
            task=task,
            payload=payload,
            priority=A2APriority.HIGH,
        )
        
        best_agent.task_count += 1
        
        return self.send(best_agent.agent_id, message)
    
    def find_agents_by_capability(self, name: str) -> List[AgentRegistration]:
        """Find all agents with a specific capability."""
        return [
            agent for agent in self._agents.values()
            if agent.has_capability(name) and agent.status == "active"
        ]
    
    def discover_capabilities(self) -> Dict[str, List[str]]:
        """Discover all capabilities across the agent mesh."""
        capabilities: Dict[str, List[str]] = {}
        
        for agent in self._agents.values():
            for cap in agent.capabilities:
                if cap.name not in capabilities:
                    capabilities[cap.name] = []
                capabilities[cap.name].append(agent.agent_id)
        
        return capabilities
    
    def heartbeat(self, agent_id: str) -> None:
        """Update agent heartbeat."""
        if agent_id in self._agents:
            self._agents[agent_id].last_heartbeat = time.time()
    
    def get_agent_status(self, agent_id: str) -> Optional[Dict[str, Any]]:
        """Get agent status info."""
        if agent_id not in self._agents:
            return None
        
        agent = self._agents[agent_id]
        return {
            "agent_id": agent.agent_id,
            "name": agent.name,
            "status": agent.status,
            "is_alive": agent.is_alive(),
            "capabilities": [c.name for c in agent.capabilities],
            "task_count": agent.task_count,
            "success_rate": agent.success_rate,
            "last_heartbeat": agent.last_heartbeat,
        }
    
    def get_mesh_status(self) -> Dict[str, Any]:
        """Get overall mesh status."""
        return {
            "total_agents": len(self._agents),
            "active_agents": sum(1 for a in self._agents.values() if a.is_alive()),
            "queued_messages": len(self._message_queue),
            "dead_letters": len(self._dead_letters),
            "total_delegations": len(self._delegation_history),
            "capabilities": self.discover_capabilities(),
        }
    
    def process_queued_messages(self) -> int:
        """Process queued messages for agents that now have handlers."""
        processed = 0
        remaining = []
        
        for msg in self._message_queue:
            if msg.recipient in self._message_handlers and not msg.is_expired():
                try:
                    self._message_handlers[msg.recipient](msg)
                    processed += 1
                except Exception as e:
                    logger.error(f"Queued message processing failed: {e}")
                    self._dead_letters.append(msg)
            elif msg.is_expired():
                self._dead_letters.append(msg)
            else:
                remaining.append(msg)
        
        self._message_queue = remaining
        return processed
    
    def get_dead_letters(self) -> List[A2AMessage]:
        """Get dead letter messages for inspection."""
        return self._dead_letters.copy()
    
    def clear_dead_letters(self) -> None:
        """Clear dead letter queue."""
        self._dead_letters.clear()


class A2AChannel:
    """
    Persistent channel for agent communication.
    """
    
    def __init__(self, protocol: A2AProtocol, agent_id: str):
        self.protocol = protocol
        self.agent_id = agent_id
        self._inbox: List[A2AMessage] = []
        self._subscribers: List[Callable[[A2AMessage], None]] = []
    
    def send(self, recipient: str, task: str, payload: Dict[str, Any] = None) -> Optional[A2AMessage]:
        """Send message through channel."""
        message = A2AMessage(
            msg_type=A2AMessageType.TASK,
            sender=self.agent_id,
            recipient=recipient,
            task=task,
            payload=payload or {},
        )
        return self.protocol.send(recipient, message)
    
    def subscribe(self, callback: Callable[[A2AMessage], None]) -> None:
        """Subscribe to incoming messages."""
        self._subscribers.append(callback)
    
    def receive(self, message: A2AMessage) -> None:
        """Receive message (called by protocol)."""
        self._inbox.append(message)
        for subscriber in self._subscribers:
            try:
                subscriber(message)
            except Exception as e:
                logger.error(f"Subscriber error: {e}")
    
    def get_inbox(self) -> List[A2AMessage]:
        """Get all messages in inbox."""
        return self._inbox.copy()
    
    def clear_inbox(self) -> None:
        """Clear inbox."""
        self._inbox.clear()


__all__ = [
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
]
