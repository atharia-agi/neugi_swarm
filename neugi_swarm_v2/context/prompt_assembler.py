"""
NEUGI v2 Prompt Assembler - Dynamic modular prompt construction.

Combines best patterns from OpenClaw (SOUL.md, bootstrap files, per-file limits)
and Claude API (system prompt sections, model-specific assembly) into a single
cohesive prompt assembly engine.

Features:
    - Modular system prompt construction from named sections
    - Bootstrap file injection with budget control
    - Per-file character limits with graceful truncation
    - Warning injection when files are truncated
    - Three prompt modes: full, minimal, none
    - Deterministic ordering for cache stability
    - Graceful degradation on missing files

Prompt Modes:
    FULL: Main agent - all sections, full memory, all skills
    MINIMAL: Sub-agents/crons - identity + essential context only
    NONE: Special cases - empty prompt (raw API passthrough)

Usage:
    assembler = PromptAssembler(base_dir="/path/to/project")
    result = assembler.assemble(mode=PromptMode.FULL, agent_id="cipher")
    print(result.system_prompt)
    print(result.warnings)
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# -- Exceptions --------------------------------------------------------------

class PromptAssemblyError(Exception):
    """Raised when prompt assembly fails."""
    pass


# -- Enums -------------------------------------------------------------------

class PromptMode(Enum):
    """
    Prompt assembly modes controlling section inclusion.

    FULL: Main agent - all sections, full memory, all skills, bootstrap files.
    MINIMAL: Sub-agents/crons - identity + essential context only.
    NONE: Special cases - empty prompt (raw API passthrough).
    """
    FULL = "full"
    MINIMAL = "minimal"
    NONE = "none"


class PromptSection(Enum):
    """
    Named sections that compose a system prompt.

    Order matters for KV cache stability - sections are assembled
    in this enum order for deterministic output.
    """
    IDENTITY = "identity"
    HEARTBEAT = "heartbeat"
    SKILLS = "skills"
    MEMORY = "memory"
    PROJECT_CONTEXT = "project_context"
    VOICE_TONE = "voice_tone"
    MODEL_ALIASES = "model_aliases"
    BOOTSTRAP = "bootstrap"
    TOOLS = "tools"
    CONVERSATION = "conversation"


# -- Data Classes ------------------------------------------------------------

@dataclass
class SectionConfig:
    """
    Configuration for a single prompt section.

    Attributes:
        name: Section identifier.
        enabled: Whether to include this section.
        max_chars: Maximum character budget (None = unlimited).
        priority: Truncation priority (lower = truncate first).
        required: If True, assembly fails when section content is missing.
        template: Optional template string with {content} placeholder.
    """
    name: str
    enabled: bool = True
    max_chars: Optional[int] = None
    priority: int = 10
    required: bool = False
    template: Optional[str] = None

    def fits(self, content: str) -> tuple[str, bool]:
        """
        Check if content fits within max_chars, truncating if needed.

        Returns:
            (content_or_truncated, was_truncated)
        """
        if self.max_chars is None or len(content) <= self.max_chars:
            return content, False

        truncated = content[:self.max_chars - 200]
        truncated += f"\n\n... [truncated, {len(content) - self.max_chars + 200} chars omitted]"
        return truncated, True


@dataclass
class BootstrapFile:
    """
    A bootstrap file to inject into the prompt.

    Bootstrap files are project-specific context files (AGENTS.md, SOUL.md,
    USER.md, TOOLS.md) that define agent behavior, preferences, and tools.

    Attributes:
        path: File path (absolute or relative to base_dir).
        label: Human-readable label for the section header.
        max_chars: Per-file character limit.
        required: If True, missing file generates a warning.
        section: Which PromptSection this belongs to.
    """
    path: str
    label: str
    max_chars: int = 4000
    required: bool = False
    section: PromptSection = PromptSection.BOOTSTRAP

    def resolve(self, base_dir: Path) -> Path:
        """Resolve the file path relative to base_dir."""
        p = Path(self.path)
        if p.is_absolute():
            return p
        return base_dir / p


@dataclass
class PromptResult:
    """
    Result of prompt assembly.

    Attributes:
        system_prompt: The assembled system prompt string.
        mode: The prompt mode used.
        sections_included: List of section names that were included.
        warnings: List of warning messages (truncations, missing files).
        char_count: Total character count of the system prompt.
        assembly_time_ms: Time taken to assemble in milliseconds.
        fingerprint: SHA-256 hash of the normalized prompt.
        metadata: Additional metadata about the assembly.
    """
    system_prompt: str
    mode: PromptMode
    sections_included: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    char_count: int = 0
    assembly_time_ms: float = 0.0
    fingerprint: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.char_count == 0:
            self.char_count = len(self.system_prompt)
        if not self.fingerprint:
            self.fingerprint = hashlib.sha256(
                self.system_prompt.encode("utf-8")
            ).hexdigest()[:16]


# -- Main Assembler ----------------------------------------------------------

class PromptAssembler:
    """
    Dynamic modular prompt assembler for NEUGI v2.

    Constructs system prompts from configurable sections with budget control,
    graceful truncation, and deterministic ordering for KV cache stability.

    Usage:
        assembler = PromptAssembler(
            base_dir="/path/to/project",
            agent_id="cipher",
            model_max_chars=120000,
        )
        result = assembler.assemble(mode=PromptMode.FULL)
    """

    # Default bootstrap files
    DEFAULT_BOOTSTRAP_FILES = [
        BootstrapFile("SOUL.md", "Agent Identity", max_chars=3000, required=False),
        BootstrapFile("AGENTS.md", "Agent Guidelines", max_chars=5000, required=False),
        BootstrapFile("USER.md", "User Preferences", max_chars=3000, required=False),
        BootstrapFile("TOOLS.md", "Available Tools", max_chars=4000, required=False),
    ]

    # Section ordering for deterministic assembly (cache-friendly)
    SECTION_ORDER = [
        PromptSection.IDENTITY,
        PromptSection.HEARTBEAT,
        PromptSection.SKILLS,
        PromptSection.MEMORY,
        PromptSection.PROJECT_CONTEXT,
        PromptSection.VOICE_TONE,
        PromptSection.MODEL_ALIASES,
        PromptSection.BOOTSTRAP,
        PromptSection.TOOLS,
        PromptSection.CONVERSATION,
    ]

    # Default section configs
    DEFAULT_SECTION_CONFIGS: dict[PromptSection, SectionConfig] = {
        PromptSection.IDENTITY: SectionConfig(
            name="identity", enabled=True, max_chars=2000, priority=1, required=True
        ),
        PromptSection.HEARTBEAT: SectionConfig(
            name="heartbeat", enabled=True, max_chars=500, priority=5
        ),
        PromptSection.SKILLS: SectionConfig(
            name="skills", enabled=True, max_chars=15000, priority=8
        ),
        PromptSection.MEMORY: SectionConfig(
            name="memory", enabled=True, max_chars=10000, priority=7
        ),
        PromptSection.PROJECT_CONTEXT: SectionConfig(
            name="project_context", enabled=True, max_chars=20000, priority=6
        ),
        PromptSection.VOICE_TONE: SectionConfig(
            name="voice_tone", enabled=True, max_chars=2000, priority=3
        ),
        PromptSection.MODEL_ALIASES: SectionConfig(
            name="model_aliases", enabled=False, max_chars=1000, priority=9
        ),
        PromptSection.BOOTSTRAP: SectionConfig(
            name="bootstrap", enabled=True, max_chars=30000, priority=4
        ),
        PromptSection.TOOLS: SectionConfig(
            name="tools", enabled=True, max_chars=10000, priority=10
        ),
        PromptSection.CONVERSATION: SectionConfig(
            name="conversation", enabled=False, max_chars=50000, priority=11
        ),
    }

    def __init__(
        self,
        base_dir: str = ".",
        agent_id: str = "neugi",
        agent_name: str = "NEUGI",
        agent_role: str = "Autonomous AI Agent",
        model_max_chars: int = 120000,
        section_configs: Optional[dict[PromptSection, SectionConfig]] = None,
        bootstrap_files: Optional[list[BootstrapFile]] = None,
        heartbeat_formatter: Optional[Callable[[], str]] = None,
        skill_injector: Optional[Callable[[], str]] = None,
        memory_injector: Optional[Callable[[], str]] = None,
        tools_injector: Optional[Callable[[], str]] = None,
    ) -> None:
        """
        Initialize the prompt assembler.

        Args:
            base_dir: Root directory for resolving bootstrap file paths.
            agent_id: Unique agent identifier.
            agent_name: Display name for the agent.
            agent_role: Role description for identity section.
            model_max_chars: Maximum total characters for the assembled prompt.
            section_configs: Custom section configurations (overrides defaults).
            bootstrap_files: Custom bootstrap file list (overrides defaults).
            heartbeat_formatter: Custom heartbeat generator function.
                Signature: () -> str
            skill_injector: Custom skill content injector function.
                Signature: () -> str
            memory_injector: Custom memory content injector function.
                Signature: () -> str
            tools_injector: Custom tools content injector function.
                Signature: () -> str
        """
        self.base_dir = Path(base_dir)
        self.agent_id = agent_id
        self.agent_name = agent_name
        self.agent_role = agent_role
        self.model_max_chars = model_max_chars

        # Merge section configs
        self._section_configs: dict[PromptSection, SectionConfig] = {}
        for section, default_config in self.DEFAULT_SECTION_CONFIGS.items():
            self._section_configs[section] = default_config
        if section_configs:
            self._section_configs.update(section_configs)

        self._bootstrap_files = bootstrap_files or list(self.DEFAULT_BOOTSTRAP_FILES)
        self._heartbeat_formatter = heartbeat_formatter or self._default_heartbeat
        self._skill_injector = skill_injector
        self._memory_injector = memory_injector
        self._tools_injector = tools_injector

        # Section content cache
        self._section_content: dict[str, str] = {}
        self._last_assembly: Optional[PromptResult] = None

    # -- Public API: Assemble ------------------------------------------------

    def assemble(
        self,
        mode: PromptMode = PromptMode.FULL,
        agent_id: Optional[str] = None,
        extra_sections: Optional[dict[str, str]] = None,
        override_configs: Optional[dict[PromptSection, SectionConfig]] = None,
    ) -> PromptResult:
        """
        Assemble a complete system prompt from configured sections.

        Args:
            mode: Assembly mode (full/minimal/none).
            agent_id: Override agent ID for this assembly.
            extra_sections: Additional named sections to include.
            override_configs: Temporary section config overrides.

        Returns:
            PromptResult with assembled prompt and metadata.

        Raises:
            PromptAssemblyError: If a required section is missing.
        """
        start_time = time.monotonic()
        agent_id = agent_id or self.agent_id
        warnings: list[str] = []
        sections_included: list[str] = []

        # Handle NONE mode
        if mode == PromptMode.NONE:
            return self._build_result(
                system_prompt="",
                mode=mode,
                sections_included=[],
                warnings=warnings,
                start_time=start_time,
            )

        # Determine which sections to include based on mode
        active_sections = self._get_active_sections(mode)

        # Apply temporary config overrides
        configs = dict(self._section_configs)
        if override_configs:
            configs.update(override_configs)

        # Assemble sections in deterministic order
        section_contents: list[tuple[str, str]] = []

        for section in self.SECTION_ORDER:
            if section not in active_sections:
                continue

            config = configs.get(section)
            if config is None or not config.enabled:
                continue

            try:
                content = self._assemble_section(section, agent_id, config)
            except PromptAssemblyError as e:
                if config.required:
                    raise
                warnings.append(f"Section {section.value} skipped: {e}")
                continue

            if not content:
                if config.required:
                    raise PromptAssemblyError(
                        f"Required section {section.value} produced empty content"
                    )
                continue

            # Apply per-section budget
            truncated, was_truncated = config.fits(content)
            if was_truncated:
                truncated_len = len(content)
                warning = (
                    f"Section '{section.value}' truncated from "
                    f"{truncated_len} to {len(truncated)} chars"
                )
                warnings.append(warning)

            # Apply template if configured
            if config.template:
                truncated = config.template.format(content=truncated)

            section_contents.append((section.value, truncated))
            sections_included.append(section.value)

        # Add extra sections
        if extra_sections:
            for name, content in sorted(extra_sections.items()):
                section_contents.append((name, content))
                sections_included.append(name)

        # Bootstrap files (only in FULL mode)
        if mode == PromptMode.FULL:
            bootstrap_content, bootstrap_warnings = self._assemble_bootstrap_files()
            warnings.extend(bootstrap_warnings)
            if bootstrap_content:
                bootstrap_config = configs.get(PromptSection.BOOTSTRAP)
                if bootstrap_config:
                    truncated, was_truncated = bootstrap_config.fits(bootstrap_content)
                    if was_truncated:
                        warnings.append(
                            f"Bootstrap section truncated from "
                            f"{len(bootstrap_content)} to {len(truncated)} chars"
                        )
                    section_contents.append(
                        (PromptSection.BOOTSTRAP.value, truncated)
                    )

        # Build final prompt
        system_prompt = self._join_sections(section_contents)

        # Global budget enforcement
        if len(system_prompt) > self.model_max_chars:
            system_prompt, emergency_warnings = self._emergency_truncate(
                system_prompt, self.model_max_chars
            )
            warnings.extend(emergency_warnings)

        return self._build_result(
            system_prompt=system_prompt,
            mode=mode,
            sections_included=sections_included,
            warnings=warnings,
            start_time=start_time,
        )

    # -- Section Assembly ----------------------------------------------------

    def _get_active_sections(self, mode: PromptMode) -> set[PromptSection]:
        """Determine which sections to include based on mode."""
        if mode == PromptMode.FULL:
            return set(self.SECTION_ORDER)
        elif mode == PromptMode.MINIMAL:
            return {
                PromptSection.IDENTITY,
                PromptSection.HEARTBEAT,
            }
        return set()

    def _assemble_section(
        self,
        section: PromptSection,
        agent_id: str,
        config: SectionConfig,
    ) -> str:
        """Assemble content for a single section."""
        if section == PromptSection.IDENTITY:
            return self._build_identity(agent_id)
        elif section == PromptSection.HEARTBEAT:
            return self._heartbeat_formatter()
        elif section == PromptSection.SKILLS:
            return self._inject_skills()
        elif section == PromptSection.MEMORY:
            return self._inject_memory()
        elif section == PromptSection.PROJECT_CONTEXT:
            return self._build_project_context()
        elif section == PromptSection.VOICE_TONE:
            return self._build_voice_tone()
        elif section == PromptSection.MODEL_ALIASES:
            return self._build_model_aliases()
        elif section == PromptSection.TOOLS:
            return self._inject_tools()
        elif section == PromptSection.CONVERSATION:
            return self._section_content.get("conversation", "")
        elif section == PromptSection.BOOTSTRAP:
            return ""  # Handled separately
        else:
            return ""

    def _build_identity(self, agent_id: str) -> str:
        """Build the identity section."""
        lines = [
            f"# Identity",
            f"",
            f"You are {self.agent_name} ({agent_id}).",
            f"Role: {self.agent_role}",
            f"Agent ID: {agent_id}",
            f"System: NEUGI v2 Autonomous Agent Framework",
            f"",
        ]
        return "\n".join(lines)

    def _default_heartbeat(self) -> str:
        """Generate default heartbeat content."""
        now = datetime.now(timezone.utc)
        lines = [
            "# Heartbeat",
            "",
            f"Current UTC: {now.isoformat()}",
            f"Timestamp: {int(now.timestamp())}",
            f"Status: active",
            "",
        ]
        return "\n".join(lines)

    def _inject_skills(self) -> str:
        """Inject skill content from the skill injector."""
        if self._skill_injector:
            try:
                content = self._skill_injector()
                if content:
                    return f"# Skills\n\n{content}"
            except Exception as e:
                logger.warning("Skill injection failed: %s", e)
        return ""

    def _inject_memory(self) -> str:
        """Inject memory content from the memory injector."""
        if self._memory_injector:
            try:
                content = self._memory_injector()
                if content:
                    return f"# Memory\n\n{content}"
            except Exception as e:
                logger.warning("Memory injection failed: %s", e)
        return ""

    def _inject_tools(self) -> str:
        """Inject tools content from the tools injector."""
        if self._tools_injector:
            try:
                content = self._tools_injector()
                if content:
                    return f"# Tools\n\n{content}"
            except Exception as e:
                logger.warning("Tools injection failed: %s", e)
        return ""

    def _build_project_context(self) -> str:
        """Build project context section from base directory."""
        lines = ["# Project Context", ""]
        context_files = ["CLAUDE.md", "README.md", "ARCHITECTURE.md"]

        for filename in context_files:
            filepath = self.base_dir / filename
            if filepath.exists():
                try:
                    content = filepath.read_text(encoding="utf-8")
                    lines.append(f"## {filename}")
                    lines.append("")
                    lines.append(content[:3000])
                    if len(content) > 3000:
                        lines.append(f"\n... [{len(content) - 3000} chars omitted]")
                    lines.append("")
                except Exception as e:
                    logger.warning("Failed to read %s: %s", filename, e)

        return "\n".join(lines) if len(lines) > 2 else ""

    def _build_voice_tone(self) -> str:
        """Build voice and tone instructions."""
        lines = [
            "# Voice & Tone",
            "",
            "- Be concise and direct",
            "- Prefer code over explanation",
            "- Use technical precision",
            "- Avoid filler and preamble",
            "- Match the user's communication style",
            "",
        ]
        return "\n".join(lines)

    def _build_model_aliases(self) -> str:
        """Build model aliases section."""
        lines = [
            "# Model Aliases",
            "",
            "Model aliases map human-readable names to specific model versions.",
            "Use the alias specified in task configuration to select the model.",
            "",
            "Available aliases:",
            "- fast: Fast inference model (low latency)",
            "- balanced: Balanced performance and cost",
            "- smart: High-reasoning model for complex tasks",
            "",
        ]
        return "\n".join(lines)

    # -- Bootstrap Files -----------------------------------------------------

    def _assemble_bootstrap_files(self) -> tuple[str, list[str]]:
        """
        Assemble all bootstrap files into a single section.

        Returns:
            (combined_content, warnings)
        """
        parts: list[str] = []
        warnings: list[str] = []

        for bf in self._bootstrap_files:
            filepath = bf.resolve(self.base_dir)
            try:
                if not filepath.exists():
                    if bf.required:
                        warnings.append(f"Required bootstrap file missing: {bf.label} ({filepath})")
                    continue

                content = filepath.read_text(encoding="utf-8")
                original_len = len(content)

                if original_len > bf.max_chars:
                    content = content[:bf.max_chars - 200]
                    content += f"\n\n... [truncated, {original_len - bf.max_chars + 200} chars omitted]"
                    warnings.append(
                        f"Bootstrap file '{bf.label}' truncated from "
                        f"{original_len} to {bf.max_chars} chars"
                    )

                parts.append(f"## {bf.label}\n\n{content}")

            except Exception as e:
                warning = f"Failed to read bootstrap file '{bf.label}': {e}"
                if bf.required:
                    warnings.append(warning)
                else:
                    logger.debug(warning)

        if not parts:
            return "", warnings

        combined = "\n\n---\n\n".join(parts)
        return f"# Bootstrap Files\n\n{combined}", warnings

    # -- Emergency Truncation ------------------------------------------------

    def _emergency_truncate(
        self, prompt: str, max_chars: int
    ) -> tuple[str, list[str]]:
        """
        Emergency truncation when prompt exceeds global budget.

        Truncates from the end, preserving critical sections at the top.

        Returns:
            (truncated_prompt, warnings)
        """
        warnings: list[str] = []
        original_len = len(prompt)

        if original_len <= max_chars:
            return prompt, warnings

        # Preserve the first max_chars - 500 characters
        preserved = prompt[:max_chars - 500]
        truncated = (
            f"{preserved}\n\n"
            f"[EMERGENCY TRUNCATION: {original_len - max_chars + 500} chars omitted "
            f"to fit within {max_chars} char budget]"
        )

        warnings.append(
            f"Emergency truncation: {original_len} -> {len(truncated)} chars "
            f"(budget: {max_chars})"
        )
        return truncated, warnings

    # -- Utilities -----------------------------------------------------------

    def _join_sections(self, sections: list[tuple[str, str]]) -> str:
        """Join sections with separators."""
        parts: list[str] = []
        for name, content in sections:
            if content:
                parts.append(content)

        return "\n\n---\n\n".join(parts)

    def _build_result(
        self,
        system_prompt: str,
        mode: PromptMode,
        sections_included: list[str],
        warnings: list[str],
        start_time: float,
    ) -> PromptResult:
        """Build a PromptResult from assembly data."""
        elapsed_ms = (time.monotonic() - start_time) * 1000

        result = PromptResult(
            system_prompt=system_prompt,
            mode=mode,
            sections_included=sections_included,
            warnings=warnings,
            char_count=len(system_prompt),
            assembly_time_ms=round(elapsed_ms, 2),
        )

        self._last_assembly = result
        return result

    # -- Configuration -------------------------------------------------------

    def set_section_config(
        self, section: PromptSection, config: SectionConfig
    ) -> None:
        """Update configuration for a section."""
        self._section_configs[section] = config

    def get_section_config(self, section: PromptSection) -> Optional[SectionConfig]:
        """Get configuration for a section."""
        return self._section_configs.get(section)

    def add_bootstrap_file(self, bootstrap_file: BootstrapFile) -> None:
        """Add a bootstrap file to the injection list."""
        self._bootstrap_files.append(bootstrap_file)

    def remove_bootstrap_file(self, label: str) -> bool:
        """Remove a bootstrap file by label. Returns True if found."""
        original_len = len(self._bootstrap_files)
        self._bootstrap_files = [bf for bf in self._bootstrap_files if bf.label != label]
        return len(self._bootstrap_files) < original_len

    def set_section_content(self, section_name: str, content: str) -> None:
        """Set raw content for a named section (e.g., conversation history)."""
        self._section_content[section_name] = content

    def clear_section_content(self, section_name: str) -> None:
        """Clear content for a named section."""
        self._section_content.pop(section_name, None)

    @property
    def last_assembly(self) -> Optional[PromptResult]:
        """Get the result of the last assembly."""
        return self._last_assembly

    @property
    def section_configs(self) -> dict[PromptSection, SectionConfig]:
        """Get all section configurations."""
        return dict(self._section_configs)

    @property
    def bootstrap_files(self) -> list[BootstrapFile]:
        """Get all bootstrap files."""
        return list(self._bootstrap_files)
