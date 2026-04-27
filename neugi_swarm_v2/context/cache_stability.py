"""
NEUGI v2 KV Cache Stability Optimization

Implements prompt fingerprinting, normalization, cache hit detection,
and prompt diffing to maximize KV cache hit rates across conversation turns.

Based on patterns from:
- Anthropic prompt caching (stable prefixes, deterministic ordering)
- vLLM cache-aware scheduling (prefix matching, fingerprint comparison)
- OpenClaw cache optimization (normalized prompts, stable assembly)

Features:
    - Prompt fingerprinting (SHA-256 of normalized prompt)
    - Normalization rules (strip whitespace, canonical tool definitions)
    - Cache hit detection (prefix matching, fingerprint comparison)
    - Stable prompt ordering (deterministic assembly)
    - Cache-aware compaction (preserve cache-friendly prefixes)
    - Prompt diffing (what changed between turns)

Cache Strategy:
    - First ~1000 tokens are most valuable for caching (system prompt)
    - Keep identity, skills, and tools stable across turns
    - Only vary conversation history and recent context
    - Normalize model aliases to canonical names

Usage:
    cache = CacheStability()
    fp1 = cache.fingerprint(system_prompt)
    fp2 = cache.fingerprint(next_turn_prompt)
    diff = cache.diff(fp1, fp2)
    if cache.is_hit(fp1, fp2):
        print("Cache hit! Reusing KV cache.")
"""

from __future__ import annotations

import hashlib
import logging
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


# -- Exceptions --------------------------------------------------------------

class CacheError(Exception):
    """Raised when cache operations fail."""
    pass


# -- Data Classes ------------------------------------------------------------

@dataclass
class PromptFingerprint:
    """
    Fingerprint of a normalized prompt for cache comparison.

    Attributes:
        full_hash: SHA-256 of the full normalized prompt.
        prefix_hash: SHA-256 of the first 1000 chars (cache-critical prefix).
        length: Length of the normalized prompt.
        normalized_prompt: The normalized prompt text.
        created_at: Timestamp when fingerprint was created.
        metadata: Additional fingerprint metadata.
    """
    full_hash: str
    prefix_hash: str
    length: int
    normalized_prompt: str = ""
    created_at: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.created_at == 0.0:
            self.created_at = time.time()


@dataclass
class PromptDiff:
    """
    Diff between two prompt fingerprints.

    Attributes:
        is_identical: Whether the prompts are identical.
        prefix_match: Whether the cache-critical prefix matches.
        added_chars: Number of characters added.
        removed_chars: Number of characters removed.
        changed_sections: Names of sections that changed.
        change_summary: Human-readable summary of changes.
    """
    is_identical: bool = False
    prefix_match: bool = False
    added_chars: int = 0
    removed_chars: int = 0
    changed_sections: list[str] = field(default_factory=list)
    change_summary: str = ""

    @property
    def is_cache_hit(self) -> bool:
        """Whether this diff would result in a cache hit."""
        return self.prefix_match

    @property
    def change_magnitude(self) -> str:
        """Categorize the magnitude of change."""
        if self.is_identical:
            return "none"
        total_change = self.added_chars + self.removed_chars
        if total_change < 50:
            return "minimal"
        elif total_change < 500:
            return "small"
        elif total_change < 2000:
            return "moderate"
        else:
            return "large"


@dataclass
class CacheStats:
    """
    Cache performance statistics.

    Attributes:
        total_checks: Total cache hit checks performed.
        hits: Number of cache hits.
        misses: Number of cache misses.
        hit_rate: Cache hit rate (hits / total_checks).
        total_fingerprints: Number of unique fingerprints stored.
        oldest_entry_age: Age of oldest cached entry in seconds.
        metadata: Additional statistics.
    """
    total_checks: int = 0
    hits: int = 0
    misses: int = 0
    total_fingerprints: int = 0
    oldest_entry_age: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def hit_rate(self) -> float:
        """Cache hit rate [0, 1]."""
        if self.total_checks == 0:
            return 0.0
        return self.hits / self.total_checks


# -- Normalization -----------------------------------------------------------

# Patterns for prompt normalization
_MODEL_ALIAS_PATTERN = re.compile(
    r"(claude-)?(sonnet|haiku|opus|gpt-4o|gpt-o[13])(-4)?-?(\d{8})?",
    re.IGNORECASE,
)
_TIMESTAMP_PATTERN = re.compile(
    r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})?"
)
_EPOCH_PATTERN = re.compile(r"\b\d{10,13}\b")
_MULTI_WHITESPACE = re.compile(r"\n{3,}")
_TRAILING_WHITESPACE = re.compile(r"[ \t]+$", re.MULTILINE)
_LEADING_WHITESPACE = re.compile(r"^[ \t]+", re.MULTILINE)

