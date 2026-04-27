"""Main SkillManager class - orchestrates loading, matching, prompting, and workshop."""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

try:
    import yaml
except ImportError:
    yaml = None  # type: ignore

from .skill_contract import (
    SkillAction,
    SkillContract,
    SkillFrontmatter,
    SkillState,
    SkillTier,
)
from .skill_loader import GatingResult, SkillLoader, SkillParseResult
from .skill_matcher import MatchResult, SkillMatcher
from .skill_prompt import CompactionResult, PromptAssembler, PromptTier


@dataclass
class WorkshopObservation:
    """An observed procedure that may become a skill.

    Attributes:
        name: Proposed skill name.
        procedure: Step-by-step description of what was observed.
        context: When/why this procedure was invoked.
        frequency: How many times this was observed.
        tools_used: Tools that were invoked during the procedure.
    """

    name: str
    procedure: str
    context: str
    frequency: int = 1
    tools_used: List[str] = field(default_factory=list)

    def to_skill_scaffold(self) -> SkillFrontmatter:
        """Generate a skill frontmatter scaffold from this observation."""
        return SkillFrontmatter(
            name=self.name,
            description=f"Auto-generated from observed procedure: {self.context}",
            tags=list(set(t for t in self.tools_used if t)),
            triggers=[self.context],
        )


@dataclass
class SkillManagerStats:
    """Runtime statistics for the skill manager.

    Attributes:
        total_loaded: Total skills loaded across all tiers.
        enabled: Number of enabled skills.
        disabled: Number of disabled (gated) skills.
        errored: Number of skills with load errors.
        total_token_cost: Sum of token costs for all enabled skills.
        tier_counts: Count per tier.
    """

    total_loaded: int = 0
    enabled: int = 0
    disabled: int = 0
    errored: int = 0
    total_token_cost: int = 0
    tier_counts: Dict[str, int] = field(default_factory=dict)


