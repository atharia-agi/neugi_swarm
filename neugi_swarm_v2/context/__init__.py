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

from context.prompt_assembler import (
    PromptAssembler,
    PromptMode,
    PromptSection,
    SectionConfig,
    BootstrapFile,
    PromptAssemblyError,
    PromptResult,
)
from context.token_budget import (
    TokenBudget,
    BudgetAllocation,
    BudgetReport,
    ModelPreset,
    BudgetError,
    SectionBudget,
)
from context.cache_stability import (
    CacheStability,
    PromptFingerprint,
    CacheStats,
    PromptDiff,
    CacheError,
)
from context.context_injector import (
    ContextInjector,
    ContextItem,
    InjectionResult,
    InjectionError,
    ContextScope,
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
]
