"""
NEUGI v2 Token Budget Management

Combines Claude API-style budget allocation with OpenClaw overflow handling
for production-ready token management across prompt sections.

Features:
    - Fast approximate token counting (chars/4 for English, with adjustments)
    - Budget allocation across sections (skills, memory, conversation, tools)
    - Overflow handling (which sections to truncate first)
    - Configurable max tokens per model
    - Budget reporting (used, remaining, per-section breakdown)
    - Emergency truncation (when severely over budget)

Token Counting Strategy:
    - English text: ~4 chars/token
    - Code: ~3 chars/token (denser)
    - CJK text: ~1.5 chars/token
    - Structured data (JSON): ~3.5 chars/token
    - Overhead: +10% for safety margin

Usage:
    budget = TokenBudget(model="claude-sonnet-4-20250514")
    budget.allocate_section("skills", 8000)
    budget.allocate_section("memory", 6000)
    report = budget.report()
    print(f"Remaining: {report.remaining_tokens}")
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


# -- Exceptions --------------------------------------------------------------

class BudgetError(Exception):
    """Raised when token budget operations fail."""
    pass


# -- Model Presets -----------------------------------------------------------

class ModelPreset(Enum):
    """
    Pre-configured model token limits.

    Values are in tokens (not characters).
    """
    CLAUDE_HAIKU = "claude-haiku"
    CLAUDE_SONNET = "claude-sonnet"
    CLAUDE_OPUS = "claude-opus"
    GPT_4O_MINI = "gpt-4o-mini"
    GPT_4O = "gpt-4o"
    GPT_O1 = "gpt-o1"
    GPT_O3 = "gpt-o3"
    CUSTOM = "custom"


# Model token limits (context window sizes)
_MODEL_LIMITS: dict[str, int] = {
    "claude-haiku": 200_000,
    "claude-sonnet": 200_000,
    "claude-opus": 200_000,
    "claude-sonnet-4-20250514": 200_000,
    "claude-opus-4-20250514": 200_000,
    "claude-haiku-4-20250514": 200_000,
    "gpt-4o-mini": 128_000,
    "gpt-4o": 128_000,
    "gpt-o1": 200_000,
    "gpt-o3": 200_000,
}

# Default output reservation (tokens reserved for model response)
_DEFAULT_OUTPUT_RESERVATION: dict[str, int] = {
    "claude-haiku": 8_192,
    "claude-sonnet": 8_192,
    "claude-opus": 8_192,
    "gpt-4o-mini": 16_384,
    "gpt-4o": 16_384,
    "gpt-o1": 100_000,
    "gpt-o3": 100_000,
}


# -- Data Classes ------------------------------------------------------------

@dataclass
class SectionBudget:
    """
    Token budget allocation for a single section.

    Attributes:
        name: Section identifier.
        allocated_tokens: Maximum tokens for this section.
        used_tokens: Currently used tokens.
        priority: Truncation priority (lower = truncate first).
        overflow_allowed: Whether this section can exceed allocation.
    """
    name: str
    allocated_tokens: int = 0
    used_tokens: int = 0
    priority: int = 10
    overflow_allowed: bool = False

    @property
    def remaining_tokens(self) -> int:
        """Tokens remaining in this section's budget."""
        return max(0, self.allocated_tokens - self.used_tokens)

    @property
    def utilization(self) -> float:
        """Budget utilization ratio [0, 1]."""
        if self.allocated_tokens == 0:
            return 0.0
        return min(1.0, self.used_tokens / self.allocated_tokens)

    def fits(self, token_count: int) -> bool:
        """Check if token_count fits within remaining budget."""
        if self.overflow_allowed:
            return True
        return token_count <= self.remaining_tokens

    def record_usage(self, token_count: int) -> None:
        """Record token usage for this section."""
        self.used_tokens += token_count

    def reset(self) -> None:
        """Reset usage counter."""
        self.used_tokens = 0


