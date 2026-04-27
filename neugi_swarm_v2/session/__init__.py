"""
NEUGI v2 Session Management system.

Provides session lifecycle management, context compaction,
real-time steering, and transcript handling.
"""

from .session_manager import (
    Session,
    SessionManager,
    SessionState,
    SessionIsolationMode,
    SessionConfig,
    SessionMetadata,
    SessionCheckpoint,
    SessionRegistry,
)
from .compaction import (
    CompactionEngine,
    CompactionConfig,
    CompactionResult,
    CompactionStrategy,
)
from .steering import (
    SteeringEngine,
    SteeringConfig,
    SteeringMessage,
    SteeringPriority,
    MessageQueuePolicy,
    SteeringHistory,
)
from .transcript import (
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