# Canonical model name mapping
_CANONICAL_MODELS: dict[str, str] = {
    "sonnet": "claude-sonnet",
    "haiku": "claude-haiku",
    "opus": "claude-opus",
    "gpt-4o": "gpt-4o",
    "gpt-o1": "gpt-o1",
    "gpt-o3": "gpt-o3",
}


def normalize_prompt(
    prompt: str,
    normalize_timestamps: bool = True,
    normalize_model_aliases: bool = True,
    normalize_whitespace: bool = True,
    preserve_structure: bool = True,
) -> str:
    """
    Normalize a prompt for stable fingerprinting.

    Normalization removes volatile content (timestamps, model aliases)
    while preserving structural elements for cache prefix matching.

    Args:
        prompt: Raw prompt text.
        normalize_timestamps: Replace timestamps with canonical placeholder.
        normalize_model_aliases: Replace model aliases with canonical names.
        normalize_whitespace: Collapse excessive whitespace.
        preserve_structure: Keep section headers and markdown structure.

    Returns:
        Normalized prompt string.
    """
    result = prompt

    if normalize_timestamps:
        # Replace ISO timestamps
        result = _TIMESTAMP_PATTERN.sub("<TIMESTAMP>", result)
        # Replace epoch timestamps
        result = _EPOCH_PATTERN.sub("<EPOCH>", result)

    if normalize_model_aliases:
        # Replace model aliases with canonical names
        def _replace_model(match: re.Match) -> str:
            base = match.group(2).lower()
            return _CANONICAL_MODELS.get(base, match.group(0))

        result = _MODEL_ALIAS_PATTERN.sub(_replace_model, result)

    if normalize_whitespace:
        # Collapse multiple newlines
        result = _MULTI_WHITESPACE.sub("\n\n", result)
        # Strip trailing whitespace per line
        result = _TRAILING_WHITESPACE.sub("", result)
        if not preserve_structure:
            # Strip leading whitespace per line
            result = _LEADING_WHITESPACE.sub("", result)

    # Ensure consistent line ending
    result = result.replace("\r\n", "\n")

    # Strip leading/trailing whitespace of entire prompt
    result = result.strip()

    return result


# -- Main Cache Stability Manager --------------------------------------------