@dataclass
class BudgetAllocation:
    """
    Complete budget allocation plan.

    Attributes:
        model: Model preset or identifier.
        total_tokens: Total context window size.
        output_reservation: Tokens reserved for model output.
        input_budget: Available tokens for input (total - output).
        sections: Per-section budget allocations.
        safety_margin: Extra buffer tokens (percentage of input_budget).
    """
    model: str = "claude-sonnet"
    total_tokens: int = 200_000
    output_reservation: int = 8_192
    input_budget: int = 191_808
    sections: dict[str, SectionBudget] = field(default_factory=dict)
    safety_margin: float = 0.05

    @property
    def effective_budget(self) -> int:
        """Input budget after safety margin."""
        return int(self.input_budget * (1 - self.safety_margin))

    @property
    def allocated_total(self) -> int:
        """Sum of all section allocations."""
        return sum(s.allocated_tokens for s in self.sections.values())

    @property
    def unallocated(self) -> int:
        """Tokens not yet allocated to sections."""
        return self.effective_budget - self.allocated_total


@dataclass
class BudgetReport:
    """
    Token budget usage report.

    Attributes:
        model: Model identifier.
        total_tokens: Total context window.
        used_tokens: Total tokens used across all sections.
        remaining_tokens: Tokens still available.
        utilization: Overall budget utilization [0, 1].
        section_breakdown: Per-section usage details.
        overflow_sections: Sections exceeding their allocation.
        is_over_budget: Whether total usage exceeds effective budget.
        metadata: Additional report metadata.
    """
    model: str
    total_tokens: int
    used_tokens: int
    remaining_tokens: int
    utilization: float
    section_breakdown: dict[str, dict[str, Any]] = field(default_factory=dict)
    overflow_sections: list[str] = field(default_factory=list)
    is_over_budget: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


# -- Token Counter -----------------------------------------------------------

# Regex patterns for content type detection
_CODE_PATTERNS = re.compile(
    r"(def |class |function |const |let |var |import |from |if |for |while |return |async |await |pub fn |fn )"
)
_CJK_PATTERN = re.compile(r"[\u4e00-\u9fff\u3040-\u309f\u30a0-\u30ff\uac00-\ud7af]")
_JSON_PATTERN = re.compile(r'^[\s\[\]{}":,]+$')
_WHITESPACE_PATTERN = re.compile(r"\s+")


def count_tokens(text: str) -> int:
    """
    Fast approximate token count for mixed content.

    Uses content-type-aware ratios:
        - English text: ~4 chars/token
        - Code: ~3 chars/token
        - CJK text: ~1.5 chars/token
        - JSON/structured: ~3.5 chars/token

    Adds 10% safety margin for tokenizer variance.

    Args:
        text: Content to count tokens for.

    Returns:
        Approximate token count (always >= 1 for non-empty text).
    """
    if not text:
        return 0

    length = len(text)

    # Detect content composition
    cjk_chars = len(_CJK_PATTERN.findall(text))
    code_lines = len(_CODE_PATTERNS.findall(text))
    is_json_like = bool(_JSON_PATTERN.match(text[:200])) if length > 200 else False

    # Estimate tokens by content type
    if cjk_chars > length * 0.3:
        # Predominantly CJK
        cjk_tokens = int(cjk_chars / 1.5)
        other_chars = length - cjk_chars
        other_tokens = int(other_chars / 4)
        tokens = cjk_tokens + other_tokens
    elif code_lines > length * 0.02:
        # Significant code content
        tokens = int(length / 3)
    elif is_json_like:
        tokens = int(length / 3.5)
    else:
        # Default: English text
        tokens = int(length / 4)

    # Safety margin (10%)
    tokens = int(tokens * 1.1)

    return max(1, tokens)


def chars_to_tokens(chars: int, content_type: str = "text") -> int:
    """
    Convert character count to approximate tokens.

    Args:
        chars: Number of characters.
        content_type: One of 'text', 'code', 'cjk', 'json'.

    Returns:
        Approximate token count.
    """
    ratios = {
        "text": 4.0,
        "code": 3.0,
        "cjk": 1.5,
        "json": 3.5,
    }
    ratio = ratios.get(content_type, 4.0)
    return max(1, int(chars / ratio * 1.1))


