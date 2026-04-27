"""
NEUGI v2 Context Injection Engine

Relevance-based context injection before each task with scoped retrieval,
prioritization, dynamic swapping, and freshness tracking.

Combines patterns from:
- RAG systems (relevance scoring, top-k retrieval)
- LangGraph (state-aware context injection)
- OpenClaw (memory-based context, scoped retrieval)

Features:
    - Relevance-based context injection before each task
    - Scoped context retrieval (from memory system)
    - Context prioritization (most relevant first)
    - Context window filling strategy
    - Dynamic context swapping (replace less relevant with more relevant)
    - Context freshness tracking (how old is each injected piece)

Injection Strategy:
    1. Score all candidate context items by relevance to task
    2. Sort by score (highest first)
    3. Fill context window until budget is reached
    4. Track freshness of each injected item
    5. On next turn, swap out stale/less relevant items

Usage:
    injector = ContextInjector(max_context_chars=10000)
    injector.register_context("user_prefs", "User prefers dark mode", tags=["preference"])
    injector.register_context("project_info", "Building a chat app", tags=["project"])
    result = injector.inject("Implement dark mode toggle")
    print(result.injected_context)
    print(result.items_used)
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# -- Exceptions --------------------------------------------------------------

class InjectionError(Exception):
    """Raised when context injection fails."""
    pass


# -- Enums -------------------------------------------------------------------

class ContextScope(Enum):
    """
    Scope levels for context items.

    Determines visibility and priority during injection.
    """
    GLOBAL = "global"
    USER = "user"
    AGENT = "agent"
    TASK = "task"
    SESSION = "session"


# -- Data Classes ------------------------------------------------------------

@dataclass
class ContextItem:
    """
    A single piece of injectable context.

    Attributes:
        id: Unique identifier.
        key: Short identifier for this context.
        content: The actual context text.
        scope: Visibility scope.
        tags: Categorization labels.
        relevance_score: Pre-computed relevance [0, 1] (updated on injection).
        created_at: When this context was registered.
        last_accessed: When this context was last injected.
        access_count: How many times this context has been injected.
        ttl_seconds: Time-to-live (None = permanent).
        metadata: Arbitrary key-value store.
    """
    id: str
    key: str
    content: str
    scope: ContextScope = ContextScope.GLOBAL
    tags: list[str] = field(default_factory=list)
    relevance_score: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: Optional[datetime] = None
    access_count: int = 0
    ttl_seconds: Optional[int] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def age_seconds(self) -> float:
        """Age of this context in seconds."""
        return (datetime.now(timezone.utc) - self.created_at).total_seconds()

    @property
    def is_expired(self) -> bool:
        """Check if this context has expired."""
        if self.ttl_seconds is None:
            return False
        return self.age_seconds > self.ttl_seconds

    @property
    def freshness(self) -> float:
        """
        Freshness score [0, 1].

        1.0 = just created, 0.0 = expired or very old.
        """
        if self.ttl_seconds is None:
            return 1.0
        remaining = max(0, self.ttl_seconds - self.age_seconds)
        return remaining / self.ttl_seconds

    def touch(self) -> None:
        """Record an access."""
        self.last_accessed = datetime.now(timezone.utc)
        self.access_count += 1

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dict."""
        return {
            "id": self.id,
            "key": self.key,
            "content": self.content,
            "scope": self.scope.value,
            "tags": self.tags,
            "relevance_score": self.relevance_score,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat() if self.last_accessed else None,
            "access_count": self.access_count,
            "ttl_seconds": self.ttl_seconds,
            "freshness": round(self.freshness, 3),
            "is_expired": self.is_expired,
            "metadata": self.metadata,
        }


@dataclass
class InjectionResult:
    """
    Result of a context injection operation.

    Attributes:
        injected_context: The assembled context string.
        items_used: List of context items that were injected.
        items_skipped: List of items that were not injected (budget/irrelevant).
        total_items_available: Total items considered.
        char_count: Character count of injected context.
        injection_time_ms: Time taken to inject.
        freshness_summary: Average freshness of injected items.
        warnings: Any warnings during injection.
    """
    injected_context: str
    items_used: list[ContextItem] = field(default_factory=list)
    items_skipped: list[ContextItem] = field(default_factory=list)
    total_items_available: int = 0
    char_count: int = 0
    injection_time_ms: float = 0.0
    freshness_summary: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        if self.char_count == 0:
            self.char_count = len(self.injected_context)
        if self.items_used:
            avg_freshness = sum(item.freshness for item in self.items_used) / len(self.items_used)
            self.freshness_summary = {
                "avg_freshness": round(avg_freshness, 3),
                "min_freshness": round(min(item.freshness for item in self.items_used), 3),
                "max_freshness": round(max(item.freshness for item in self.items_used), 3),
                "item_count": len(self.items_used),
            }