class CacheStability:
    """
    KV cache stability optimizer for NEUGI v2.

    Manages prompt fingerprinting, cache hit detection, and prompt diffing
    to maximize KV cache reuse across conversation turns.

    Usage:
        cache = CacheStability(prefix_length=1000)
        fp = cache.fingerprint(system_prompt)
        # Next turn:
        fp2 = cache.fingerprint(next_prompt)
        if cache.is_hit(fp, fp2):
            print("Cache hit!")
        diff = cache.diff_between(fp, fp2)
    """

    # Default prefix length for cache-critical region
    DEFAULT_PREFIX_LENGTH = 1000

    def __init__(
        self,
        prefix_length: int = DEFAULT_PREFIX_LENGTH,
        max_history: int = 50,
        enable_normalization: bool = True,
    ) -> None:
        """
        Initialize cache stability manager.

        Args:
            prefix_length: Length of cache-critical prefix for matching.
            max_history: Maximum number of fingerprints to retain.
            enable_normalization: Whether to normalize prompts before fingerprinting.
        """
        self.prefix_length = prefix_length
        self.max_history = max_history
        self.enable_normalization = enable_normalization

        # Fingerprint history
        self._history: list[PromptFingerprint] = []
        self._fingerprint_map: dict[str, PromptFingerprint] = {}

        # Cache stats
        self._stats = CacheStats()

    # -- Public API: Fingerprinting ------------------------------------------

    def fingerprint(self, prompt: str, metadata: Optional[dict[str, Any]] = None) -> PromptFingerprint:
        """
        Create a fingerprint of a prompt for cache comparison.

        Args:
            prompt: Raw prompt text.
            metadata: Optional metadata to attach to the fingerprint.

        Returns:
            PromptFingerprint with full and prefix hashes.
        """
        normalized = self._normalize(prompt) if self.enable_normalization else prompt

        full_hash = hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]

        prefix = normalized[:self.prefix_length]
        prefix_hash = hashlib.sha256(prefix.encode("utf-8")).hexdigest()[:16]

        fp = PromptFingerprint(
            full_hash=full_hash,
            prefix_hash=prefix_hash,
            length=len(normalized),
            normalized_prompt=normalized,
            metadata=metadata or {},
        )

        # Store in history
        self._add_to_history(fp)
        self._fingerprint_map[full_hash] = fp

        return fp

    def fingerprint_sections(
        self,
        sections: dict[str, str],
        metadata: Optional[dict[str, Any]] = None,
    ) -> PromptFingerprint:
        """
        Create a fingerprint from multiple named sections.

        Sections are concatenated in sorted order for determinism.

        Args:
            sections: {section_name: content} mapping.
            metadata: Optional metadata.

        Returns:
            Combined PromptFingerprint.
        """
        # Sort sections by name for deterministic ordering
        parts = []
        for name in sorted(sections.keys()):
            content = sections[name]
            parts.append(f"## {name}\n\n{content}")

        combined = "\n\n---\n\n".join(parts)
        return self.fingerprint(combined, metadata=metadata)

    # -- Public API: Cache Hit Detection -------------------------------------

    def is_hit(self, current: PromptFingerprint, previous: PromptFingerprint) -> bool:
        """
        Check if two fingerprints would result in a cache hit.

        A cache hit occurs when the cache-critical prefixes match.

        Args:
            current: Current turn's fingerprint.
            previous: Previous turn's fingerprint.

        Returns:
            True if cache would be reused.
        """
        self._stats.total_checks += 1

        if current.prefix_hash == previous.prefix_hash:
            self._stats.hits += 1
            return True

        self._stats.misses += 1
        return False

    def check_against_history(self, prompt: str) -> tuple[bool, Optional[PromptFingerprint]]:
        """
        Check if a prompt would hit against any cached fingerprint.

        Args:
            prompt: Prompt to check.

        Returns:
            (is_hit, matching_fingerprint) tuple.
        """
        fp = self.fingerprint(prompt)

        for prev in reversed(self._history):
            if self.is_hit(fp, prev):
                return True, prev

        return False, None

    def find_best_prefix_match(self, prompt: str) -> tuple[float, Optional[PromptFingerprint]]:
        """
        Find the best prefix match in history.

        Returns the longest matching prefix length and the matching fingerprint.

        Args:
            prompt: Prompt to match against.

        Returns:
            (match_length, matching_fingerprint) tuple.
        """
        normalized = self._normalize(prompt) if self.enable_normalization else prompt

        best_length = 0
        best_match: Optional[PromptFingerprint] = None

        for prev in self._history:
            # Find common prefix length
            match_len = 0
            for i, (c1, c2) in enumerate(zip(normalized, prev.normalized_prompt)):
                if c1 != c2:
                    break
                match_len = i + 1

            if match_len > best_length:
                best_length = match_len
                best_match = prev

        return best_length, best_match

    # -- Public API: Prompt Diffing ------------------------------------------

    def diff_between(
        self,
        current: PromptFingerprint,
        previous: PromptFingerprint,
    ) -> PromptDiff:
        """
        Compute the diff between two fingerprints.

        Args:
            current: Current fingerprint.
            previous: Previous fingerprint.

        Returns:
            PromptDiff with change details.
        """
        if current.full_hash == previous.full_hash:
            return PromptDiff(
                is_identical=True,
                prefix_match=True,
                change_summary="No changes",
            )

        prefix_match = current.prefix_hash == previous.prefix_hash

        # Estimate added/removed characters
        len_diff = current.length - previous.length
        if len_diff > 0:
            added = len_diff
            removed = 0
        else:
            added = 0
            removed = abs(len_diff)

        # Detect changed sections
        changed_sections = self._detect_changed_sections(
            current.normalized_prompt,
            previous.normalized_prompt,
        )

        # Build summary
        summary_parts = []
        if not prefix_match:
            summary_parts.append("prefix changed")
        if added > 0:
            summary_parts.append(f"+{added} chars")
        if removed > 0:
            summary_parts.append(f"-{removed} chars")
        if changed_sections:
            summary_parts.append(f"sections: {', '.join(changed_sections)}")

        return PromptDiff(
            is_identical=False,
            prefix_match=prefix_match,
            added_chars=added,
            removed_chars=removed,
            changed_sections=changed_sections,
            change_summary="; ".join(summary_parts) if summary_parts else "unknown",
        )

    def diff_text(
        self,
        current_prompt: str,
        previous_prompt: str,
    ) -> PromptDiff:
        """
        Compute diff between two raw prompts.

        Convenience method that fingerprints both prompts first.

        Args:
            current_prompt: Current prompt text.
            previous_prompt: Previous prompt text.

        Returns:
            PromptDiff with change details.
        """
        current_fp = self.fingerprint(current_prompt)
        previous_fp = self.fingerprint(previous_prompt)
        return self.diff_between(current_fp, previous_fp)

    # -- Public API: Cache-Aware Compaction ----------------------------------

    def compact_aware(
        self,
        sections: dict[str, str],
        max_chars: int,
        preserve_order: Optional[list[str]] = None,
    ) -> dict[str, str]:
        """
        Compact sections while preserving cache-friendly prefixes.

        Higher-priority sections (earlier in preserve_order) are kept intact,
        while lower-priority sections are truncated.

        Args:
            sections: {section_name: content} mapping.
            max_chars: Maximum total characters.
            preserve_order: Section names in priority order (first = highest priority).

        Returns:
            Compacted sections dict.
        """
        if preserve_order is None:
            preserve_order = list(sections.keys())

        total_chars = sum(len(v) for v in sections.values())
        if total_chars <= max_chars:
            return dict(sections)

        result: dict[str, str] = {}
        remaining_budget = max_chars

        # First pass: allocate to high-priority sections
        for name in preserve_order:
            if name not in sections:
                continue
            content = sections[name]
            if len(content) <= remaining_budget:
                result[name] = content
                remaining_budget -= len(content)
            else:
                # Truncate this section
                result[name] = content[:remaining_budget - 100]
                result[name] += f"\n\n... [{len(content) - remaining_budget + 100} chars omitted]"
                remaining_budget = 0
                break

        # Add remaining sections that weren't in preserve_order
        for name, content in sections.items():
            if name not in result and remaining_budget > 100:
                available = min(len(content), remaining_budget - 100)
                result[name] = content[:available]
                remaining_budget -= len(result[name])

        return result

    # -- Public API: Statistics ----------------------------------------------

    @property
    def stats(self) -> CacheStats:
        """Get cache performance statistics."""
        self._stats.total_fingerprints = len(self._fingerprint_map)
        if self._history:
            oldest = self._history[0].created_at
            self._stats.oldest_entry_age = time.time() - oldest
        return self._stats

    def reset_stats(self) -> None:
        """Reset cache statistics."""
        self._stats = CacheStats()

    def clear_history(self) -> None:
        """Clear fingerprint history."""
        self._history.clear()
        self._fingerprint_map.clear()

    # -- Internal Methods ----------------------------------------------------

    def _normalize(self, prompt: str) -> str:
        """Normalize a prompt for fingerprinting."""
        return normalize_prompt(prompt)

    def _add_to_history(self, fp: PromptFingerprint) -> None:
        """Add a fingerprint to history, respecting max_history limit."""
        self._history.append(fp)

        # Trim history
        if len(self._history) > self.max_history:
            removed = self._history[:len(self._history) - self.max_history]
            self._history = self._history[-self.max_history:]

            # Remove from map if no longer in history
            for old_fp in removed:
                if old_fp.full_hash in self._fingerprint_map:
                    # Check if it's still referenced
                    if not any(f.full_hash == old_fp.full_hash for f in self._history):
                        del self._fingerprint_map[old_fp.full_hash]

    def _detect_changed_sections(
        self,
        current: str,
        previous: str,
    ) -> list[str]:
        """
        Detect which sections changed between two prompts.

        Uses markdown section headers to identify sections.
        """
        section_pattern = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)

        current_sections = {m.group(2).strip() for m in section_pattern.finditer(current)}
        previous_sections = {m.group(2).strip() for m in section_pattern.finditer(previous)}

        # Sections that exist in both but may have different content
        common = current_sections & previous_sections
        changed = []

        for section_name in sorted(common):
            # Extract section content from both prompts
            current_content = self._extract_section(current, section_name)
            previous_content = self._extract_section(previous, section_name)

            if current_content != previous_content:
                changed.append(section_name)

        # Sections added or removed
        added = current_sections - previous_sections
        removed = previous_sections - current_sections

        for name in sorted(added):
            changed.append(f"+{name}")
        for name in sorted(removed):
            changed.append(f"-{name}")

        return changed

    def _extract_section(self, prompt: str, section_name: str) -> str:
        """Extract content of a named section from a prompt."""
        # Escape special regex chars in section name
        escaped = re.escape(section_name)
        pattern = re.compile(
            rf"^{{1,3}}\s+{escaped}\s*\n(.*?)(?=^{{1,3}}\s+|\Z)",
            re.MULTILINE | re.DOTALL,
        )
        match = pattern.search(prompt)
        if match:
            return match.group(1).strip()
        return ""

    # -- Context Manager -----------------------------------------------------

    def __enter__(self) -> "CacheStability":
        return self

    def __exit__(self, *args: Any) -> None:
        self.clear_history()

    def __repr__(self) -> str:
        stats = self.stats
        return (
            f"CacheStability(prefix_length={self.prefix_length}, "
            f"history={len(self._history)}, "
            f"hit_rate={stats.hit_rate:.1%})"
        )
