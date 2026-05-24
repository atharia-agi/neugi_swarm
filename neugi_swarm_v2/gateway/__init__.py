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

    gateway = Gateway(port=17901)
    gateway.start()
"""

from gateway.cron import (
    CronError,
    CronExpression,
    CronJob,
    CronJobHistory,
    CronJobResult,
    CronJobState,
    CronSchedule,
    CronScheduler,
)
from gateway.device import (
    Device,
    DeviceCapabilities,
    DeviceError,
    DeviceManager,
    DeviceSession,
    DeviceState,
    DeviceTrustLevel,
)
from gateway.gateway import (
    Connection,
    Event,
    EventType,
    GatewayServer,
    RPCRequest,
    RPCResponse,
)
from gateway.heartbeat import (
    HeartbeatEngine,
    HeartbeatError,
    HeartbeatResult,
    HeartbeatState,
    HeartbeatTask,
    WakeupQueue,
)
from gateway.router import (
    DeliveryReceipt,
    MessageRouter,
    Route,
    RouterError,
    RouteTarget,
    RouteType,
    RoutingResult,
)

__all__ = [
    # Gateway
    "Device",
    "DeviceTrustLevel",
    "Event",
    "EventType",
    "Connection",
    "GatewayServer",
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