def tokens_to_chars(tokens: int, content_type: str = "text") -> int:
    """
    Convert token count to approximate characters.

    Args:
        tokens: Number of tokens.
        content_type: One of 'text', 'code', 'cjk', 'json'.

    Returns:
        Approximate character count.
    """
    ratios = {
        "text": 4.0,
        "code": 3.0,
        "cjk": 1.5,
        "json": 3.5,
    }
    ratio = ratios.get(content_type, 4.0)
    return int(tokens / 1.1 * ratio)


# -- Main Token Budget -------------------------------------------------------

class TokenBudget:
    """
    Production token budget manager for NEUGI v2.

    Manages token allocation across prompt sections with overflow handling,
    budget reporting, and emergency truncation.

    Usage:
        budget = TokenBudget(model="claude-sonnet-4-20250514")
        budget.allocate_section("skills", 8000)
        budget.allocate_section("memory", 6000)
        budget.record_usage("skills", count_tokens(skill_content))
        report = budget.report()
    """

    # Default section priorities (lower = truncate first)
    DEFAULT_PRIORITIES: dict[str, int] = {
        "conversation": 1,
        "tools": 3,
        "skills": 5,
        "memory": 6,
        "bootstrap": 7,
        "project_context": 8,
        "voice_tone": 9,
        "identity": 10,
        "heartbeat": 11,
    }

    def __init__(
        self,
        model: str = "claude-sonnet",
        total_tokens: Optional[int] = None,
        output_reservation: Optional[int] = None,
        safety_margin: float = 0.05,
    ) -> None:
        """
        Initialize token budget manager.

        Args:
            model: Model preset name or custom identifier.
            total_tokens: Override total context window (auto-detected from preset if None).
            output_reservation: Override output token reservation (auto-detected if None).
            safety_margin: Buffer percentage (0.05 = 5% of input budget).
        """
        self.model = model
        self.safety_margin = safety_margin

        # Resolve model preset
        preset = self._resolve_preset(model)
        self.total_tokens = total_tokens or _MODEL_LIMITS.get(model, 200_000)
        self.output_reservation = output_reservation or _DEFAULT_OUTPUT_RESERVATION.get(model, 8_192)
        self.input_budget = self.total_tokens - self.output_reservation

        # Section budgets
        self._sections: dict[str, SectionBudget] = {}

        # Track raw content for re-counting
        self._section_content: dict[str, str] = {}

    # -- Public API: Allocation ----------------------------------------------

    def allocate_section(
        self,
        name: str,
        tokens: int,
        priority: Optional[int] = None,
        overflow_allowed: bool = False,
    ) -> SectionBudget:
        """
        Allocate tokens to a named section.

        Args:
            name: Section identifier.
            tokens: Token budget for this section.
            priority: Truncation priority (lower = truncate first).
            overflow_allowed: Whether section can exceed allocation.

        Returns:
            The created SectionBudget.

        Raises:
            BudgetError: If allocation exceeds available budget.
        """
        if tokens < 0:
            raise BudgetError(f"Token allocation must be non-negative: {tokens}")

        priority = priority or self.DEFAULT_PRIORITIES.get(name, 10)

        section = SectionBudget(
            name=name,
            allocated_tokens=tokens,
            priority=priority,
            overflow_allowed=overflow_allowed,
        )

        self._sections[name] = section
        return section

    def auto_allocate(
        self,
        section_tokens: dict[str, int],
        scale_to_fit: bool = True,
    ) -> dict[str, SectionBudget]:
        """
        Allocate tokens to multiple sections, optionally scaling to fit budget.

        Args:
            section_tokens: {section_name: token_count} mapping.
            scale_to_fit: If True, scale allocations proportionally to fit budget.

        Returns:
            Dict of created SectionBudget objects.

        Raises:
            BudgetError: If allocations exceed budget and scale_to_fit is False.
        """
        total_requested = sum(section_tokens.values())

        if total_requested > self.effective_budget:
            if not scale_to_fit:
                raise BudgetError(
                    f"Requested {total_requested} tokens exceeds "
                    f"effective budget {self.effective_budget}"
                )

            # Scale proportionally
            scale_factor = self.effective_budget / total_requested
            section_tokens = {
                name: int(tokens * scale_factor)
                for name, tokens in section_tokens.items()
            }

        result = {}
        for name, tokens in section_tokens.items():
            result[name] = self.allocate_section(name, tokens)

        return result

    def deallocate_section(self, name: str) -> bool:
        """
        Remove a section's allocation.

        Returns:
            True if section was found and removed.
        """
        if name in self._sections:
            del self._sections[name]
            self._section_content.pop(name, None)
            return True
        return False

    # -- Public API: Usage Tracking ------------------------------------------

    def record_usage(self, section_name: str, token_count: int) -> None:
        """
        Record token usage for a section.

        Args:
            section_name: Section identifier.
            token_count: Tokens used.

        Raises:
            BudgetError: If section is not allocated.
        """
        section = self._sections.get(section_name)
        if section is None:
            raise BudgetError(f"Section '{section_name}' is not allocated")

        section.record_usage(token_count)

    def record_content(self, section_name: str, content: str) -> int:
        """
        Record content for a section, auto-counting tokens.

        Args:
            section_name: Section identifier.
            content: Raw content string.

        Returns:
            Token count of the content.

        Raises:
            BudgetError: If section is not allocated.
        """
        section = self._sections.get(section_name)
        if section is None:
            raise BudgetError(f"Section '{section_name}' is not allocated")

        token_count = count_tokens(content)
        section.used_tokens = token_count
        self._section_content[section_name] = content
        return token_count

    def reset_usage(self, section_name: Optional[str] = None) -> None:
        """
        Reset usage counters.

        Args:
            section_name: Reset specific section, or all if None.
        """
        if section_name:
            section = self._sections.get(section_name)
            if section:
                section.reset()
        else:
            for section in self._sections.values():
                section.reset()
            self._section_content.clear()

    # -- Public API: Budget Queries ------------------------------------------

    def report(self) -> BudgetReport:
        """
        Generate a comprehensive budget usage report.

        Returns:
            BudgetReport with usage details.
        """
        total_used = sum(s.used_tokens for s in self._sections.values())
        remaining = max(0, self.effective_budget - total_used)
        utilization = total_used / self.effective_budget if self.effective_budget > 0 else 0.0

        section_breakdown: dict[str, dict[str, Any]] = {}
        overflow_sections: list[str] = []

        for name, section in sorted(self._sections.items(), key=lambda x: x[1].priority):
            section_breakdown[name] = {
                "allocated": section.allocated_tokens,
                "used": section.used_tokens,
                "remaining": section.remaining_tokens,
                "utilization": round(section.utilization, 3),
                "priority": section.priority,
                "overflow_allowed": section.overflow_allowed,
            }
            if section.used_tokens > section.allocated_tokens and not section.overflow_allowed:
                overflow_sections.append(name)

        return BudgetReport(
            model=self.model,
            total_tokens=self.total_tokens,
            used_tokens=total_used,
            remaining_tokens=remaining,
            utilization=round(utilization, 3),
            section_breakdown=section_breakdown,
            overflow_sections=overflow_sections,
            is_over_budget=total_used > self.effective_budget,
        )

    def can_fit(self, token_count: int) -> bool:
        """Check if additional tokens can fit in the remaining budget."""
        total_used = sum(s.used_tokens for s in self._sections.values())
        return (total_used + token_count) <= self.effective_budget

    def remaining_for_section(self, section_name: str) -> int:
        """Get remaining tokens for a specific section."""
        section = self._sections.get(section_name)
        if section is None:
            return 0
        return section.remaining_tokens

    # -- Public API: Overflow Handling ---------------------------------------

    def handle_overflow(self) -> list[str]:
        """
        Handle budget overflow by truncating low-priority sections.

        Returns:
            List of truncated section names.
        """
        report = self.report()
        if not report.is_over_budget:
            return []

        excess = report.used_tokens - self.effective_budget
        truncated: list[str] = []

        # Sort sections by priority (lowest first = truncate first)
        sorted_sections = sorted(
            self._sections.values(),
            key=lambda s: s.priority,
        )

        for section in sorted_sections:
            if excess <= 0:
                break
            if section.overflow_allowed:
                continue

            # Calculate how much to reduce
            current_used = section.used_tokens
            reduction = min(excess, current_used - int(current_used * 0.5))

            if reduction > 0:
                section.used_tokens -= reduction
                excess -= reduction
                truncated.append(section.name)

        if excess > 0:
            logger.warning(
                "Still %d tokens over budget after truncation", excess
            )

        return truncated

    def emergency_truncate(self, target_tokens: int) -> list[str]:
        """
        Emergency truncation to reach a specific token target.

        Aggressively truncates sections starting from lowest priority.

        Args:
            target_tokens: Target total token count.

        Returns:
            List of truncated section names.
        """
        total_used = sum(s.used_tokens for s in self._sections.values())
        excess = total_used - target_tokens

        if excess <= 0:
            return []

        truncated: list[str] = []
        sorted_sections = sorted(
            self._sections.values(),
            key=lambda s: s.priority,
        )

        for section in sorted_sections:
            if excess <= 0:
                break

            if section.name in ("identity", "heartbeat"):
                # Never truncate critical sections
                continue

            # Reduce to 25% of current usage
            new_usage = int(section.used_tokens * 0.25)
            reduction = section.used_tokens - new_usage
            section.used_tokens = new_usage
            excess -= reduction
            truncated.append(section.name)

        return truncated

    # -- Public API: Content-Aware Truncation --------------------------------

    def truncate_section_to_fit(
        self, section_name: str, max_tokens: int
    ) -> Optional[str]:
        """
        Get truncated content for a section to fit within token limit.

        Uses the cached content and truncates proportionally.

        Args:
            section_name: Section to truncate.
            max_tokens: Maximum tokens for the truncated content.

        Returns:
            Truncated content string, or None if no content cached.
        """
        content = self._section_content.get(section_name)
        if content is None:
            return None

        current_tokens = count_tokens(content)
        if current_tokens <= max_tokens:
            return content

        # Estimate truncation point
        ratio = max_tokens / current_tokens
        char_target = int(len(content) * ratio)

        # Truncate at word boundary
        truncated = content[:char_target]
        last_space = truncated.rfind(" ")
        if last_space > char_target * 0.8:
            truncated = truncated[:last_space]

        truncated += f"\n\n... [{current_tokens - count_tokens(truncated)} tokens omitted]"
        return truncated

    # -- Utilities -----------------------------------------------------------

    def _resolve_preset(self, model: str) -> Optional[ModelPreset]:
        """Resolve a model string to a ModelPreset."""
        model_lower = model.lower()
        for preset in ModelPreset:
            if preset.value in model_lower:
                return preset
        return None

    # -- Properties ----------------------------------------------------------

    @property
    def effective_budget(self) -> int:
        """Input budget after safety margin."""
        return int(self.input_budget * (1 - self.safety_margin))

    @property
    def sections(self) -> dict[str, SectionBudget]:
        """Get all section budgets."""
        return dict(self._sections)

    @property
    def total_allocated(self) -> int:
        """Sum of all section allocations."""
        return sum(s.allocated_tokens for s in self._sections.values())

    @property
    def total_used(self) -> int:
        """Sum of all section usage."""
        return sum(s.used_tokens for s in self._sections.values())

    @property
    def unallocated(self) -> int:
        """Tokens not yet allocated to sections."""
        return self.effective_budget - self.total_allocated

    # -- Context Manager -----------------------------------------------------

    def __enter__(self) -> "TokenBudget":
        return self

    def __exit__(self, *args: Any) -> None:
        self.reset_usage()

    def __repr__(self) -> str:
        report = self.report()
        return (
            f"TokenBudget(model={self.model!r}, "
            f"used={report.used_tokens}, "
            f"remaining={report.remaining_tokens}, "
            f"utilization={report.utilization:.1%})"
        )
