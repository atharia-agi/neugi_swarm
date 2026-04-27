"""
NEUGI v2 Message Router
========================

Routes incoming messages to correct sessions with support for DM routing
(shared vs per-peer vs per-channel-peer), group chat routing (isolated per
group), cron job routing (fresh session per run), webhook routing (isolated
per hook), sub-agent routing (parent-child session key space isolation),
and delivery dispatch (results routed back to original channel).
"""

from __future__ import annotations

import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# -- Enums -------------------------------------------------------------------

class RouteType(str, Enum):
    """Type of message route."""
    DM = "dm"
    GROUP = "group"
    CRON = "cron"
    WEBHOOK = "webhook"
    SUB_AGENT = "sub_agent"
    SYSTEM = "system"


class RouteTarget(str, Enum):
    """Target type for message delivery."""
    SESSION = "session"
    CHANNEL = "channel"
    DEVICE = "device"
    BROADCAST = "broadcast"


# -- Data Classes ------------------------------------------------------------

@dataclass
class Route:
    """A message routing rule.

    Attributes:
        route_id: Unique route identifier.
        route_type: Type of route.
        source: Source identifier (channel, webhook URL, etc.).
        target: Target identifier (session ID, group ID, etc.).
        isolation_mode: Session isolation mode for this route.
        metadata: Arbitrary route metadata.
        created_at: Unix timestamp of creation.
    """
    route_id: str
    route_type: RouteType
    source: str
    target: str
    isolation_mode: str = "shared"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serialize route to a dictionary."""
        return {
            "route_id": self.route_id,
            "route_type": self.route_type.value,
            "source": self.source,
            "target": self.target,
            "isolation_mode": self.isolation_mode,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }


@dataclass
class RoutingResult:
    """Result of routing a message.

    Attributes:
        message_id: The routed message ID.
        session_id: The session the message was routed to.
        route_id: The route that was matched.
        routed_at: Unix timestamp of routing.
        handler: The handler that will process the message.
        metadata: Routing metadata.
    """
    message_id: str
    session_id: str
    route_id: str
    routed_at: float
    handler: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DeliveryReceipt:
    """Receipt for a delivered message result.

    Attributes:
        receipt_id: Unique receipt identifier.
        message_id: Original message ID.
        session_id: Session that processed the message.
        target: Delivery target.
        target_type: Type of delivery target.
        delivered_at: Unix timestamp of delivery.
        success: Whether delivery succeeded.
        error: Error message if delivery failed.
        response: Response data to deliver.
    """
    receipt_id: str
    message_id: str
    session_id: str
    target: str
    target_type: RouteTarget
    delivered_at: float
    success: bool
    error: str | None = None
    response: Any = None


@dataclass
class MessageEnvelope:
    """Wrapped message for routing.

    Attributes:
        message_id: Unique message identifier.
        source: Source identifier.
        content: Message content.
        route_type: Expected route type.
        idempotency_key: Key for deduplication.
        reply_to: Message ID this is replying to.
        channel: Original channel for delivery dispatch.
        device_id: Device that sent the message.
        timestamp: Unix timestamp of creation.
        metadata: Arbitrary message metadata.
    """
    message_id: str
    source: str
    content: Any
    route_type: RouteType = RouteType.DM
    idempotency_key: str = ""
    reply_to: str = ""
    channel: str = ""
    device_id: str = ""
    timestamp: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


# -- Exceptions --------------------------------------------------------------

class RouterError(Exception):
    """Base exception for message router errors."""

    def __init__(self, message: str, route_id: str | None = None) -> None:
        self.route_id = route_id
        super().__init__(message)


class RouteNotFoundError(RouterError):
    """Raised when a route is not found."""
    pass


class RouteAlreadyExistsError(RouterError):
    """Raised when attempting to register a duplicate route."""
    pass


class RoutingFailedError(RouterError):
    """Raised when message routing fails."""
    pass


# -- Message Router ----------------------------------------------------------

class MessageRouter:
    """Routes messages to the correct session with isolation guarantees.

    Supports DM routing (shared vs per-peer vs per-channel-peer), group
    chat routing (isolated per group), cron job routing (fresh session
    per run), webhook routing (isolated per hook), sub-agent routing
    (parent-child session key space isolation), and delivery dispatch
    (results routed back to original channel).

    All operations are thread-safe via a reentrant lock.

    Attributes:
        _lock: Reentrant lock for thread safety.
        _routes: Map of route_id -> Route.
        _source_routes: Map of source -> Route (fast lookup).
        _handlers: Map of route_type -> handler callable.
        _delivery_handlers: Map of target_type -> delivery callable.
        _idempotency_cache: Cache of processed idempotency keys.
        _idempotency_ttl: Seconds to retain idempotency keys.
    """

    def __init__(
        self,
        idempotency_ttl: float = 3600.0,
    ) -> None:
        """Initialize the message router.

        Args:
            idempotency_ttl: Seconds to retain idempotency keys.
        """
        self._lock = threading.RLock()
        self._routes: dict[str, Route] = {}
        self._source_routes: dict[str, str] = {}
        self._handlers: dict[RouteType, Callable[..., Any]] = {}
        self._delivery_handlers: dict[RouteTarget, Callable[..., Any]] = {}
        self._idempotency_cache: dict[str, float] = {}
        self._idempotency_ttl = idempotency_ttl
        logger.info("MessageRouter initialized")

    # -- Route Registration --------------------------------------------------

    def register_route(
        self,
        route_type: RouteType,
        source: str,
        target: str,
        route_id: str | None = None,
        isolation_mode: str = "shared",
        metadata: dict[str, Any] | None = None,
    ) -> Route:
        """Register a new message route.

        Args:
            route_type: Type of route.
            source: Source identifier (channel, webhook, etc.).
            target: Target identifier (session, group, etc.).
            route_id: Unique route ID (auto-generated if None).
            isolation_mode: Session isolation mode.
            metadata: Arbitrary route metadata.

        Returns:
            The registered Route.

        Raises:
            RouteAlreadyExistsError: If source already has a route.
        """
        route_id = route_id or str(uuid.uuid4())
        metadata = metadata or {}
        now = time.time()

        route = Route(
            route_id=route_id,
            route_type=route_type,
            source=source,
            target=target,
            isolation_mode=isolation_mode,
            metadata=metadata,
            created_at=now,
        )

        with self._lock:
            if source in self._source_routes:
                existing = self._source_routes[source]
                raise RouteAlreadyExistsError(
                    f"Route for source '{source}' already exists: {existing}",
                    existing,
                )

            self._routes[route_id] = route
            self._source_routes[source] = route_id

        logger.debug(
            "Route registered: %s -> %s (type=%s)",
            source, target, route_type.value,
        )
        return route

    def register_dm_route(
        self,
        channel: str,
        peer: str,
        session_id: str,
        isolation_mode: str = "shared",
    ) -> Route:
        """Register a DM routing rule.

        The source key is constructed as 'dm:{channel}:{peer}'.

        Args:
            channel: Channel identifier (e.g., 'discord', 'slack').
            peer: Peer identifier (user ID).
            session_id: Session to route messages to.
            isolation_mode: Session isolation mode.

        Returns:
            The registered Route.
        """
        source = f"dm:{channel}:{peer}"
        return self.register_route(
            route_type=RouteType.DM,
            source=source,
            target=session_id,
            isolation_mode=isolation_mode,
            metadata={"channel": channel, "peer": peer},
        )

    def register_group_route(
        self,
        channel: str,
        group_id: str,
        session_id: str,
    ) -> Route:
        """Register a group chat routing rule.

        Group chats are always isolated per group.

        Args:
            channel: Channel identifier.
            group_id: Group/chat room identifier.
            session_id: Session to route messages to.

        Returns:
            The registered Route.
        """
        source = f"group:{channel}:{group_id}"
        return self.register_route(
            route_type=RouteType.GROUP,
            source=source,
            target=session_id,
            isolation_mode="per-group",
            metadata={"channel": channel, "group_id": group_id},
        )

    def register_cron_route(
        self,
        job_id: str,
        session_template: str,
    ) -> Route:
        """Register a cron job routing rule.

        Cron jobs always get a fresh session per run.

        Args:
            job_id: Cron job identifier.
            session_template: Session ID template (uses {run_id} placeholder).

        Returns:
            The registered Route.
        """
        source = f"cron:{job_id}"
        return self.register_route(
            route_type=RouteType.CRON,
            source=source,
            target=session_template,
            isolation_mode="per-run",
            metadata={"job_id": job_id},
        )

    def register_webhook_route(
        self,
        webhook_id: str,
        session_id: str,
    ) -> Route:
        """Register a webhook routing rule.

        Webhooks are isolated per hook.

        Args:
            webhook_id: Webhook identifier.
            session_id: Session to route messages to.

        Returns:
            The registered Route.
        """
        source = f"webhook:{webhook_id}"
        return self.register_route(
            route_type=RouteType.WEBHOOK,
            source=source,
            target=session_id,
            isolation_mode="per-hook",
            metadata={"webhook_id": webhook_id},
        )

    def register_sub_agent_route(
        self,
        parent_session_id: str,
        sub_agent_id: str,
        child_session_id: str,
    ) -> Route:
        """Register a sub-agent routing rule.

        Sub-agents get parent-child session key space isolation.

        Args:
            parent_session_id: Parent session ID.
            sub_agent_id: Sub-agent identifier.
            child_session_id: Child session ID.

        Returns:
            The registered Route.
        """
        source = f"subagent:{parent_session_id}:{sub_agent_id}"
        return self.register_route(
            route_type=RouteType.SUB_AGENT,
            source=source,
            target=child_session_id,
            isolation_mode="parent-child",
            metadata={
                "parent_session_id": parent_session_id,
                "sub_agent_id": sub_agent_id,
            },
        )

    # -- Route Management ----------------------------------------------------

    def get_route(self, route_id: str) -> Route:
        """Get a route by ID.

        Args:
            route_id: The route identifier.

        Returns:
            The Route.

        Raises:
            RouteNotFoundError: If not found.
        """
        with self._lock:
            route = self._routes.get(route_id)
            if route is None:
                raise RouteNotFoundError(
                    f"Route '{route_id}' not found", route_id
                )
            return route

    def get_route_by_source(self, source: str) -> Route | None:
        """Get a route by source identifier.

        Args:
            source: The source identifier.

        Returns:
            The Route or None if not found.
        """
        with self._lock:
            route_id = self._source_routes.get(source)
            if route_id is None:
                return None
            return self._routes.get(route_id)

    def list_routes(
        self,
        route_type: RouteType | None = None,
    ) -> list[Route]:
        """List all routes with optional type filter.

        Args:
            route_type: Filter by route type.

        Returns:
            List of matching Route objects.
        """
        with self._lock:
            routes = list(self._routes.values())
            if route_type:
                routes = [r for r in routes if r.route_type == route_type]
            return routes

    def remove_route(self, route_id: str) -> None:
        """Remove a route.

        Args:
            route_id: The route to remove.

        Raises:
            RouteNotFoundError: If not found.
        """
        with self._lock:
            route = self._routes.get(route_id)
            if route is None:
                raise RouteNotFoundError(
                    f"Route '{route_id}' not found", route_id
                )

            del self._routes[route_id]
            self._source_routes.pop(route.source, None)

        logger.debug("Route removed: %s", route_id[:8])

    def remove_all_routes_for_source(self, source: str) -> int:
        """Remove all routes for a source.

        Args:
            source: The source to remove routes for.

        Returns:
            Number of routes removed.
        """
        with self._lock:
            route_id = self._source_routes.pop(source, None)
            if route_id is None:
                return 0

            del self._routes[route_id]
            return 1

    # -- Handler Registration ------------------------------------------------

    def register_handler(
        self,
        route_type: RouteType,
        handler: Callable[..., Any],
    ) -> None:
        """Register a handler for a route type.

        Args:
            route_type: The route type to handle.
            handler: Callable to process messages of this type.
        """
        with self._lock:
            self._handlers[route_type] = handler

    def register_delivery_handler(
        self,
        target_type: RouteTarget,
        handler: Callable[..., Any],
    ) -> None:
        """Register a delivery handler for a target type.

        Args:
            target_type: The target type to handle delivery for.
            handler: Callable to deliver results.
        """
        with self._lock:
            self._delivery_handlers[target_type] = handler

    # -- Routing -------------------------------------------------------------

    def route_message(
        self,
        envelope: MessageEnvelope,
    ) -> RoutingResult:
        """Route a message envelope to the correct session.

        Checks idempotency, finds the matching route, and dispatches
        to the appropriate handler.

        Args:
            envelope: The message envelope to route.

        Returns:
            RoutingResult with routing details.

        Raises:
            RoutingFailedError: If routing fails.
        """
        if envelope.idempotency_key:
            if self._is_duplicate(envelope.idempotency_key):
                logger.debug(
                    "Duplicate message skipped: %s", envelope.idempotency_key
                )
                raise RoutingFailedError(
                    "Duplicate message (idempotency key already processed)"
                )

        source = envelope.source
        route = self.get_route_by_source(source)

        if route is None:
            route = self._resolve_fallback_route(envelope)

        if route is None:
            raise RoutingFailedError(
                f"No route found for source '{source}'"
            )

        session_id = self._resolve_session_id(route, envelope)

        handler = self._handlers.get(route.route_type)
        handler_name = handler.__name__ if handler else ""

        result = RoutingResult(
            message_id=envelope.message_id,
            session_id=session_id,
            route_id=route.route_id,
            routed_at=time.time(),
            handler=handler_name,
            metadata={
                "route_type": route.route_type.value,
                "isolation_mode": route.isolation_mode,
            },
        )

        if envelope.idempotency_key:
            self._mark_processed(envelope.idempotency_key)

        if handler:
            try:
                handler(envelope, session_id, route)
            except Exception as e:
                logger.error(
                    "Route handler failed for %s: %s",
                    envelope.message_id, e,
                )

        return result

    def _resolve_session_id(
        self,
        route: Route,
        envelope: MessageEnvelope,
    ) -> str:
        """Resolve the target session ID for a routed message.

        For cron routes, generates a fresh session ID per run.
        For other routes, uses the route's target.

        Args:
            route: The matched route.
            envelope: The message envelope.

        Returns:
            The resolved session ID.
        """
        if route.route_type == RouteType.CRON:
            run_id = str(uuid.uuid4())[:8]
            return route.target.replace("{run_id}", run_id)

        if route.route_type == RouteType.SUB_AGENT:
            parent = envelope.metadata.get("parent_session_id", "")
            if parent:
                return f"{parent}:sub:{route.target}"

        return route.target

    def _resolve_fallback_route(
        self,
        envelope: MessageEnvelope,
    ) -> Route | None:
        """Attempt to find a fallback route for an unmatched message.

        Tries pattern matching on the source for common prefixes.

        Args:
            envelope: The unmatched message envelope.

        Returns:
            A matching Route or None.
        """
        source = envelope.source

        with self._lock:
            for route in self._routes.values():
                if source.startswith(route.source):
                    return route

        return None

    # -- Delivery Dispatch ---------------------------------------------------

    def deliver_result(
        self,
        message_id: str,
        session_id: str,
        target: str,
        target_type: RouteTarget,
        response: Any,
        success: bool = True,
        error: str | None = None,
    ) -> DeliveryReceipt:
        """Deliver a message result back to the original channel.

        Args:
            message_id: Original message ID.
            session_id: Session that processed the message.
            target: Delivery target identifier.
            target_type: Type of delivery target.
            response: Response data to deliver.
            success: Whether the processing succeeded.
            error: Error message if processing failed.

        Returns:
            DeliveryReceipt with delivery details.
        """
        receipt_id = str(uuid.uuid4())
        now = time.time()

        receipt = DeliveryReceipt(
            receipt_id=receipt_id,
            message_id=message_id,
            session_id=session_id,
            target=target,
            target_type=target_type,
            delivered_at=now,
            success=success,
            error=error,
            response=response,
        )

        handler = self._delivery_handlers.get(target_type)
        if handler:
            try:
                handler(receipt)
            except Exception as e:
                logger.error(
                    "Delivery handler failed for %s: %s",
                    receipt_id, e,
                )
                receipt.success = False
                receipt.error = str(e)
        else:
            logger.debug(
                "No delivery handler for target type %s", target_type.value
            )

        return receipt

    def deliver_to_session(
        self,
        message_id: str,
        session_id: str,
        response: Any,
        success: bool = True,
        error: str | None = None,
    ) -> DeliveryReceipt:
        """Deliver a result to a session target.

        Args:
            message_id: Original message ID.
            session_id: Target session.
            response: Response data.
            success: Whether processing succeeded.
            error: Error message if failed.

        Returns:
            DeliveryReceipt.
        """
        return self.deliver_result(
            message_id=message_id,
            session_id=session_id,
            target=session_id,
            target_type=RouteTarget.SESSION,
            response=response,
            success=success,
            error=error,
        )

    def deliver_to_channel(
        self,
        message_id: str,
        session_id: str,
        channel: str,
        response: Any,
        success: bool = True,
        error: str | None = None,
    ) -> DeliveryReceipt:
        """Deliver a result to a channel target.

        Args:
            message_id: Original message ID.
            session_id: Session that processed the message.
            channel: Target channel.
            response: Response data.
            success: Whether processing succeeded.
            error: Error message if failed.

        Returns:
            DeliveryReceipt.
        """
        return self.deliver_result(
            message_id=message_id,
            session_id=session_id,
            target=channel,
            target_type=RouteTarget.CHANNEL,
            response=response,
            success=success,
            error=error,
        )

    def broadcast(
        self,
        message_id: str,
        session_id: str,
        response: Any,
        exclude_targets: list[str] | None = None,
    ) -> list[DeliveryReceipt]:
        """Broadcast a result to all connected targets.

        Args:
            message_id: Original message ID.
            session_id: Session that generated the broadcast.
            response: Response data to broadcast.
            exclude_targets: Targets to exclude from broadcast.

        Returns:
            List of DeliveryReceipts for each delivery.
        """
        exclude = set(exclude_targets or [])
        receipts: list[DeliveryReceipt] = []

        handler = self._delivery_handlers.get(RouteTarget.BROADCAST)
        if handler:
            try:
                results = handler(response, exclude)
                for target in results:
                    receipt = DeliveryReceipt(
                        receipt_id=str(uuid.uuid4()),
                        message_id=message_id,
                        session_id=session_id,
                        target=target,
                        target_type=RouteTarget.BROADCAST,
                        delivered_at=time.time(),
                        success=True,
                        response=response,
                    )
                    receipts.append(receipt)
            except Exception as e:
                logger.error("Broadcast failed: %s", e)

        return receipts

    # -- Idempotency ---------------------------------------------------------

    def _is_duplicate(self, idempotency_key: str) -> bool:
        """Check if an idempotency key has already been processed.

        Args:
            idempotency_key: The key to check.

        Returns:
            True if the key was already processed.
        """
        self._cleanup_idempotency_cache()
        return idempotency_key in self._idempotency_cache

    def _mark_processed(self, idempotency_key: str) -> None:
        """Mark an idempotency key as processed.

        Args:
            idempotency_key: The key to mark.
        """
        self._idempotency_cache[idempotency_key] = time.time()

    def _cleanup_idempotency_cache(self) -> None:
        """Remove expired idempotency keys."""
        now = time.time()
        expired = [
            k for k, v in self._idempotency_cache.items()
            if now - v > self._idempotency_ttl
        ]
        for k in expired:
            del self._idempotency_cache[k]

    # -- Utility -------------------------------------------------------------

    def get_route_count(self) -> int:
        """Get the total number of registered routes.

        Returns:
            Number of routes.
        """
        return len(self._routes)

    def get_stats(self) -> dict[str, Any]:
        """Get router statistics.

        Returns:
            Dictionary with route counts by type and other metrics.
        """
        with self._lock:
            by_type: dict[str, int] = {}
            for route in self._routes.values():
                type_key = route.route_type.value
                by_type[type_key] = by_type.get(type_key, 0) + 1

            return {
                "total_routes": len(self._routes),
                "by_type": by_type,
                "handlers_registered": list(self._handlers.keys()),
                "delivery_handlers": list(self._delivery_handlers.keys()),
                "idempotency_cache_size": len(self._idempotency_cache),
            }

    def close(self) -> None:
        """Shut down the message router."""
        with self._lock:
            self._routes.clear()
            self._source_routes.clear()
            self._handlers.clear()
            self._delivery_handlers.clear()
            self._idempotency_cache.clear()

        logger.info("MessageRouter shut down")
