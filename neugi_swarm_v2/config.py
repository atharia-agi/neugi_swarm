"""
NEUGI v2 Centralized Configuration
===================================

Loads configuration from config.json with sensible defaults.
All subsystems read from this single source of truth.

Usage:
    from neugi_swarm_v2.config import load_config, NeugiConfig

    config = load_config()
    print(config.llm.model)
    print(config.memory_dir)
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

try:
    from security.secret_manager import SecretClass, SecretManager
except ImportError:
    SecretManager = None  # type: ignore
    SecretClass = None  # type: ignore

logger = logging.getLogger(__name__)


# -- LLM Provider Configuration ----------------------------------------------

@dataclass
class LLMConfig:
    """LLM provider configuration.

    Attributes:
        provider: Provider type ('ollama', 'openai', 'anthropic').
        model: Default model name.
        fallback_model: Model to use on errors.
        base_url: Base URL for OpenAI-compatible APIs.
        ollama_url: URL for local Ollama instance.
        api_key: API key for cloud providers.
        temperature: Default sampling temperature.
        max_tokens: Maximum output tokens.
        timeout_seconds: Request timeout.
        max_retries: Number of retries on failure.
        retry_delay_seconds: Delay between retries.
    """

    provider: str = "ollama"
    model: str = "qwen2.5-coder:7b"
    fallback_model: str = "llama3.2:3b"
    base_url: str = "https://api.openai.com/v1"
    ollama_url: str = "http://localhost:11434"
    api_key: str = ""
    temperature: float = 0.7
    max_tokens: int = 4096
    timeout_seconds: float = 60.0
    max_retries: int = 3
    retry_delay_seconds: float = 2.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> LLMConfig:
        """Create from a dictionary, ignoring unknown keys."""
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


# -- Session Configuration ---------------------------------------------------

@dataclass
class NeugiSessionConfig:
    """Session lifecycle configuration.

    Attributes:
        isolation_mode: Key-space isolation strategy.
        daily_reset_hour: Hour (0-23) for daily session reset.
        idle_reset_minutes: Minutes of idle before reset (None = disabled).
        max_transcript_lines: Maximum transcript lines before pruning.
        enable_checkpointing: Enable session checkpointing.
        compaction_token_threshold: Tokens before triggering compaction.
    """

    isolation_mode: str = "shared"
    daily_reset_hour: int = 4
    idle_reset_minutes: int | None = None
    max_transcript_lines: int = 10000
    enable_checkpointing: bool = True
    compaction_token_threshold: int = 32768

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NeugiSessionConfig:
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


# -- Memory Configuration ----------------------------------------------------

@dataclass
class MemoryConfig:
    """Memory system configuration.

    Attributes:
        daily_ttl_days: Days before daily memories expire.
        scoring_recency_weight: Weight for recency in scoring.
        scoring_importance_weight: Weight for importance in scoring.
        scoring_frequency_weight: Weight for access frequency in scoring.
        scoring_relevance_weight: Weight for query relevance in scoring.
        dreaming_enabled: Enable dreaming consolidation.
        dreaming_hour: Hour to run dreaming (0-23).
        dreaming_consolidation_threshold: Memories needed before consolidation.
        enable_fts: Enable full-text search.
        enable_vec: Enable vector embeddings.
    """

    daily_ttl_days: int = 30
    scoring_recency_weight: float = 0.25
    scoring_importance_weight: float = 0.30
    scoring_frequency_weight: float = 0.20
    scoring_relevance_weight: float = 0.25
    dreaming_enabled: bool = True
    dreaming_hour: int = 3
    dreaming_consolidation_threshold: int = 50
    enable_fts: bool = True
    enable_vec: bool = False

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MemoryConfig:
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


# -- Capability Profile Configuration ----------------------------------------

@dataclass
class CapabilityProfileConfig:
    """Model capability profile configuration (auto-detected, editable).

    Attributes:
        name: Model name.
        provider: Provider name.
        tier: Model tier (local/medium/cloud).
        context_length: Context window size.
        supports_tools: Whether model supports tool use.
        supports_vision: Whether model supports vision.
        supports_json_mode: Whether model supports JSON mode.
        max_tools_per_call: Max tools per LLM call.
        effective_context_ratio: Usable context fraction.
        max_memory_entries: Max memory entries to inject.
        recommended_prompt_tier: minimal/standard/maximal.
    """

    name: str = ""
    provider: str = ""
    tier: str = "medium"
    context_length: int = 4096
    supports_tools: bool = False
    supports_vision: bool = False
    supports_json_mode: bool = False
    max_tools_per_call: int = 3
    effective_context_ratio: float = 0.75
    max_memory_entries: int = 10
    recommended_prompt_tier: str = "standard"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> CapabilityProfileConfig:
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)

    def to_profile_dict(self) -> dict[str, Any]:
        """Convert to dict for CapabilityProfile construction."""
        return {
            "name": self.name,
            "provider": self.provider,
            "tier": self.tier,
            "context_length": self.context_length,
            "supports_tools": self.supports_tools,
            "supports_vision": self.supports_vision,
            "supports_json_mode": self.supports_json_mode,
            "max_tools_per_call": self.max_tools_per_call,
            "effective_context_ratio": self.effective_context_ratio,
            "max_memory_entries": self.max_memory_entries,
            "recommended_prompt_tier": self.recommended_prompt_tier,
        }


# -- Skill Configuration -----------------------------------------------------

@dataclass
class SkillConfig:
    """Skills system configuration.

    Attributes:
        skill_dirs: List of directories to scan for skills.
        max_skills_in_prompt: Maximum skills included in a prompt.
        max_tokens_in_prompt: Token budget for skill section.
        compaction_threshold: Tokens before compacting skill prompt.
        enable_hot_reload: Enable file watcher for skill changes.
        hot_reload_interval_seconds: File watcher polling interval.
    """

    skill_dirs: list[str] = field(default_factory=lambda: [
        "workspace/skills",
        "project/skills",
        "bundled/skills",
    ])
    max_skills_in_prompt: int = 20
    max_tokens_in_prompt: int = 8000
    compaction_threshold: int = 32768
    enable_hot_reload: bool = False
    hot_reload_interval_seconds: float = 5.0

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SkillConfig:
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


# -- Agent Configuration -----------------------------------------------------

@dataclass
class AgentConfig:
    """Multi-agent system configuration.

    Attributes:
        default_agents: List of default agent names to initialize.
        xp_threshold: XP needed per level.
        max_level: Maximum agent level.
        heartbeat_interval_seconds: Seconds between heartbeats.
        max_concurrent_agents: Maximum agents running simultaneously.
        enable_evaluator_optimizer: Enable eval-optimize loop.
    """

    default_agents: list[str] = field(default_factory=lambda: [
        "Aurora", "Cipher", "Nova", "Pulse", "Quark", "Shield", "Spark", "Ink", "Nexus",
    ])
    xp_threshold: int = 100
    max_level: int = 50
    heartbeat_interval_seconds: float = 30.0
    max_concurrent_agents: int = 5
    enable_evaluator_optimizer: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> AgentConfig:
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


# -- Context Configuration ---------------------------------------------------

@dataclass
class ContextConfig:
    """Context window optimization configuration.

    Attributes:
        max_tokens: Maximum context tokens.
        max_chars: Maximum context characters (fallback).
        safety_margin: Buffer fraction (0.05 = 5%).
        identity_max_chars: Max chars for identity section.
        skills_max_chars: Max chars for skills section.
        memory_max_chars: Max chars for memory section.
        conversation_max_chars: Max chars for conversation section.
        tools_max_chars: Max chars for tools section.
        bootstrap_max_chars: Max chars for bootstrap section.
        enable_cache_stability: Enable KV cache optimization.
    """

    max_tokens: int = 200_000
    max_chars: int = 120_000
    safety_margin: float = 0.05
    identity_max_chars: int = 2000
    skills_max_chars: int = 15000
    memory_max_chars: int = 10000
    conversation_max_chars: int = 50000
    tools_max_chars: int = 10000
    bootstrap_max_chars: int = 30000
    enable_cache_stability: bool = True

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextConfig:
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


# -- Main Configuration ------------------------------------------------------

@dataclass
@dataclass
class ObservabilityConfig:
    """Observability subsystem configuration.

    Attributes:
        enabled: Enable the event bus.
        max_history: Maximum number of events to keep in history.
    """

    enabled: bool = True
    max_history: int = 1000

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ObservabilityConfig:
        known = {k: v for k, v in data.items() if k in cls.__dataclass_fields__}
        return cls(**known)


class NeugiConfig:
    """Top-level NEUGI v2 configuration.

    Attributes:
        neugi_dir: Root NEUGI directory.
        data_dir: Data storage directory.
        memory_dir: Memory storage directory.
        skills_dir: Skills storage directory.
        sessions_dir: Session storage directory.
        llm: LLM provider configuration.
        session: Session lifecycle configuration.
        memory: Memory system configuration.
        skill: Skills system configuration.
        agent: Multi-agent system configuration.
        context: Context window configuration.
        observability: Observability event bus configuration.
    """

    neugi_dir: Path = field(default_factory=lambda: Path.home() / ".neugi")
    data_dir: Path = field(default_factory=lambda: Path.home() / ".neugi" / "data")
    memory_dir: Path = field(default_factory=lambda: Path.home() / ".neugi" / "data" / "memory")
    skills_dir: Path = field(default_factory=lambda: Path.home() / ".neugi" / "data" / "skills")
    sessions_dir: Path = field(default_factory=lambda: Path.home() / ".neugi" / "data" / "sessions")

    llm: LLMConfig = field(default_factory=LLMConfig)
    session: NeugiSessionConfig = field(default_factory=NeugiSessionConfig)
    memory: MemoryConfig = field(default_factory=MemoryConfig)
    skill: SkillConfig = field(default_factory=SkillConfig)
    agent: AgentConfig = field(default_factory=AgentConfig)
    context: ContextConfig = field(default_factory=ContextConfig)
    capability_profile: CapabilityProfileConfig = field(default_factory=CapabilityProfileConfig)
    observability: ObservabilityConfig = field(default_factory=ObservabilityConfig)

    def ensure_dirs(self) -> None:
        """Create all configured directories if they don't exist."""
        for d in [self.neugi_dir, self.data_dir, self.memory_dir,
                  self.skills_dir, self.sessions_dir]:
            d.mkdir(parents=True, exist_ok=True)

    def to_session_config(self) -> SessionConfig:
        """Convert to session.SessionConfig for the session manager."""
        from neugi_swarm_v2.session import SessionConfig, SessionIsolationMode

        mode_map = {
            "shared": SessionIsolationMode.SHARED,
            "per-peer": SessionIsolationMode.PER_PEER,
            "per-channel-peer": SessionIsolationMode.PER_CHANNEL_PEER,
            "per-account-channel-peer": SessionIsolationMode.PER_ACCOUNT_CHANNEL_PEER,
        }

        return SessionConfig(
            isolation_mode=mode_map.get(
                self.session.isolation_mode, SessionIsolationMode.SHARED
            ),
            daily_reset_hour=self.session.daily_reset_hour,
            idle_reset_minutes=self.session.idle_reset_minutes,
            max_transcript_lines=self.session.max_transcript_lines,
            enable_checkpointing=self.session.enable_checkpointing,
            compaction_token_threshold=self.session.compaction_token_threshold,
        )

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> NeugiConfig:
        """Create from a dictionary, ignoring unknown keys."""
        config = cls()

        if "neugi_dir" in data:
            config.neugi_dir = Path(data["neugi_dir"])
        if "data_dir" in data:
            config.data_dir = Path(data["data_dir"])
        if "memory_dir" in data:
            config.memory_dir = Path(data["memory_dir"])
        if "skills_dir" in data:
            config.skills_dir = Path(data["skills_dir"])
        if "sessions_dir" in data:
            config.sessions_dir = Path(data["sessions_dir"])

        if "llm" in data:
            config.llm = LLMConfig.from_dict(data["llm"])
        if "session" in data:
            config.session = NeugiSessionConfig.from_dict(data["session"])
        if "memory" in data:
            config.memory = MemoryConfig.from_dict(data["memory"])
        if "skill" in data:
            config.skill = SkillConfig.from_dict(data["skill"])
        if "agent" in data:
            config.agent = AgentConfig.from_dict(data["agent"])
        if "context" in data:
            config.context = ContextConfig.from_dict(data["context"])
        if "capability_profile" in data:
            config.capability_profile = CapabilityProfileConfig.from_dict(data["capability_profile"])
        if "observability" in data:
            config.observability = ObservabilityConfig.from_dict(data["observability"])

        return config

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary."""
        return {
            "neugi_dir": str(self.neugi_dir),
            "data_dir": str(self.data_dir),
            "memory_dir": str(self.memory_dir),
            "skills_dir": str(self.skills_dir),
            "sessions_dir": str(self.sessions_dir),
            "llm": {
                "provider": self.llm.provider,
                "model": self.llm.model,
                "fallback_model": self.llm.fallback_model,
                "base_url": self.llm.base_url,
                "ollama_url": self.llm.ollama_url,
                "temperature": self.llm.temperature,
                "max_tokens": self.llm.max_tokens,
                "timeout_seconds": self.llm.timeout_seconds,
                "max_retries": self.llm.max_retries,
            },
            "session": {
                "isolation_mode": self.session.isolation_mode,
                "daily_reset_hour": self.session.daily_reset_hour,
                "idle_reset_minutes": self.session.idle_reset_minutes,
                "max_transcript_lines": self.session.max_transcript_lines,
                "enable_checkpointing": self.session.enable_checkpointing,
                "compaction_token_threshold": self.session.compaction_token_threshold,
            },
            "memory": {
                "daily_ttl_days": self.memory.daily_ttl_days,
                "dreaming_enabled": self.memory.dreaming_enabled,
                "dreaming_hour": self.memory.dreaming_hour,
                "enable_fts": self.memory.enable_fts,
            },
            "skill": {
                "skill_dirs": self.skill.skill_dirs,
                "max_skills_in_prompt": self.skill.max_skills_in_prompt,
                "max_tokens_in_prompt": self.skill.max_tokens_in_prompt,
                "enable_hot_reload": self.skill.enable_hot_reload,
            },
            "agent": {
                "default_agents": self.agent.default_agents,
                "xp_threshold": self.agent.xp_threshold,
                "max_level": self.agent.max_level,
                "heartbeat_interval_seconds": self.agent.heartbeat_interval_seconds,
            },
            "context": {
                "max_tokens": self.context.max_tokens,
                "max_chars": self.context.max_chars,
                "safety_margin": self.context.safety_margin,
            },
            "capability_profile": {
                "name": self.capability_profile.name,
                "provider": self.capability_profile.provider,
                "tier": self.capability_profile.tier,
                "context_length": self.capability_profile.context_length,
                "supports_tools": self.capability_profile.supports_tools,
                "supports_vision": self.capability_profile.supports_vision,
                "supports_json_mode": self.capability_profile.supports_json_mode,
                "max_tools_per_call": self.capability_profile.max_tools_per_call,
                "effective_context_ratio": self.capability_profile.effective_context_ratio,
                "max_memory_entries": self.capability_profile.max_memory_entries,
                "recommended_prompt_tier": self.capability_profile.recommended_prompt_tier,
            },
            "observability": {
                "enabled": self.observability.enabled,
                "max_history": self.observability.max_history,
            },
        }


# -- Config Loading (Simple) -------------------------------------------------

def load_config(
    base_dir: str | None = None,
    config_path: str | None = None,
    **overrides,
) -> NeugiConfig:
    """Load NEUGI v2 configuration.

    Simple: one JSON file, auto-generated by wizard, user-editable.

    Args:
        base_dir: Root directory. Defaults to ~/.neugi.
        config_path: Explicit path to config.json.
        **overrides: Override any field (dot-notation: llm.model='gpt-4o').

    Returns:
        NeugiConfig instance.
    """
    config = NeugiConfig()

    # Set paths
    if base_dir:
        config.neugi_dir = Path(base_dir)
        config.data_dir = config.neugi_dir / "data"
        config.memory_dir = config.data_dir / "memory"
        config.skills_dir = config.data_dir / "skills"
        config.sessions_dir = config.data_dir / "sessions"

    # Find and load config.json
    if config_path is None:
        config_path = _find_config(config.neugi_dir)

    if config_path and Path(config_path).exists():
        try:
            with open(config_path, encoding="utf-8") as f:
                data = json.load(f)

            # SECURITY: Migrate API key from plaintext config to SecretManager
            _migrate_api_key_to_secrets(data, config.neugi_dir, config_path)

            config = NeugiConfig.from_dict(data)
            # Re-apply paths if base_dir was explicit
            if base_dir:
                config.neugi_dir = Path(base_dir)
                config.data_dir = config.neugi_dir / "data"
                config.memory_dir = config.data_dir / "memory"
                config.skills_dir = config.data_dir / "skills"
                config.sessions_dir = config.data_dir / "sessions"
        except (json.JSONDecodeError, OSError) as e:
            logger.warning(
                "Failed to load config from %s: %s, using defaults", config_path, e
            )

    config.ensure_dirs()
    _apply_overrides(config, overrides)
    return config


def _find_config(neugi_dir: Path) -> str | None:
    """Find config.json in conventional locations."""
    candidates = [
        neugi_dir / "config.json",
        Path.cwd() / "config.json",
        Path.home() / ".neugi" / "config.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return str(candidate)
    return None


def _apply_overrides(config: NeugiConfig, overrides: dict[str, Any]) -> None:
    """Apply dot-notation overrides to config."""
    for key, value in overrides.items():
        parts = key.split(".")
        if len(parts) == 2:
            section, field_name = parts
            section_obj = getattr(config, section, None)
            if section_obj is not None and hasattr(section_obj, field_name):
                setattr(section_obj, field_name, value)
        elif len(parts) == 1 and hasattr(config, parts[0]):
            setattr(config, parts[0], value)


def _migrate_api_key_to_secrets(
    data: dict[str, Any], neugi_dir: Path, config_path: str
) -> None:
    """Migrate API key from plaintext config.json to SecretManager.

    If an api_key is found in the loaded JSON, it is moved to an encrypted
    SecretManager database and removed from the config file.
    """
    llm_data = data.get("llm", {})
    api_key = llm_data.get("api_key", "")
    if not api_key:
        return

    # Store in SecretManager if available
    if SecretManager is not None:
        try:
            secrets_db = neugi_dir / "secrets.db"
            manager = SecretManager(db_path=str(secrets_db))
            manager.add_secret(
                name="llm_api_key",
                value=api_key,
                secret_class=SecretClass.API_KEY,
                description="LLM provider API key (auto-migrated from config.json)",
            )
            logger.info("API key migrated to encrypted storage: %s", secrets_db)
        except Exception as e:
            logger.warning("Failed to migrate API key to SecretManager: %s", e)
            return  # Leave key in config if migration fails
    else:
        logger.warning(
            "SecretManager not available — API key remains in config.json. "
            "Set NEUGI_LLM_API_KEY environment variable instead."
        )
        return

    # Remove from config data
    del llm_data["api_key"]
    data["llm"] = llm_data

    # Rewrite config.json without the API key
    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
        logger.info("config.json rewritten without plaintext API key")
    except OSError as e:
        logger.warning("Failed to rewrite config.json after key migration: %s", e)