class SkillManager:
    """Central orchestrator for the NEUGI v2 Skills System.

    Manages the full skill lifecycle:
    - Discovery and loading from 6-tier directory hierarchy
    - Name collision resolution (highest tier wins)
    - Gating evaluation at load time
    - Natural language query matching
    - Dynamic prompt assembly with token budgeting
    - Agent allowlist filtering
    - Skill workshop (auto-generation from observations)
    - Import/export in all supported formats

    Usage:
        manager = SkillManager()
        manager.register_tier_path(SkillTier.PROJECT, "/project/skills")
        manager.register_tier_path(SkillTier.BUNDLED, "/bundled/skills")
        manager.load()
        results = manager.match("how do I deploy")
        prompt = manager.assemble_prompt(results, tier=PromptTier.FULL)
    """

    def __init__(
        self,
        token_budget: int = 8000,
        max_skills_in_prompt: int = 20,
        default_agent: Optional[str] = None,
    ) -> None:
        """Initialize skill manager.

        Args:
            token_budget: Maximum tokens for skill section in prompts.
            max_skills_in_prompt: Hard limit on skills per prompt.
            default_agent: Default agent name for allowlist filtering.
        """
        self._loader = SkillLoader()
        self._matcher = SkillMatcher()
        self._assembler = PromptAssembler(
            token_budget=token_budget,
            max_skills_in_prompt=max_skills_in_prompt,
        )
        self._default_agent = default_agent
        self._skills: Dict[str, SkillContract] = {}
        self._tier_paths: Dict[SkillTier, List[str]] = {
            tier: [] for tier in SkillTier
        }
        self._workshop: List[WorkshopObservation] = []
        self._on_skill_loaded: Optional[Callable[[SkillContract], None]] = None

    def register_tier_path(self, tier: SkillTier, path: str) -> None:
        """Register a search path for a specific tier.

        Args:
            tier: Skill tier this path belongs to.
            path: Directory path to scan.
        """
        self._tier_paths[tier].append(path)
        self._loader.add_search_path(path, tier)

    def register_default_paths(self) -> None:
        """Register conventional default paths for all tiers.

        Uses environment variables if set, otherwise uses relative paths:
        - NEUGI_WORKSPACE_SKILLS or ./workspace/skills
        - NEUGI_PROJECT_SKILLS or ./project/skills
        - NEUGI_PERSONAL_SKILLS or ~/.neugi/skills
        - NEUGI_MANAGED_SKILLS or ./managed/skills
        - NEUGI_BUNDLED_SKILLS or ./bundled/skills
        - NEUGI_EXTRA_SKILLS or ./extra/skills
        """
        defaults = [
            (SkillTier.WORKSPACE, "NEUGI_WORKSPACE_SKILLS", "workspace/skills"),
            (SkillTier.PROJECT, "NEUGI_PROJECT_SKILLS", "project/skills"),
            (SkillTier.PERSONAL, "NEUGI_PERSONAL_SKILLS", None),
            (SkillTier.MANAGED, "NEUGI_MANAGED_SKILLS", "managed/skills"),
            (SkillTier.BUNDLED, "NEUGI_BUNDLED_SKILLS", "bundled/skills"),
            (SkillTier.EXTRA, "NEUGI_EXTRA_SKILLS", "extra/skills"),
        ]
        for tier, env_var, rel_path in defaults:
            path = os.environ.get(env_var)
            if path:
                self.register_tier_path(tier, path)
            elif rel_path:
                self.register_tier_path(tier, rel_path)
            elif tier == SkillTier.PERSONAL:
                home = Path.home()
                personal = home / ".neugi" / "skills"
                if personal.is_dir():
                    self.register_tier_path(tier, str(personal))

    def set_reload_callback(self, callback: Callable[[], None]) -> None:
        """Set callback for hot reload events."""
        self._loader.set_reload_callback(callback)

    def start_hot_reload(self, interval: float = 5.0) -> None:
        """Start background file watcher for hot reload."""
        self._loader.start_watching(interval)

    def stop_hot_reload(self) -> None:
        """Stop background file watcher."""
        self._loader.stop_watching()

    def load(self) -> Dict[str, SkillContract]:
        """Load all skills from registered paths.

        Loads in tier precedence order. Name collisions resolved by
        keeping the highest-tier skill.

        Returns:
            Dict mapping skill name to SkillContract.
        """
        self._skills = self._loader.load_all()
        self._matcher.build_index(list(self._skills.values()))

        if self._on_skill_loaded:
            for skill in self._skills.values():
                self._on_skill_loaded(skill)

        return self._skills

    def reload(self) -> Dict[str, SkillContract]:
        """Reload all skills (full re-scan)."""
        return self.load()

    def get(self, name: str) -> Optional[SkillContract]:
        """Get a skill by name.

        Args:
            name: Skill name (case-insensitive).

        Returns:
            SkillContract if found, None otherwise.
        """
        return self._skills.get(name.lower())

    def get_all(self) -> Dict[str, SkillContract]:
        """Return all loaded skills."""
        return dict(self._skills)

    def get_enabled(self) -> List[SkillContract]:
        """Return all enabled skills."""
        return [s for s in self._skills.values() if s.is_enabled]

    def get_by_tier(self, tier: SkillTier) -> List[SkillContract]:
        """Return all skills in a specific tier."""
        return [s for s in self._skills.values() if s.tier == tier]

    def get_by_agent(self, agent_name: str) -> List[SkillContract]:
        """Return skills available to a specific agent.

        Skills with empty agent allowlist are available to all agents.
        """
        return [
            s
            for s in self._skills.values()
            if s.is_enabled
            and (not s.frontmatter.agents or agent_name in s.frontmatter.agents)
        ]

    def disable(self, name: str, reason: str = "") -> bool:
        """Disable a skill by name.

        Args:
            name: Skill name.
            reason: Reason for disabling.

        Returns:
            True if skill was found and disabled.
        """
        skill = self._skills.get(name)
        if skill:
            skill.state = SkillState.DISABLED
            skill.load_error = reason
            return True
        return False

    def enable(self, name: str) -> bool:
        """Re-enable a previously disabled skill.

        Args:
            name: Skill name.

        Returns:
            True if skill was found and enabled.
        """
        skill = self._skills.get(name)
        if skill:
            skill.state = SkillState.ENABLED
            skill.load_error = ""
            return True
        return False

    def match(
        self,
        query: str,
        top_n: int = 5,
        agent_name: Optional[str] = None,
    ) -> List[MatchResult]:
        """Match a natural language query to skills.

        Args:
            query: Natural language query.
            top_n: Maximum results to return.
            agent_name: Filter by agent allowlist. Uses default_agent if None.

        Returns:
            List of MatchResult sorted by score.
        """
        agent = agent_name or self._default_agent
        candidates = self.get_by_agent(agent) if agent else self.get_enabled()
        return self._matcher.match(query, top_n=top_n, skills=candidates)

    def match_by_trigger(self, trigger_phrase: str) -> List[MatchResult]:
        """Match skills by exact trigger phrase."""
        return self._matcher.match_by_trigger(trigger_phrase)

    def assemble_prompt(
        self,
        skills: Optional[List[SkillContract]] = None,
        tier: PromptTier = PromptTier.FULL,
        agent_name: Optional[str] = None,
        extra_context: str = "",
    ) -> CompactionResult:
        """Assemble skills into system prompt content.

        Args:
            skills: Skills to include. If None, uses all enabled skills.
            tier: Compaction level.
            agent_name: Filter by agent allowlist.
            extra_context: Additional context to prepend.

        Returns:
            CompactionResult with assembled prompt.
        """
        if skills is None:
            agent = agent_name or self._default_agent
            skills = self.get_by_agent(agent) if agent else self.get_enabled()
        return self._assembler.assemble(
            skills, tier=tier, agent_name=agent_name, extra_context=extra_context
        )

    def compute_fingerprint(self, skills: Optional[List[SkillContract]] = None) -> str:
        """Compute cache-friendly fingerprint for skill set."""
        if skills is None:
            skills = self.get_enabled()
        return self._assembler.compute_fingerprint(skills)

    def estimate_token_cost(self, skills: Optional[List[SkillContract]] = None) -> int:
        """Estimate total token cost for skills."""
        if skills is None:
            skills = self.get_enabled()
        return self._assembler.estimate_total_tokens(skills)

    def get_stats(self) -> SkillManagerStats:
        """Get runtime statistics."""
        stats = SkillManagerStats()
        stats.total_loaded = len(self._skills)
        for skill in self._skills.values():
            if skill.state == SkillState.ENABLED:
                stats.enabled += 1
                stats.total_token_cost += skill.compute_token_cost()
            elif skill.state == SkillState.DISABLED:
                stats.disabled += 1
            elif skill.state == SkillState.ERROR:
                stats.errored += 1
            stats.tier_counts[skill.tier.name] = (
                stats.tier_counts.get(skill.tier.name, 0) + 1
            )
        return stats

    def observe_procedure(
        self,
        name: str,
        procedure: str,
        context: str,
        tools_used: Optional[List[str]] = None,
    ) -> WorkshopObservation:
        """Record an observed procedure for potential skill generation.

        Args:
            name: Proposed skill name.
            procedure: Step-by-step description.
            context: When/why this was invoked.
            tools_used: Tools used during the procedure.

        Returns:
            The created observation.
        """
        existing = next(
            (o for o in self._workshop if o.name == name), None
        )
        if existing:
            existing.frequency += 1
            if tools_used:
                existing.tools_used.extend(tools_used)
            return existing

        obs = WorkshopObservation(
            name=name,
            procedure=procedure,
            context=context,
            tools_used=tools_used or [],
        )
        self._workshop.append(obs)
        return obs

    def generate_skill_from_observation(
        self, observation: WorkshopObservation, output_dir: str
    ) -> SkillContract:
        """Generate a skill SKILL.md from a workshop observation.

        Args:
            observation: The observation to convert.
            output_dir: Directory to write the skill.

        Returns:
            The generated SkillContract.
        """
        frontmatter = observation.to_skill_scaffold()
        body = (
            f"# {observation.name}\n\n"
            f"## Procedure\n\n{observation.procedure}\n\n"
            f"## Context\n\n{observation.context}\n\n"
            f"## Tools Used\n\n{', '.join(observation.tools_used)}\n"
        )

        contract = SkillContract(
            frontmatter=frontmatter,
            body=body,
            tier=SkillTier.EXTRA,
            state=SkillState.ENABLED,
        )

        out_path = Path(output_dir) / observation.name
        out_path.mkdir(parents=True, exist_ok=True)
        (out_path / "SKILL.md").write_text(
            contract.to_skill_md(), encoding="utf-8"
        )

        return contract

    def get_workshop(self) -> List[WorkshopObservation]:
        """Return all workshop observations."""
        return list(self._workshop)

    def export_skill(
        self, name: str, fmt: str = "neugi"
    ) -> str:
        """Export a single skill in the specified format.

        Supported formats:
        - neugi: NEUGI JSON format
        - openclaw: OpenClaw SKILL.md format
        - claude: Claude Code .md command format
        - mcp: MCP tool definition (JSON)
        - langchain: LangChain tool definition (JSON)

        Args:
            name: Skill name to export.
            fmt: Export format.

        Returns:
            Exported content as string.

        Raises:
            KeyError: If skill not found.
            ValueError: If format not supported.
        """
        skill = self._skills.get(name)
        if not skill:
            raise KeyError(f"Skill '{name}' not found")

        if fmt == "neugi":
            return skill.to_neugi_json()
        elif fmt == "openclaw":
            return skill.to_skill_md()
        elif fmt == "claude":
            return skill.to_claude_code()
        elif fmt == "mcp":
            return json.dumps(skill.to_mcp_tool_def(), indent=2)
        elif fmt == "langchain":
            return json.dumps(skill.to_langchain_tool(), indent=2)
        else:
            raise ValueError(
                f"Unsupported format '{fmt}'. "
                "Supported: neugi, openclaw, claude, mcp, langchain"
            )

    def export_all(self, fmt: str = "neugi") -> Dict[str, str]:
        """Export all skills in the specified format.

        Args:
            fmt: Export format.

        Returns:
            Dict mapping skill name to exported content.
        """
        result: Dict[str, str] = {}
        for name in self._skills:
            try:
                result[name] = self.export_skill(name, fmt)
            except (KeyError, ValueError):
                pass
        return result

    def import_skill(self, content: str, fmt: str = "neugi") -> SkillContract:
        """Import a skill from external format.

        Args:
            content: Skill content string.
            fmt: Import format.

        Returns:
            Imported SkillContract.

        Raises:
            ValueError: If format not supported or content invalid.
        """
        if fmt == "neugi":
            return self._import_neugi(content)
        elif fmt == "openclaw":
            return self._import_openclaw(content)
        elif fmt == "claude":
            return self._import_claude(content)
        elif fmt == "mcp":
            return self._import_mcp(content)
        elif fmt == "langchain":
            return self._import_langchain(content)
        else:
            raise ValueError(
                f"Unsupported format '{fmt}'. "
                "Supported: neugi, openclaw, claude, mcp, langchain"
            )

    def import_from_directory(
        self, path: str, tier: Optional[SkillTier] = None
    ) -> List[SkillContract]:
        """Import all skills from a directory.

        Args:
            path: Directory containing skill subdirectories.
            tier: Tier to assign. Inferred from path if None.

        Returns:
            List of imported skill contracts.
        """
        imported: List[SkillContract] = []
        base = Path(path)
        if not base.is_dir():
            return imported

        for entry in sorted(base.iterdir()):
            if not entry.is_dir():
                continue
            skill_md = entry / "SKILL.md"
            if not skill_md.is_file():
                continue
            result = self._loader.load_single(str(skill_md), tier)
            if result.success and result.contract:
                imported.append(result.contract)
                self._skills[result.contract.name] = result.contract

        self._matcher.build_index(list(self._skills.values()))
        return imported

    def _import_neugi(self, content: str) -> SkillContract:
        """Import from NEUGI JSON format."""
        data = json.loads(content)
        return SkillContract.from_dict(data)

    def _import_openclaw(self, content: str) -> SkillContract:
        """Import from OpenClaw SKILL.md format."""
        if yaml is None:
            raise RuntimeError("PyYAML required for OpenClaw import")

        import re
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n(.*)", content, re.DOTALL)
        if not match:
            raise ValueError("Invalid SKILL.md: no frontmatter found")

        fm_data = yaml.safe_load(match.group(1))
        body = match.group(2).strip()
        frontmatter = SkillFrontmatter.from_dict(fm_data)

        return SkillContract(
            frontmatter=frontmatter,
            body=body,
            state=SkillState.ENABLED,
        )

    def _import_claude(self, content: str) -> SkillContract:
        """Import from Claude Code .md command format."""
        lines = content.strip().split("\n")
        name = ""
        description = ""
        body_lines: List[str] = []
        in_body = False

        for line in lines:
            if line.startswith("# ") and not name:
                name = line[2:].strip()
                in_body = True
            elif line.startswith("Tags:"):
                continue
            elif in_body:
                body_lines.append(line)

        if not name:
            name = "imported_skill"
        if body_lines:
            description = body_lines[0].strip()
            body_lines = body_lines[1:]

        frontmatter = SkillFrontmatter(
            name=name,
            description=description,
        )
        return SkillContract(
            frontmatter=frontmatter,
            body="\n".join(body_lines).strip(),
            state=SkillState.ENABLED,
        )

    def _import_mcp(self, content: str) -> SkillContract:
        """Import from MCP tool definition."""
        data = json.loads(content)
        name = data.get("name", "imported_mcp_tool")
        description = data.get("description", "")
        input_schema = data.get("inputSchema", {})
        params = []
        for prop_name, prop_def in input_schema.get("properties", {}).items():
            params.append({
                "name": prop_name,
                "type": prop_def.get("type", "string"),
                "description": prop_def.get("description", ""),
                "required": prop_name in input_schema.get("required", []),
            })

        frontmatter = SkillFrontmatter(
            name=name,
            description=description,
        )
        action = SkillAction(name="execute", description=description, parameters=params)
        return SkillContract(
            frontmatter=frontmatter,
            body="",
            actions=[action],
            state=SkillState.ENABLED,
        )

    def _import_langchain(self, content: str) -> SkillContract:
        """Import from LangChain tool definition."""
        data = json.loads(content)
        name = data.get("name", "imported_langchain_tool")
        description = data.get("description", "")
        params_def = data.get("parameters", {})
        params = []
        for prop_name, prop_def in params_def.get("properties", {}).items():
            params.append({
                "name": prop_name,
                "type": prop_def.get("type", "string"),
                "description": prop_def.get("description", ""),
                "required": prop_name in params_def.get("required", []),
            })

        frontmatter = SkillFrontmatter(
            name=name,
            description=description,
        )
        action = SkillAction(name="execute", description=description, parameters=params)
        return SkillContract(
            frontmatter=frontmatter,
            body="",
            actions=[action],
            state=SkillState.ENABLED,
        )
