"""
NEUGI v2 Memory System
======================

Production-ready hierarchical memory combining:
- Karpathy-style dreaming consolidation (3-tier, markdown files, cron-based)
- CrewAI unified memory (hierarchical scopes, composite scoring, LLM analysis)
- LangGraph checkpointing (durable execution, state persistence)

Usage:
    from memory import MemorySystem, DreamingEngine, ScopePath, ScoringEngine
"""

from memory.scopes import ScopePath, MemoryScope, MemorySlice, ScopeError
from memory.scoring import ScoringEngine, ScoreComponents, ScoreConfig
from memory.memory_core import MemorySystem, MemoryEntry, MemoryTier, MemoryError
from memory.dreaming import DreamingEngine, DreamPhase, DreamConfig, DreamResult

__all__ = [
    "MemorySystem",
    "MemoryEntry",
    "MemoryTier",
    "MemoryError",
    "DreamingEngine",
    "DreamPhase",
    "DreamConfig",
    "DreamResult",
    "ScopePath",
    "MemoryScope",
    "MemorySlice",
    "ScopeError",
    "ScoringEngine",
    "ScoreComponents",
    "ScoreConfig",
]
