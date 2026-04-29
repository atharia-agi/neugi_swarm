"""
NEUGI v2 Context Window Optimization System
============================================

Production-ready context management combining:
- OpenClaw-style dynamic prompt assembly with modular sections
- Claude API-style token budget allocation and overflow handling
- KV cache stability optimization with fingerprinting and diffing
- Relevance-based context injection with freshness tracking

Usage:
    from context import PromptAssembler, TokenBudget, CacheStability, ContextInjector
"""

from context.cache_stability import (
    CacheError,
    CacheStability,
    CacheStats,
    PromptDiff,
    PromptFingerprint,
)
from context.context_injector import (
    ContextInjector,
    ContextItem,
    ContextScope,
    InjectionError,
    InjectionResult,
)
from context.prompt_assembler import (
    BootstrapFile,
    PromptAssembler,
    PromptAssemblyError,
    PromptMode,
    PromptResult,
    PromptSection,
    SectionConfig,
)
from context.soul_engine import SoulEngine, SoulFile
from context.token_budget import (
    BudgetAllocation,
    BudgetError,
    BudgetReport,
    ModelPreset,
    SectionBudget,
    TokenBudget,
)

__all__ = [
    # Prompt assembler
    "PromptAssembler",
    "PromptMode",
    "PromptSection",
    "SectionConfig",
    "BootstrapFile",
    "PromptAssemblyError",
    "PromptResult",
    # Token budget
    "TokenBudget",
    "BudgetAllocation",
    "BudgetReport",
    "ModelPreset",
    "BudgetError",
    "SectionBudget",
    # Cache stability
    "CacheStability",
    "PromptFingerprint",
    "CacheStats",
    "PromptDiff",
    "CacheError",
    # Context injector
    "ContextInjector",
    "ContextItem",
    "InjectionResult",
    "InjectionError",
    "ContextScope",
    "SoulEngine",
    "SoulFile",
]
