"""
NEUGI v2 Gateway Server
=======================

Central control plane for the NEUGI Swarm v2 multi-agent system.
Provides WebSocket RPC, HTTP REST API, device management, message routing,
heartbeat execution, and cron scheduling.

Usage:
    from neugi_swarm_v2.gateway import (
        Gateway,
        MessageRouter,
        DeviceManager,
        HeartbeatEngine,
        CronScheduler,
    )

    gateway = Gateway(port=8080)
    gateway.start()
"""

from .gateway import (
    Gateway,
    GatewayConfig,
    GatewayState,
    GatewayError,
    ConnectionInfo,
    EventDispatcher,
    RPCMethod,
    RPCRequest,
    RPCResponse,
)
from .router import (
    MessageRouter,
    Route,
    RouteTarget,
    RouteType,
    RoutingResult,
    DeliveryReceipt,
    RouterError,
)
from .device import (
    DeviceManager,
    Device,
    DeviceTrustLevel,
    DeviceState,
    DeviceCapabilities,
    DeviceSession,
    DeviceError,
)
from .heartbeat import (
    HeartbeatEngine,
    HeartbeatTask,
    HeartbeatState,
    HeartbeatResult,
    WakeupQueue,
    HeartbeatError,
)
from .cron import (
    CronScheduler,
    CronJob,
    CronExpression,
    CronSchedule,
    CronJobState,
    CronJobResult,
    CronJobHistory,
    CronError,
)

__all__ = [
    # Gateway
    "Gateway",
    "GatewayConfig",
    "GatewayState",
    "GatewayError",
    "ConnectionInfo",
    "EventDispatcher",
    "RPCMethod",
    "RPCRequest",
    "RPCResponse",
    # Router
    "MessageRouter",
    "Route",
    "RouteTarget",
    "RouteType",
    "RoutingResult",
    "DeliveryReceipt",
    "RouterError",
    # Device
    "DeviceManager",
    "Device",
    "DeviceTrustLevel",
    "DeviceState",
    "DeviceCapabilities",
    "DeviceSession",
    "DeviceError",
    # Heartbeat
    "HeartbeatEngine",
    "HeartbeatTask",
    "HeartbeatState",
    "HeartbeatResult",
    "WakeupQueue",
    "HeartbeatError",
    # Cron
    "CronScheduler",
    "CronJob",
    "CronExpression",
    "CronSchedule",
    "CronJobState",
    "CronJobResult",
    "CronJobHistory",
    "CronError",
]
