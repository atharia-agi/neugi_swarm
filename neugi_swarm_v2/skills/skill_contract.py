"""Skill definition contract - SKILL.md format specification and validation."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class SkillTier(Enum):
    """Six-tier skill loading precedence (higher index = higher priority)."""

    BUNDLED = 0
    EXTRA = 1
    MANAGED = 2
    PERSONAL = 3
    PROJECT = 4
    WORKSPACE = 5

    @classmethod
    def from_path(cls, path: str) -> "SkillTier":
        """Infer tier from directory path heuristics."""
        path_lower = path.lower()
        if "workspace" in path_lower or "ws" in path_lower:
            return cls.WORKSPACE
        if "project" in path_lower or "proj" in path_lower:
            return cls.PROJECT
        if "personal" in path_lower or "user" in path_lower:
            return cls.PERSONAL
        if "managed" in path_lower or "admin" in path_lower:
            return cls.MANAGED
        if "extra" in path_lower or "community" in path_lower:
            return cls.EXTRA
        return cls.BUNDLED

    @property
    def priority(self) -> int:
        return self.value


class SkillState(Enum):
    """Skill lifecycle states."""

    LOADING = "loading"
    ENABLED = "enabled"
    DISABLED = "disabled"
    ERROR = "error"


@dataclass
class SkillAction:
    """A typed action that a skill can perform.

    Attributes:
        name: Machine-readable action identifier.
        description: Human-readable description of what the action does.
        parameters: Ordered list of parameter definitions.
        returns: Description of the return value, if any.
        side_effects: List of side effects (e.g., 'writes_file', 'network_call').
    """

    name: str
    description: str
    parameters: List[Dict[str, Any]] = field(default_factory=list)
    returns: Optional[str] = None
    side_effects: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary."""
        result: Dict[str, Any] = {
            "name": self.name,
            "description": self.description,
        }
        if self.parameters:
            result["parameters"] = self.parameters
        if self.returns:
            result["returns"] = self.returns
        if self.side_effects:
            result["side_effects"] = self.side_effects
        return result

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillAction":
        """Deserialize from dictionary."""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            parameters=data.get("parameters", []),
            returns=data.get("returns"),
            side_effects=data.get("side_effects", []),
        )


