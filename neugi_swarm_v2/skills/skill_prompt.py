"""Skill-to-prompt injection - dynamic assembly, token budgeting, and compaction."""

from __future__ import annotations

import hashlib
import textwrap
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Set

from .skill_contract import SkillContract, SkillState


class PromptTier(Enum):
    """Prompt compaction levels."""

    FULL = "full"
    COMPACT = "compact"
    TRUNCATED = "truncated"


@dataclass
class CompactionResult:
    """Result of prompt compaction.

    Attributes:
        content: The assembled prompt content.
        token_count: Estimated token count.
        tier: Compaction tier used.
        skills_included: Number of skills included.
        skills_omitted: Number of skills omitted due to budget.
        fingerprint: Cache-friendly hash of the prompt content.
    """

    content: str
    token_count: int
    tier: PromptTier
    skills_included: int
    skills_omitted: int
    fingerprint: str


class PromptAssembler:
    """Assembles skill content into system prompt sections.

    Handles token budget management, compaction strategies, and
    cache-friendly fingerprinting for KV cache reuse.

    Usage:
        assembler = PromptAssembler(token_budget=8000)
        result = assembler.assemble(skills, tier=PromptTier.FULL)
    """

    def __init__(
        self,
        token_budget: int = 8000,
        max_skills_in_prompt: int = 20,
        delimiter: str = "skill",
    ) -> None:
        """Initialize prompt assembler.

        Args:
            token_budget: Maximum tokens for skill section of prompt.
            max_skills_in_prompt: Hard limit on number of skills included.
            delimiter: XML tag name for skill wrapping (e.g., 'skill' -> <skill>).
        """
        self.token_budget = token_budget
        self.max_skills_in_prompt = max_skills_in_prompt
        self.delimiter = delimiter

    def assemble(
        self,
        skills: List[SkillContract],
        tier: PromptTier = PromptTier.FULL,
        agent_name: Optional[str] = None,
        extra_context: str = "",
    ) -> CompactionResult:
        """Assemble skills into prompt content.

        Args:
            skills: List of enabled skill contracts to include.
            tier: Compaction level.
            agent_name: Filter skills by agent allowlist. If None, include all.
            extra_context: Additional context to prepend.

        Returns:
            CompactionResult with assembled content and metadata.
        """
        filtered = self._filter_by_agent(skills, agent_name)
        enabled = [s for s in filtered if s.state == SkillState.ENABLED]

        if tier == PromptTier.FULL:
            return self._assemble_full(enabled, extra_context)
        elif tier == PromptTier.COMPACT:
            return self._assemble_compact(enabled, extra_context)
        else:
            return self._assemble_truncated(enabled, extra_context)

    def compute_fingerprint(self, skills: List[SkillContract]) -> str:
        """Compute cache-friendly fingerprint for a set of skills.

        Normalizes skill order and content to maximize KV cache reuse
        across sessions with the same skill set.

        Args:
            skills: List of skill contracts.

        Returns:
            SHA-256 hex digest of normalized skill content.
        """
        normalized = []
        for s in sorted(skills, key=lambda x: x.name):
            parts = [
                s.name,
                s.frontmatter.version,
                s.frontmatter.description,
                str(sorted(s.frontmatter.tags)),
            ]
            normalized.append("|".join(parts))
        blob = "\n".join(normalized).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()[:16]

    def estimate_total_tokens(self, skills: List[SkillContract]) -> int:
        """Estimate total token cost for a list of skills."""
        return sum(s.compute_token_cost() for s in skills)

    def _filter_by_agent(
        self, skills: List[SkillContract], agent_name: Optional[str]
    ) -> List[SkillContract]:
        """Filter skills by agent allowlist."""
        if agent_name is None:
            return skills
        return [
            s
            for s in skills
            if not s.frontmatter.agents or agent_name in s.frontmatter.agents
        ]

    def _assemble_full(
        self, skills: List[SkillContract], extra_context: str
    ) -> CompactionResult:
        """Full compaction: include all skill details."""
        sections: List[str] = []
        if extra_context:
            sections.append(extra_context)

        included = 0
        omitted = 0
        total_tokens = 0

        for skill in skills:
            if included >= self.max_skills_in_prompt:
                omitted += len(skills) - included
                break
            skill_cost = skill.compute_token_cost()
            if total_tokens + skill_cost > self.token_budget:
                omitted += 1
                continue
            section = self._format_skill_full(skill)
            sections.append(section)
            total_tokens += skill_cost
            included += 1

        content = "\n\n".join(sections)
        fingerprint = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

        return CompactionResult(
            content=content,
            token_count=total_tokens,
            tier=PromptTier.FULL,
            skills_included=included,
            skills_omitted=omitted,
            fingerprint=fingerprint,
        )

    def _assemble_compact(
        self, skills: List[SkillContract], extra_context: str
    ) -> CompactionResult:
        """Compact compaction: name, description, tags only."""
        sections: List[str] = []
        if extra_context:
            sections.append(extra_context)

        included = 0
        omitted = 0
        total_tokens = 0

        for skill in skills:
            if included >= self.max_skills_in_prompt:
                omitted += len(skills) - included
                break
            section = self._format_skill_compact(skill)
            cost = len(section) // 4
            if total_tokens + cost > self.token_budget:
                omitted += 1
                continue
            sections.append(section)
            total_tokens += cost
            included += 1

        content = "\n\n".join(sections)
        fingerprint = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

        return CompactionResult(
            content=content,
            token_count=total_tokens,
            tier=PromptTier.COMPACT,
            skills_included=included,
            skills_omitted=omitted,
            fingerprint=fingerprint,
        )

    def _assemble_truncated(
        self, skills: List[SkillContract], extra_context: str
    ) -> CompactionResult:
        """Truncated compaction: name and one-line description only."""
        sections: List[str] = []
        if extra_context:
            sections.append(extra_context)

        included = 0
        omitted = 0
        total_tokens = 0

        for skill in skills:
            if included >= self.max_skills_in_prompt:
                omitted += len(skills) - included
                break
            section = self._format_skill_truncated(skill)
            cost = len(section) // 4
            if total_tokens + cost > self.token_budget:
                omitted += 1
                continue
            sections.append(section)
            total_tokens += cost
            included += 1

        content = "\n\n".join(sections)
        fingerprint = hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]

        return CompactionResult(
            content=content,
            token_count=total_tokens,
            tier=PromptTier.TRUNCATED,
            skills_included=included,
            skills_omitted=omitted,
            fingerprint=fingerprint,
        )

    def _format_skill_full(self, skill: SkillContract) -> str:
        """Format skill with full details in XML-style compact format."""
        lines = [
            f"<{self.delimiter} name=\"{skill.name}\" version=\"{skill.frontmatter.version}\">",
            f"  <description>{_escape_xml(skill.frontmatter.description)}</description>",
        ]
        if skill.frontmatter.tags:
            tags = ", ".join(skill.frontmatter.tags)
            lines.append(f"  <tags>{_escape_xml(tags)}</tags>")
        if skill.frontmatter.allowed_tools:
            tools = ", ".join(skill.frontmatter.allowed_tools)
            lines.append(f"  <tools>{_escape_xml(tools)}</tools>")
        if skill.frontmatter.requires:
            requires = ", ".join(skill.frontmatter.requires)
            lines.append(f"  <requires>{_escape_xml(requires)}</requires>")
        if skill.frontmatter.triggers:
            triggers = ", ".join(skill.frontmatter.triggers)
            lines.append(f"  <triggers>{_escape_xml(triggers)}</triggers>")
        if skill.frontmatter.category:
            lines.append(
                f"  <category>{_escape_xml(skill.frontmatter.category)}</category>"
            )
        if skill.actions:
            for action in skill.actions:
                lines.append(
                    f"  <action name=\"{action.name}\">{_escape_xml(action.description)}</action>"
                )
        if skill.body:
            body = textwrap.indent(skill.body, "  ")
            lines.append(f"  <instructions>")
            lines.append(body)
            lines.append(f"  </instructions>")
        lines.append(f"</{self.delimiter}>")
        return "\n".join(lines)

    def _format_skill_compact(self, skill: SkillContract) -> str:
        """Format skill with compact details (no body instructions)."""
        lines = [
            f"<{self.delimiter} name=\"{skill.name}\" version=\"{skill.frontmatter.version}\">",
            f"  <description>{_escape_xml(skill.frontmatter.description)}</description>",
        ]
        if skill.frontmatter.tags:
            tags = ", ".join(skill.frontmatter.tags)
            lines.append(f"  <tags>{_escape_xml(tags)}</tags>")
        if skill.frontmatter.triggers:
            triggers = ", ".join(skill.frontmatter.triggers)
            lines.append(f"  <triggers>{_escape_xml(triggers)}</triggers>")
        if skill.actions:
            for action in skill.actions:
                lines.append(
                    f"  <action name=\"{action.name}\">{_escape_xml(action.description)}</action>"
                )
        lines.append(f"</{self.delimiter}>")
        return "\n".join(lines)

    def _format_skill_truncated(self, skill: SkillContract) -> str:
        """Format skill with minimal details (name + description only)."""
        return (
            f"<{self.delimiter} name=\"{skill.name}\">"
            f" {skill.frontmatter.description}"
            f"</{self.delimiter}>"
        )


def _escape_xml(text: str) -> str:
    """Escape special XML characters in text."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&apos;")
    )
