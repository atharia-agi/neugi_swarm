"""
Composite scoring engine for NEUGI v2 memory recall.

Combines multiple signals into a single relevance score:
    - TF-IDF semantic similarity
    - Recency decay (exponential with configurable half-life)
    - Importance weighting (user-set or LLM-inferred)
    - Frequency boost (how often accessed/referenced)

All weights are configurable and can be tuned per-scope.
"""

from __future__ import annotations

import math
import re
import string
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional


@dataclass
class ScoreComponents:
    """Individual signal values that contribute to the composite score."""

    semantic: float = 0.0
    recency: float = 0.0
    importance: float = 0.0
    frequency: float = 0.0

    @property
    def max_possible(self) -> float:
        """Sum of all weights (normalization ceiling)."""
        return 1.0

    def weighted_sum(self, config: ScoreConfig) -> float:
        """Compute the weighted composite score."""
        return (
            config.semantic_weight * self.semantic
            + config.recency_weight * self.recency
            + config.importance_weight * self.importance
            + config.frequency_weight * self.frequency
        )


@dataclass
class ScoreConfig:
    """
    Configurable weights for the composite scoring engine.

    Default weights are tuned for general-purpose memory recall.
    Override per-scope for specialized behaviour (e.g. task scopes
    may prioritise recency over importance).
    """

    semantic_weight: float = 0.35
    recency_weight: float = 0.25
    importance_weight: float = 0.25
    frequency_weight: float = 0.15

    recency_half_life_hours: float = 48.0
    frequency_cap: int = 100

    def __post_init__(self) -> None:
        total = (
            self.semantic_weight
            + self.recency_weight
            + self.importance_weight
            + self.frequency_weight
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(f"Score weights must sum to 1.0, got {total}")
        if self.recency_half_life_hours <= 0:
            raise ValueError("recency_half_life_hours must be positive")
        if self.frequency_cap < 1:
            raise ValueError("frequency_cap must be >= 1")

    @classmethod
    def recency_focused(cls) -> ScoreConfig:
        """Prioritise recent memories (useful for task scopes)."""
        return cls(
            semantic_weight=0.20,
            recency_weight=0.45,
            importance_weight=0.20,
            frequency_weight=0.15,
        )

    @classmethod
    def importance_focused(cls) -> ScoreConfig:
        """Prioritise high-importance memories (useful for core knowledge)."""
        return cls(
            semantic_weight=0.25,
            recency_weight=0.15,
            importance_weight=0.45,
            frequency_weight=0.15,
        )

    @classmethod
    def semantic_focused(cls) -> ScoreConfig:
        """Prioritise semantic match (useful for research/learning)."""
        return cls(
            semantic_weight=0.50,
            recency_weight=0.15,
            importance_weight=0.20,
            frequency_weight=0.15,
        )


# -- TF-IDF implementation (pure Python, no external deps) ------------------

_STOP_WORDS = frozenset({
    "a", "an", "the", "and", "or", "but", "in", "on", "at", "to", "for",
    "of", "with", "by", "from", "is", "are", "was", "were", "be", "been",
    "being", "have", "has", "had", "do", "does", "did", "will", "would",
    "could", "should", "may", "might", "shall", "can", "need", "dare",
    "ought", "used", "it", "its", "this", "that", "these", "those", "i",
    "you", "he", "she", "we", "they", "what", "which", "who", "whom",
    "whose", "where", "when", "why", "how", "all", "each", "every",
    "both", "few", "more", "most", "other", "some", "such", "no", "not",
    "only", "own", "same", "so", "than", "too", "very", "just", "also",
    "as", "if", "then", "because", "while", "about", "against", "between",
    "into", "through", "during", "before", "after", "above", "below",
    "up", "down", "out", "off", "over", "under", "again", "further",
})

_PUNCT_RE = re.compile(f"[{re.escape(string.punctuation)}]")


def _tokenize(text: str) -> list[str]:
    """Lowercase, strip punctuation, remove stop words and short tokens."""
    text = _PUNCT_RE.sub(" ", text.lower())
    tokens = text.split()
    return [t for t in tokens if t not in _STOP_WORDS and len(t) > 2]


def _tf(tokens: list[str]) -> dict[str, float]:
    """Term frequency: count / total for a single document."""
    if not tokens:
        return {}
    counts = Counter(tokens)
    total = len(tokens)
    return {term: count / total for term, count in counts.items()}


def _idf(documents: list[list[str]]) -> dict[str, float]:
    """Inverse document frequency across a corpus."""
    n_docs = len(documents)
    if n_docs == 0:
        return {}
    doc_freq: Counter = Counter()
    for tokens in documents:
        doc_freq.update(set(tokens))
    return {
        term: math.log(n_docs / (1 + df)) for term, df in doc_freq.items()
    }


def _cosine_similarity(vec_a: dict[str, float], vec_b: dict[str, float]) -> float:
    """Cosine similarity between two sparse term vectors."""
    if not vec_a or not vec_b:
        return 0.0
    common_keys = set(vec_a) & set(vec_b)
    if not common_keys:
        return 0.0
    dot = sum(vec_a[k] * vec_b[k] for k in common_keys)
    norm_a = math.sqrt(sum(v * v for v in vec_a.values()))
    norm_b = math.sqrt(sum(v * v for v in vec_b.values()))
    if norm_a == 0 or norm_b == 0:
        return 0.0
    return dot / (norm_a * norm_b)


# -- Scoring Engine ----------------------------------------------------------

class ScoringEngine:
    """
    Composite scoring engine combining TF-IDF semantic similarity,
    recency decay, importance weighting, and frequency boost.

    Usage:
        engine = ScoringEngine()
        engine.index("mem_1", "The user prefers dark mode")
        engine.index("mem_2", "Enable light theme by default")
        scores = engine.score_all("dark mode preference")
        # Returns {mem_id: ScoreComponents}
    """

    def __init__(self, config: Optional[ScoreConfig] = None) -> None:
        self.config = config or ScoreConfig()
        self._doc_tokens: dict[str, list[str]] = {}
        self._access_counts: dict[str, int] = {}
        self._importance: dict[str, float] = {}
        self._indexed_at: dict[str, datetime] = {}
        self._idf_cache: Optional[dict[str, float]] = None

    # -- Indexing ------------------------------------------------------------

    def index(
        self,
        mem_id: str,
        content: str,
        importance: float = 0.5,
        timestamp: Optional[datetime] = None,
    ) -> None:
        """
        Register a memory entry for scoring.

        Args:
            mem_id: Unique identifier for the memory.
            content: Text content to tokenize and index.
            importance: Importance weight in [0, 1].
            timestamp: When the memory was created (defaults to now).
        """
        tokens = _tokenize(content)
        self._doc_tokens[mem_id] = tokens
        self._importance[mem_id] = max(0.0, min(1.0, importance))
        self._indexed_at[mem_id] = timestamp or datetime.now(timezone.utc)
        self._access_counts.setdefault(mem_id, 0)
        self._idf_cache = None  # invalidate cache

    def update_importance(self, mem_id: str, importance: float) -> None:
        """Update the importance weight for an existing memory."""
        if mem_id in self._importance:
            self._importance[mem_id] = max(0.0, min(1.0, importance))

    def record_access(self, mem_id: str) -> None:
        """Increment the access counter for a memory (frequency boost)."""
        self._access_counts[mem_id] = self._access_counts.get(mem_id, 0) + 1

    def remove(self, mem_id: str) -> None:
        """Remove a memory from the scoring index."""
        self._doc_tokens.pop(mem_id, None)
        self._access_counts.pop(mem_id, None)
        self._importance.pop(mem_id, None)
        self._indexed_at.pop(mem_id, None)
        self._idf_cache = None

    def clear(self) -> None:
        """Remove all indexed memories."""
        self._doc_tokens.clear()
        self._access_counts.clear()
        self._importance.clear()
        self._indexed_at.clear()
        self._idf_cache = None

    # -- Scoring -------------------------------------------------------------

    def _get_idf(self) -> dict[str, float]:
        """Compute (cached) IDF across all indexed documents."""
        if self._idf_cache is None:
            self._idf_cache = _idf(list(self._doc_tokens.values()))
        return self._idf_cache

    def _semantic_score(self, query: str, mem_id: str) -> float:
        """TF-IDF cosine similarity between query and a memory."""
        if mem_id not in self._doc_tokens:
            return 0.0
        idf = self._get_idf()
        query_tokens = _tokenize(query)
        if not query_tokens:
            return 0.0

        # Build TF-IDF vectors
        query_tf = _tf(query_tokens)
        doc_tf = _tf(self._doc_tokens[mem_id])

        query_vec = {t: query_tf.get(t, 0) * idf.get(t, 0) for t in query_tokens}
        doc_vec = {
            t: doc_tf.get(t, 0) * idf.get(t, 0)
            for t in self._doc_tokens[mem_id]
        }

        return _cosine_similarity(query_vec, doc_vec)

    def _recency_score(self, mem_id: str, now: Optional[datetime] = None) -> float:
        """
        Exponential decay based on age.

        score = 2^(-age_hours / half_life)
        """
        if mem_id not in self._indexed_at:
            return 0.0
        now = now or datetime.now(timezone.utc)
        created = self._indexed_at[mem_id]
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        age_hours = (now - created).total_seconds() / 3600.0
        if age_hours < 0:
            return 1.0
        half_life = self.config.recency_half_life_hours
        return 2.0 ** (-age_hours / half_life)

    def _importance_score(self, mem_id: str) -> float:
        """Return the stored importance weight in [0, 1]."""
        return self._importance.get(mem_id, 0.5)

    def _frequency_score(self, mem_id: str) -> float:
        """
        Log-scaled frequency boost, capped at config.frequency_cap.

        score = log(1 + accesses) / log(1 + cap)
        """
        accesses = self._access_counts.get(mem_id, 0)
        cap = self.config.frequency_cap
        if cap <= 0:
            return 0.0
        return math.log(1 + min(accesses, cap)) / math.log(1 + cap)

    def score(
        self, query: str, mem_id: str, now: Optional[datetime] = None
    ) -> ScoreComponents:
        """
        Compute all score components for a single memory against a query.

        Returns:
            ScoreComponents with individual signal values and a
            weighted_sum() method using the current config.
        """
        return ScoreComponents(
            semantic=self._semantic_score(query, mem_id),
            recency=self._recency_score(mem_id, now),
            importance=self._importance_score(mem_id),
            frequency=self._frequency_score(mem_id),
        )

    def score_all(
        self,
        query: str,
        mem_ids: Optional[Iterable[str]] = None,
        now: Optional[datetime] = None,
        min_score: float = 0.0,
    ) -> list[tuple[str, float, ScoreComponents]]:
        """
        Score all (or a subset of) memories against a query.

        Args:
            query: The search/recall query.
            mem_ids: Specific memory IDs to score (None = all indexed).
            now: Reference time for recency (defaults to now).
            min_score: Filter out results below this composite score.

        Returns:
            List of (mem_id, composite_score, components) sorted by
            composite score descending.
        """
        targets = mem_ids if mem_ids is not None else list(self._doc_tokens)
        results: list[tuple[str, float, ScoreComponents]] = []
        for mid in targets:
            components = self.score(query, mid, now)
            composite = components.weighted_sum(self.config)
            if composite >= min_score:
                results.append((mid, composite, components))
        results.sort(key=lambda x: x[1], reverse=True)
        return results

    def top_k(
        self,
        query: str,
        k: int = 10,
        mem_ids: Optional[Iterable[str]] = None,
        now: Optional[datetime] = None,
        min_score: float = 0.0,
    ) -> list[tuple[str, float, ScoreComponents]]:
        """Return the top-k scored memories for a query."""
        return self.score_all(query, mem_ids, now, min_score)[:k]

    # -- Bulk operations -----------------------------------------------------

    def reindex_all(self) -> None:
        """Recompute IDF cache (useful after bulk updates)."""
        self._idf_cache = None
        self._get_idf()

    @property
    def indexed_count(self) -> int:
        """Number of memories currently indexed."""
        return len(self._doc_tokens)
