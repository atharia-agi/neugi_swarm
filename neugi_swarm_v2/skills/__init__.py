"""NEUGI v2 Skills System - Production-ready skill architecture.

Implements a hierarchical, multi-format compatible skill system with:
- 6-tier loading with precedence
- Name collision resolution
- SKILL.md parsing with YAML frontmatter
- Script/reference/asset support
- Skill gating at load time
- Token impact calculation
- Prompt compaction tiers
- Agent allowlists
- Natural language trigger matching
- Skill workshop (auto-generation)
- Import/export in all formats
"""

from skills.skill_contract import (
    SkillAction,
    SkillContract,
    SkillFrontmatter,
    SkillState,
    SkillTier,
)
from skills.skill_loader import (
    GatingResult,
    SkillLoader,
    SkillParseResult,
)
from skills.skill_manager import SkillManager
from skills.skill_matcher import MatchResult, SkillMatcher
from skills.skill_prompt import (
    CompactionResult,
    PromptAssembler,
    PromptTier,
)

__all__ = [
    "CompactionResult",
    "GatingResult",
    "MatchResult",
    "PromptAssembler",
    "PromptTier",
    "SkillAction",
    "SkillContract",
    "SkillFrontmatter",
    "SkillLoader",
    "SkillManager",
    "SkillMatcher",
    "SkillParseResult",
    "SkillState",
    "SkillTier",
]