@dataclass
class SkillFrontmatter:
    """YAML frontmatter schema for SKILL.md files.

    This matches the OpenClaw SKILL.md format and extends it with
    NEUGI-specific fields for gating, token budgeting, and agent routing.

    Required fields:
        name: Unique skill identifier (snake_case or kebab-case).
        description: One-line summary shown in skill lists.

    Optional fields:
        version: Semantic version string (e.g., "1.2.0").
        author: Author or organization name.
        tags: List of keyword tags for matching.
        allowed_tools: List of tool names this skill may invoke.
        requires: List of prerequisite skill names.
        bins: List of required executables (checked at load time).
        env: Dict of required environment variables.
        config: Dict of required configuration keys.
        os: List of allowed OS platforms (linux, darwin, win32).
        always: If True, skip all gating checks.
        agents: List of agent names allowed to use this skill (empty = all).
        triggers: List of natural language trigger phrases.
        category: High-level category for fallback matching.
        token_estimate: Approximate token cost when loaded into prompt.
        max_skills_in_prompt: Max concurrent skills of this tier in prompt.
    """

    name: str
    description: str
    version: str = "1.0.0"
    author: str = ""
    tags: List[str] = field(default_factory=list)
    allowed_tools: List[str] = field(default_factory=list)
    requires: List[str] = field(default_factory=list)
    bins: List[str] = field(default_factory=list)
    env: Dict[str, str] = field(default_factory=dict)
    config: Dict[str, str] = field(default_factory=dict)
    os: List[str] = field(default_factory=list)
    always: bool = False
    agents: List[str] = field(default_factory=list)
    triggers: List[str] = field(default_factory=list)
    category: str = ""
    token_estimate: int = 0
    max_skills_in_prompt: int = 0

    _NAME_RE = re.compile(r"^[a-z0-9][a-z0-9_-]*$")

    def validate(self) -> List[str]:
        """Validate frontmatter fields. Returns list of error messages."""
        errors: List[str] = []
        if not self.name:
            errors.append("name is required")
        elif not self._NAME_RE.match(self.name):
            errors.append(
                f"name '{self.name}' must be snake_case or kebab-case"
            )
        if not self.description:
            errors.append("description is required")
        if self.version and not re.match(r"^\d+\.\d+\.\d+$", self.version):
            errors.append(f"version '{self.version}' must be semver")
        if self.token_estimate < 0:
            errors.append("token_estimate must be non-negative")
        if self.max_skills_in_prompt < 0:
            errors.append("max_skills_in_prompt must be non-negative")
        return errors

    def to_yaml(self) -> str:
        """Serialize to YAML string (without --- delimiters)."""
        try:
            import yaml
        except ImportError:
            raise RuntimeError("PyYAML is required for YAML serialization")

        data: Dict[str, Any] = {
            "name": self.name,
            "description": self.description,
        }
        if self.version != "1.0.0":
            data["version"] = self.version
        if self.author:
            data["author"] = self.author
        if self.tags:
            data["tags"] = self.tags
        if self.allowed_tools:
            data["allowed_tools"] = self.allowed_tools
        if self.requires:
            data["requires"] = self.requires
        if self.bins:
            data["bins"] = self.bins
        if self.env:
            data["env"] = self.env
        if self.config:
            data["config"] = self.config
        if self.os:
            data["os"] = self.os
        if self.always:
            data["always"] = True
        if self.agents:
            data["agents"] = self.agents
        if self.triggers:
            data["triggers"] = self.triggers
        if self.category:
            data["category"] = self.category
        if self.token_estimate:
            data["token_estimate"] = self.token_estimate
        if self.max_skills_in_prompt:
            data["max_skills_in_prompt"] = self.max_skills_in_prompt

        return yaml.dump(data, default_flow_style=False, sort_keys=False).rstrip()

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillFrontmatter":
        """Create from dictionary (e.g., parsed YAML)."""
        return cls(
            name=data.get("name", ""),
            description=data.get("description", ""),
            version=data.get("version", "1.0.0"),
            author=data.get("author", ""),
            tags=data.get("tags", []),
            allowed_tools=data.get("allowed_tools", []),
            requires=data.get("requires", []),
            bins=data.get("bins", []),
            env=data.get("env", {}),
            config=data.get("config", {}),
            os=data.get("os", []),
            always=data.get("always", False),
            agents=data.get("agents", []),
            triggers=data.get("triggers", []),
            category=data.get("category", ""),
            token_estimate=data.get("token_estimate", 0),
            max_skills_in_prompt=data.get("max_skills_in_prompt", 0),
        )