# -- Relevance Scoring -------------------------------------------------------

def compute_relevance(
    query: str,
    content: str,
    tags: Optional[list[str]] = None,
    tag_weights: Optional[dict[str, float]] = None,
    freshness_bonus: float = 0.1,
    access_bonus: float = 0.05,
) -> float:
    """
    Compute relevance score between a query and context content.

    Uses keyword overlap, tag matching, and recency bonuses.

    Args:
        query: Task/query text.
        content: Context item content.
        tags: Context item tags.
        tag_weights: Per-tag weight multipliers.
        freshness_bonus: Max bonus for fresh content.
        access_bonus: Bonus per previous access (capped).

    Returns:
        Relevance score [0, 1].
    """
    if not query or not content:
        return 0.0

    query_lower = query.lower()
    content_lower = content.lower()

    # Tokenize query into meaningful terms
    query_terms = set(re.findall(r"\b\w{3,}\b", query_lower))
    if not query_terms:
        return 0.0

    # Keyword overlap score
    content_terms = set(re.findall(r"\b\w{3,}\b", content_lower))
    overlap = query_terms & content_terms
    keyword_score = len(overlap) / len(query_terms) if query_terms else 0.0

    # Tag matching score
    tag_score = 0.0
    if tags:
        tag_weights = tag_weights or {}
        matched_tags = 0
        total_weight = 0.0
        for tag in tags:
            tag_lower = tag.lower()
            if tag_lower in query_lower:
                weight = tag_weights.get(tag, 1.0)
                matched_tags += weight
                total_weight += weight
            else:
                total_weight += tag_weights.get(tag, 1.0)
        if total_weight > 0:
            tag_score = matched_tags / total_weight

    # Combined score (70% keyword, 30% tag)
    base_score = 0.7 * keyword_score + 0.3 * tag_score

    # Clamp to [0, 1]
    return min(1.0, max(0.0, base_score))


# -- Main Context Injector ---------------------------------------------------

