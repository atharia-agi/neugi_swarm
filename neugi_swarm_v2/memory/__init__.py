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

from memory.dreaming import DreamConfig, DreamingEngine, DreamPhase, DreamResult
from memory.memory_core import MemoryEntry, MemoryError, MemorySystem, MemoryTier
from memory.scopes import MemoryScope, MemorySlice, ScopeError, ScopePath
from memory.scoring import ScoreComponents, ScoreConfig, ScoringEngine

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
