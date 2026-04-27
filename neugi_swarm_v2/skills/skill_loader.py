"""Skill discovery and loading - directory scanning, parsing, gating, and hot reload."""

from __future__ import annotations

import os
import platform
import re
import sys
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

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

# Regex for YAML frontmatter block: ---\n...\n---
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)", re.DOTALL)


@dataclass
class GatingResult:
    """Result of evaluating skill gating conditions.

    Attributes:
        passed: Whether all gating conditions are satisfied.
        reasons: List of human-readable reasons for pass/fail.
        failed_check: Name of the first failed check, if any.
    """

    passed: bool
    reasons: List[str] = field(default_factory=list)
    failed_check: Optional[str] = None

    @classmethod
    def ok(cls, reason: str = "") -> "GatingResult":
        result = cls(passed=True)
        if reason:
            result.reasons.append(reason)
        return result

    @classmethod
    def fail(cls, check: str, reason: str) -> "GatingResult":
        return cls(passed=False, reasons=[reason], failed_check=check)


@dataclass
class SkillParseResult:
    """Result of parsing a SKILL.md file.

    Attributes:
        success: Whether parsing succeeded.
        contract: Parsed skill contract, if successful.
        error: Error message, if parsing failed.
    """

    success: bool
    contract: Optional[SkillContract] = None
    error: str = ""