@dataclass
class SkillContract:
    """Complete skill definition combining frontmatter, body, and metadata.

    This is the canonical representation of a loaded skill used throughout
    the NEUGI v2 system.

    Attributes:
        frontmatter: Parsed YAML frontmatter.
        body: Markdown body text (after frontmatter).
        tier: Loading tier (determines precedence).
        state: Current lifecycle state.
        path: Absolute path to the SKILL.md file.
        scripts: List of loaded script paths from scripts/ subdirectory.
        references: List of loaded reference paths from references/ subdirectory.
        assets: List of asset paths from assets/ subdirectory.
        actions: List of defined skill actions.
        load_error: Error message if state is ERROR.
    """

    frontmatter: SkillFrontmatter
    body: str
    tier: SkillTier = SkillTier.BUNDLED
    state: SkillState = SkillState.LOADING
    path: str = ""
    scripts: List[str] = field(default_factory=list)
    references: List[str] = field(default_factory=list)
    assets: List[str] = field(default_factory=list)
    actions: List[SkillAction] = field(default_factory=list)
    load_error: str = ""

    @property
    def name(self) -> str:
        return self.frontmatter.name

    @property
    def description(self) -> str:
        return self.frontmatter.description

    @property
    def tags(self) -> List[str]:
        return self.frontmatter.tags

    @property
    def category(self) -> str:
        return self.frontmatter.category

    @property
    def token_estimate(self) -> int:
        return self.frontmatter.token_estimate

    @property
    def is_enabled(self) -> bool:
        return self.state == SkillState.ENABLED

    def compute_token_cost(self) -> int:
        """Compute deterministic token cost for this skill in prompt.

        Uses frontmatter estimate if set, otherwise calculates from
        body length using a conservative 4 chars/token ratio.
        """
        if self.frontmatter.token_estimate > 0:
            return self.frontmatter.token_estimate
        body_tokens = len(self.body) // 4
        meta_tokens = len(self.frontmatter.description) // 4
        tag_tokens = sum(len(t) // 4 for t in self.frontmatter.tags)
        action_tokens = sum(
            len(a.name) // 4 + len(a.description) // 4 for a in self.actions
        )
        return max(1, body_tokens + meta_tokens + tag_tokens + action_tokens)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dictionary for export."""
        return {
            "frontmatter": {
                "name": self.frontmatter.name,
                "description": self.frontmatter.description,
                "version": self.frontmatter.version,
                "author": self.frontmatter.author,
                "tags": self.frontmatter.tags,
                "allowed_tools": self.frontmatter.allowed_tools,
                "requires": self.frontmatter.requires,
                "bins": self.frontmatter.bins,
                "env": self.frontmatter.env,
                "config": self.frontmatter.config,
                "os": self.frontmatter.os,
                "always": self.frontmatter.always,
                "agents": self.frontmatter.agents,
                "triggers": self.frontmatter.triggers,
                "category": self.frontmatter.category,
                "token_estimate": self.frontmatter.token_estimate,
                "max_skills_in_prompt": self.frontmatter.max_skills_in_prompt,
            },
            "body": self.body,
            "tier": self.tier.name,
            "state": self.state.value,
            "path": self.path,
            "scripts": self.scripts,
            "references": self.references,
            "assets": self.assets,
            "actions": [a.to_dict() for a in self.actions],
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SkillContract":
        """Deserialize from dictionary."""
        fm_data = data.get("frontmatter", {})
        frontmatter = SkillFrontmatter.from_dict(fm_data)
        actions = [
            SkillAction.from_dict(a) for a in data.get("actions", [])
        ]
        return cls(
            frontmatter=frontmatter,
            body=data.get("body", ""),
            tier=SkillTier[data.get("tier", "BUNDLED")],
            state=SkillState(data.get("state", "loading")),
            path=data.get("path", ""),
            scripts=data.get("scripts", []),
            references=data.get("references", []),
            assets=data.get("assets", []),
            actions=actions,
            load_error=data.get("load_error", ""),
        )

    def to_skill_md(self) -> str:
        """Export as OpenClaw-compatible SKILL.md format."""
        yaml_str = self.frontmatter.to_yaml()
        return f"---\n{yaml_str}\n---\n\n{self.body}"

    def to_neugi_json(self) -> str:
        """Export as NEUGI JSON format."""
        import json
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)

    def to_claude_code(self) -> str:
        """Export as Claude Code .md command format.

        Claude Code commands are markdown files in .claude/commands/.
        This produces a compatible format.
        """
        lines = [f"# {self.name}", ""]
        if self.frontmatter.description:
            lines.append(self.frontmatter.description)
            lines.append("")
        if self.frontmatter.tags:
            lines.append(f"Tags: {', '.join(self.frontmatter.tags)}")
            lines.append("")
        if self.body:
            lines.append(self.body)
        return "\n".join(lines)

    def to_mcp_tool_def(self) -> Dict[str, Any]:
        """Export as MCP tool definition schema."""
        properties: Dict[str, Any] = {}
        required: List[str] = []
        for param in self.actions[0].parameters if self.actions else []:
            prop_name = param.get("name", "")
            properties[prop_name] = {
                "type": param.get("type", "string"),
                "description": param.get("description", ""),
            }
            if param.get("required", False):
                required.append(prop_name)

        return {
            "name": self.name,
            "description": self.frontmatter.description,
            "inputSchema": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        }

    def to_langchain_tool(self) -> Dict[str, Any]:
        """Export as LangChain-compatible tool definition."""
        return {
            "name": self.name,
            "description": self.frontmatter.description,
            "parameters": {
                "type": "object",
                "properties": {
                    p["name"]: {
                        "type": p.get("type", "string"),
                        "description": p.get("description", ""),
                    }
                    for p in (self.actions[0].parameters if self.actions else [])
                },
                "required": [
                    p["name"]
                    for p in (self.actions[0].parameters if self.actions else [])
                    if p.get("required", False)
                ],
            },
        }
