"""
NEUGI v2 Session Management system.

Provides session lifecycle management, context compaction,
real-time steering, and transcript handling.
"""

from session.compaction import (
    CompactionConfig,
    CompactionEngine,
    CompactionResult,
    CompactionStrategy,
)
from session.session_manager import (
    Session,
    SessionCheckpoint,
    SessionConfig,
    SessionIsolationMode,
    SessionManager,
    SessionMetadata,
    SessionRegistry,
    SessionState,
)
from session.steering import (
    MessageQueuePolicy,
    SteeringConfig,
    SteeringEngine,
    SteeringHistory,
    SteeringMessage,
    SteeringPriority,
)
from session.transcript import (
    Transcript,
    TranscriptEntry,
    TranscriptFormat,
    TranscriptSearch,
)

__all__ = [
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
    "CompactionResult",
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
]