class SkillLoader:
    """Discovers, parses, gates, and loads skills from directory trees.

    Supports hot reload via file watchers (polling-based for cross-platform
    compatibility).

    Usage:
        loader = SkillLoader()
        loader.add_search_path("/path/to/skills", tier=SkillTier.PROJECT)
        contracts = loader.load_all()
    """

    def __init__(self) -> None:
        self._search_paths: List[Tuple[Path, SkillTier]] = []
        self._loaded_contracts: Dict[str, SkillContract] = {}
        self._file_hashes: Dict[str, str] = {}
        self._watch_thread: Optional[threading.Thread] = None
        self._watching = False
        self._on_reload: Optional[Callable[[], None]] = None
        self._lock = threading.Lock()

    def add_search_path(self, path: str, tier: Optional[SkillTier] = None) -> None:
        """Add a directory to scan for skill directories.

        Args:
            path: Directory path to scan.
            tier: Loading tier for skills found here. If None, inferred from path.
        """
        p = Path(path).resolve()
        if tier is None:
            tier = SkillTier.from_path(str(p))
        self._search_paths.append((p, tier))

    def set_reload_callback(self, callback: Callable[[], None]) -> None:
        """Set callback invoked when hot reload detects changes.

        Args:
            callback: Zero-argument function called on change detection.
        """
        self._on_reload = callback

    def start_watching(self, interval: float = 5.0) -> None:
        """Start background file watcher for hot reload.

        Args:
            interval: Polling interval in seconds.
        """
        if self._watching:
            return
        self._watching = True
        self._watch_thread = threading.Thread(
            target=self._watch_loop, args=(interval,), daemon=True
        )
        self._watch_thread.start()

    def stop_watching(self) -> None:
        """Stop the background file watcher."""
        self._watching = False
        if self._watch_thread:
            self._watch_thread.join(timeout=10)
            self._watch_thread = None

    def load_all(self) -> Dict[str, SkillContract]:
        """Load all skills from registered search paths.

        Returns:
            Dict mapping skill name to SkillContract. Higher-tier skills
            overwrite lower-tier skills with the same name.
        """
        contracts: Dict[str, SkillContract] = {}

        for search_path, tier in self._search_paths:
            if not search_path.is_dir():
                continue
            for entry in sorted(search_path.iterdir()):
                if not entry.is_dir():
                    continue
                skill_md = entry / "SKILL.md"
                if not skill_md.is_file():
                    continue
                result = self._parse_skill_file(skill_md, tier)
                if result.success and result.contract:
                    contract = result.contract
                    existing = contracts.get(contract.name)
                    if existing is None or tier.priority > existing.tier.priority:
                        contracts[contract.name] = contract

        with self._lock:
            self._loaded_contracts = contracts
            self._index_hashes()

        return contracts

    def reload_changed(self) -> List[str]:
        """Check for changed files and reload affected skills.

        Returns:
            List of skill names that were reloaded.
        """
        changed: List[str] = []
        current_hashes: Dict[str, str] = {}

        for search_path, tier in self._search_paths:
            if not search_path.is_dir():
                continue
            for entry in sorted(search_path.iterdir()):
                if not entry.is_dir():
                    continue
                skill_md = entry / "SKILL.md"
                if not skill_md.is_file():
                    continue
                h = self._hash_file(skill_md)
                current_hashes[str(skill_md)] = h
                old_h = self._file_hashes.get(str(skill_md))
                if old_h and old_h != h:
                    result = self._parse_skill_file(skill_md, tier)
                    if result.success and result.contract:
                        with self._lock:
                            self._loaded_contracts[result.contract.name] = result.contract
                        changed.append(result.contract.name)

        with self._lock:
            self._file_hashes = current_hashes

        return changed

    def load_single(self, path: str, tier: Optional[SkillTier] = None) -> SkillParseResult:
        """Load a single SKILL.md file.

        Args:
            path: Path to SKILL.md file.
            tier: Loading tier. Inferred from path if None.

        Returns:
            Parse result with contract or error.
        """
        p = Path(path).resolve()
        if tier is None:
            tier = SkillTier.from_path(str(p))
        return self._parse_skill_file(p, tier)

    def get_loaded(self) -> Dict[str, SkillContract]:
        """Return currently loaded skill contracts."""
        with self._lock:
            return dict(self._loaded_contracts)

    def _parse_skill_file(
        self, path: Path, tier: SkillTier
    ) -> SkillParseResult:
        """Parse a single SKILL.md file into a SkillContract."""
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as e:
            return SkillParseResult(success=False, error=f"Cannot read file: {e}")

        fm_match = _FRONTMATTER_RE.match(content)
        if not fm_match:
            return SkillParseResult(
                success=False, error="No YAML frontmatter found"
            )

        yaml_text = fm_match.group(1)
        body = fm_match.group(2).strip()

        if yaml is None:
            return SkillParseResult(
                success=False, error="PyYAML is required but not installed"
            )

        try:
            fm_data = yaml.safe_load(yaml_text)
        except yaml.YAMLError as e:
            return SkillParseResult(
                success=False, error=f"Invalid YAML frontmatter: {e}"
            )

        if not isinstance(fm_data, dict):
            return SkillParseResult(
                success=False, error="YAML frontmatter must be a mapping"
            )

        frontmatter = SkillFrontmatter.from_dict(fm_data)
        errors = frontmatter.validate()
        if errors:
            return SkillParseResult(
                success=False, error="; ".join(errors)
            )

        contract = SkillContract(
            frontmatter=frontmatter,
            body=body,
            tier=tier,
            path=str(path),
        )

        # Load subdirectory contents
        skill_dir = path.parent
        contract.scripts = self._load_directory(skill_dir / "scripts")
        contract.references = self._load_directory(skill_dir / "references")
        contract.assets = self._load_directory(skill_dir / "assets")

        # Parse actions from body (look for ## Action: patterns)
        contract.actions = self._parse_actions(body)

        # Evaluate gating
        gate = self._evaluate_gating(frontmatter)
        if not gate.passed:
            contract.state = SkillState.DISABLED
            contract.load_error = f"Gated: {gate.failed_check} - {', '.join(gate.reasons)}"
        else:
            contract.state = SkillState.ENABLED

        return SkillParseResult(success=True, contract=contract)

    def _load_directory(self, dir_path: Path) -> List[str]:
        """List files in a skill subdirectory. Returns relative paths."""
        if not dir_path.is_dir():
            return []
        return [
            str(f.relative_to(dir_path))
            for f in sorted(dir_path.iterdir())
            if f.is_file()
        ]

    def _parse_actions(self, body: str) -> List[SkillAction]:
        """Extract action definitions from markdown body.

        Looks for patterns like:
            ## Action: action_name
            Description text...
        """
        actions: List[SkillAction] = []
        action_re = re.compile(r"^##\s+[Aa]ction:\s+(\S+)\s*$", re.MULTILINE)
        for match in action_re.finditer(body):
            name = match.group(1)
            start = match.end()
            next_match = action_re.search(body, start)
            section = body[start:next_match.start()] if next_match else body[start:]
            description = section.strip().split("\n")[0].strip()
            actions.append(SkillAction(name=name, description=description))
        return actions

    def _evaluate_gating(self, fm: SkillFrontmatter) -> GatingResult:
        """Evaluate all gating conditions for a skill."""
        if fm.always:
            return GatingResult.ok("always=true bypasses gating")

        # Check bins
        for binary in fm.bins:
            if not self._find_executable(binary):
                return GatingResult.fail(
                    "bins", f"Required executable '{binary}' not found"
                )

        # Check env
        for env_var, expected in fm.env.items():
            actual = os.environ.get(env_var, "")
            if expected and actual != expected:
                return GatingResult.fail(
                    "env",
                    f"Environment variable '{env_var}' expected '{expected}', got '{actual}'",
                )
            if not expected and not actual:
                return GatingResult.fail(
                    "env", f"Environment variable '{env_var}' is not set"
                )

        # Check config (placeholder - config source injected at runtime)
        for key, expected in fm.config.items():
            actual = self._get_config(key)
            if actual != expected:
                return GatingResult.fail(
                    "config",
                    f"Config key '{key}' expected '{expected}', got '{actual}'",
                )

        # Check OS
        if fm.os:
            current_os = sys.platform
            if current_os not in fm.os:
                return GatingResult.fail(
                    "os",
                    f"Skill requires OS in {fm.os}, current is '{current_os}'",
                )

        return GatingResult.ok("All gating checks passed")

    def _find_executable(self, name: str) -> bool:
        """Check if an executable is available on PATH."""
        if sys.platform == "win32":
            name_with_ext = name if "." in name else f"{name}.exe"
        else:
            name_with_ext = name

        for path_dir in os.environ.get("PATH", "").split(os.pathsep):
            if (Path(path_dir) / name_with_ext).is_file():
                return True
        return False

    def _get_config(self, key: str) -> str:
        """Get configuration value. Override in subclass for real config."""
        return os.environ.get(f"NEUGI_CONFIG_{key}", "")

    def _hash_file(self, path: Path) -> str:
        """Compute simple hash of file content for change detection."""
        try:
            content = path.read_bytes()
            h = 0
            for byte in content:
                h = (h * 31 + byte) & 0xFFFFFFFF
            return hex(h)
        except OSError:
            return ""

    def _index_hashes(self) -> None:
        """Index hashes of all loaded skill files."""
        self._file_hashes.clear()
        for contract in self._loaded_contracts.values():
            if contract.path:
                self._file_hashes[contract.path] = self._hash_file(
                    Path(contract.path)
                )

    def _watch_loop(self, interval: float) -> None:
        """Background polling loop for hot reload."""
        import time
        while self._watching:
            try:
                changed = self.reload_changed()
                if changed and self._on_reload:
                    self._on_reload()
            except Exception:
                pass
            time.sleep(interval)