class ContextInjector:
    """
    Relevance-based context injection engine for NEUGI v2.

    Manages context items, scores them against tasks, and injects the most
    relevant context within budget constraints.

    Usage:
        injector = ContextInjector(max_context_chars=10000)
        injector.register("user_prefs", "User prefers dark mode", tags=["preference", "ui"])
        result = injector.inject("Implement dark mode toggle")
        print(result.injected_context)
    """

    # Scope priority (higher = more likely to be included)
    SCOPE_PRIORITY: dict[ContextScope, int] = {
        ContextScope.TASK: 5,
        ContextScope.SESSION: 4,
        ContextScope.AGENT: 3,
        ContextScope.USER: 2,
        ContextScope.GLOBAL: 1,
    }

    def __init__(
        self,
        max_context_chars: int = 10000,
        max_items: int = 20,
        min_relevance: float = 0.1,
        tag_weights: Optional[dict[str, float]] = None,
        freshness_bonus: float = 0.1,
        access_bonus: float = 0.05,
        custom_scorer: Optional[Callable[[str, str, list[str]], float]] = None,
    ) -> None:
        """
        Initialize context injector.

        Args:
            max_context_chars: Maximum characters for injected context.
            max_items: Maximum number of items to inject.
            min_relevance: Minimum relevance score for inclusion.
            tag_weights: Per-tag weight multipliers for scoring.
            freshness_bonus: Max bonus for fresh content.
            access_bonus: Bonus per previous access (capped at 0.2).
            custom_scorer: Custom relevance scorer function.
                Signature: (query, content, tags) -> score
        """
        self.max_context_chars = max_context_chars
        self.max_items = max_items
        self.min_relevance = min_relevance
        self.tag_weights = tag_weights or {}
        self.freshness_bonus = freshness_bonus
        self.access_bonus = access_bonus
        self.custom_scorer = custom_scorer

        # Context store
        self._items: dict[str, ContextItem] = {}
        self._id_counter = 0

        # Injection history
        self._last_result: Optional[InjectionResult] = None
        self._injection_count = 0

    # -- Public API: Registration --------------------------------------------

    def register(
        self,
        key: str,
        content: str,
        scope: ContextScope = ContextScope.GLOBAL,
        tags: Optional[list[str]] = None,
        ttl_seconds: Optional[int] = None,
        metadata: Optional[dict[str, Any]] = None,
    ) -> ContextItem:
        """
        Register a new context item.

        Args:
            key: Short identifier for this context.
            content: The context text.
            scope: Visibility scope.
            tags: Categorization labels.
            ttl_seconds: Time-to-live (None = permanent).
            metadata: Arbitrary key-value store.

        Returns:
            The registered ContextItem.

        Raises:
            InjectionError: If key is empty or content is blank.
        """
        if not key.strip():
            raise InjectionError("Context key cannot be empty")
        if not content.strip():
            raise InjectionError("Context content cannot be blank")

        self._id_counter += 1
        item = ContextItem(
            id=f"ctx_{self._id_counter:06d}",
            key=key,
            content=content,
            scope=scope,
            tags=tags or [],
            ttl_seconds=ttl_seconds,
            metadata=metadata or {},
        )

        self._items[key] = item
        return item

    def register_batch(
        self,
        items: list[dict[str, Any]],
    ) -> list[ContextItem]:
        """
        Register multiple context items at once.

        Args:
            items: List of dicts with keys matching register() args.

        Returns:
            List of registered ContextItems.
        """
        results = []
        for item_data in items:
            item = self.register(
                key=item_data["key"],
                content=item_data["content"],
                scope=item_data.get("scope", ContextScope.GLOBAL),
                tags=item_data.get("tags"),
                ttl_seconds=item_data.get("ttl_seconds"),
                metadata=item_data.get("metadata"),
            )
            results.append(item)
        return results

    def unregister(self, key: str) -> bool:
        """
        Remove a context item.

        Returns:
            True if item was found and removed.
        """
        if key in self._items:
            del self._items[key]
            return True
        return False

    def update(self, key: str, content: Optional[str] = None, tags: Optional[list[str]] = None) -> Optional[ContextItem]:
        """
        Update an existing context item.

        Args:
            key: Item identifier.
            content: New content (None to keep existing).
            tags: New tags (None to keep existing).

        Returns:
            Updated ContextItem, or None if not found.
        """
        item = self._items.get(key)
        if item is None:
            return None

        if content is not None:
            item.content = content
        if tags is not None:
            item.tags = tags

        return item

    # -- Public API: Injection -----------------------------------------------

    def inject(
        self,
        query: str,
        scope_filter: Optional[ContextScope] = None,
        tag_filter: Optional[list[str]] = None,
        exclude_keys: Optional[set[str]] = None,
        max_chars: Optional[int] = None,
    ) -> InjectionResult:
        """
        Inject the most relevant context for a task/query.

        Args:
            query: Task or query text for relevance scoring.
            scope_filter: Only include items at this scope or higher priority.
            tag_filter: Only include items with at least one matching tag.
            exclude_keys: Keys to exclude from injection.
            max_chars: Override max_context_chars for this injection.

        Returns:
            InjectionResult with assembled context and metadata.
        """
        start_time = time.monotonic()
        max_chars = max_chars or self.max_context_chars
        exclude_keys = exclude_keys or set()
        warnings: list[str] = []

        # Get candidate items
        candidates = self._get_candidates(scope_filter, tag_filter, exclude_keys)

        # Score candidates
        scored = []
        for item in candidates:
            score = self._score_item(query, item)
            item.relevance_score = score
            scored.append((item, score))

        # Sort by score (highest first), then by scope priority
        scored.sort(
            key=lambda x: (
                x[1],
                self.SCOPE_PRIORITY.get(x[0].scope, 0),
                x[0].access_count,
            ),
            reverse=True,
        )

        # Fill context window
        items_used: list[ContextItem] = []
        items_skipped: list[ContextItem] = []
        used_chars = 0

        for item, score in scored:
            if score < self.min_relevance:
                items_skipped.append(item)
                continue

            item_chars = len(item.content) + 50  # +50 for header/separator overhead

            if used_chars + item_chars > max_chars:
                items_skipped.append(item)
                continue

            if len(items_used) >= self.max_items:
                items_skipped.append(item)
                continue

            items_used.append(item)
            used_chars += item_chars
            item.touch()

        # Build injected context string
        injected_context = self._build_context_string(items_used)

        elapsed_ms = (time.monotonic() - start_time) * 1000
        self._injection_count += 1

        result = InjectionResult(
            injected_context=injected_context,
            items_used=items_used,
            items_skipped=items_skipped,
            total_items_available=len(candidates),
            char_count=len(injected_context),
            injection_time_ms=round(elapsed_ms, 2),
            warnings=warnings,
        )

        self._last_result = result
        return result

    def inject_dynamic(
        self,
        query: str,
        previous_items: Optional[list[str]] = None,
        new_items: Optional[list[dict[str, Any]]] = None,
        max_chars: Optional[int] = None,
    ) -> InjectionResult:
        """
        Dynamic context injection with swapping.

        Registers new items, then injects the most relevant context,
        potentially swapping out previously injected items.

        Args:
            query: Task/query text.
            previous_items: Keys of previously injected items.
            new_items: New context items to register before injection.
            max_chars: Override max_context_chars.

        Returns:
            InjectionResult with assembled context.
        """
        # Register new items
        if new_items:
            for item_data in new_items:
                try:
                    scope = item_data.get("scope", ContextScope.TASK)
                    if isinstance(scope, str):
                        scope = ContextScope(scope)
                    self.register(
                        key=item_data["key"],
                        content=item_data["content"],
                        scope=scope,
                        tags=item_data.get("tags"),
                        ttl_seconds=item_data.get("ttl_seconds"),
                    )
                except InjectionError as e:
                    logger.warning("Failed to register new context item: %s", e)

        # Exclude previous items to allow re-scoring
        exclude = set(previous_items or [])

        return self.inject(query, exclude_keys=exclude, max_chars=max_chars)

    # -- Public API: Queries -------------------------------------------------

    def get(self, key: str) -> Optional[ContextItem]:
        """Get a context item by key."""
        return self._items.get(key)

    def list_items(
        self,
        scope: Optional[ContextScope] = None,
        tag: Optional[str] = None,
        include_expired: bool = False,
    ) -> list[ContextItem]:
        """
        List context items with optional filters.

        Args:
            scope: Filter by scope.
            tag: Filter by tag (must contain this tag).
            include_expired: Include expired items.

        Returns:
            List of matching ContextItems.
        """
        items = list(self._items.values())

        if scope is not None:
            items = [i for i in items if i.scope == scope]

        if tag is not None:
            items = [i for i in items if tag in i.tags]

        if not include_expired:
            items = [i for i in items if not i.is_expired]

        return items

    def cleanup_expired(self) -> int:
        """
        Remove expired context items.

        Returns:
            Number of items removed.
        """
        expired_keys = [
            key for key, item in self._items.items()
            if item.is_expired
        ]

        for key in expired_keys:
            del self._items[key]

        if expired_keys:
            logger.debug("Cleaned up %d expired context items", len(expired_keys))

        return len(expired_keys)

    # -- Internal Methods ----------------------------------------------------

    def _get_candidates(
        self,
        scope_filter: Optional[ContextScope],
        tag_filter: Optional[list[str]],
        exclude_keys: set[str],
    ) -> list[ContextItem]:
        """Get candidate items for injection."""
        candidates = []

        for key, item in self._items.items():
            if key in exclude_keys:
                continue
            if item.is_expired:
                continue

            if scope_filter is not None:
                min_priority = self.SCOPE_PRIORITY.get(scope_filter, 0)
                item_priority = self.SCOPE_PRIORITY.get(item.scope, 0)
                if item_priority < min_priority:
                    continue

            if tag_filter:
                if not any(t in item.tags for t in tag_filter):
                    continue

            candidates.append(item)

        return candidates

    def _score_item(self, query: str, item: ContextItem) -> float:
        """Score a context item for relevance to a query."""
        if self.custom_scorer:
            try:
                base_score = self.custom_scorer(query, item.content, item.tags)
            except Exception as e:
                logger.warning("Custom scorer failed: %s", e)
                base_score = compute_relevance(
                    query, item.content, item.tags, self.tag_weights
                )
        else:
            base_score = compute_relevance(
                query, item.content, item.tags, self.tag_weights
            )

        # Freshness bonus
        freshness = item.freshness
        freshness_bonus = self.freshness_bonus * freshness

        # Access bonus (capped)
        access_bonus = min(0.2, item.access_count * self.access_bonus)

        # Scope bonus
        scope_bonus = self.SCOPE_PRIORITY.get(item.scope, 0) * 0.02

        # Combined score
        total = base_score + freshness_bonus + access_bonus + scope_bonus

        return min(1.0, max(0.0, total))

    def _build_context_string(self, items: list[ContextItem]) -> str:
        """Build the injected context string from items."""
        if not items:
            return ""

        parts: list[str] = []

        for item in items:
            header = f"## {item.key} (scope: {item.scope.value}, relevance: {item.relevance_score:.2f})"
            parts.append(f"{header}\n\n{item.content}")

        return "\n\n---\n\n".join(parts)

    # -- Properties ----------------------------------------------------------

    @property
    def item_count(self) -> int:
        """Total number of registered context items."""
        return len(self._items)

    @property
    def last_result(self) -> Optional[InjectionResult]:
        """Get the result of the last injection."""
        return self._last_result

    @property
    def injection_count(self) -> int:
        """Total number of injections performed."""
        return self._injection_count

    # -- Context Manager -----------------------------------------------------

    def __enter__(self) -> "ContextInjector":
        return self

    def __exit__(self, *args: Any) -> None:
        pass

    def __repr__(self) -> str:
        return (
            f"ContextInjector(items={self.item_count}, "
            f"max_chars={self.max_context_chars}, "
            f"injections={self._injection_count})"
        )
