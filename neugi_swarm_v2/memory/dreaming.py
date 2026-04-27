"""
Karpathy-style dreaming consolidation for NEUGI v2.

Implements a three-phase sleep cycle for memory consolidation:
    Light Sleep: Sort recent material, stage candidates, record reinforcement signals
    Deep Sleep: Rank candidates using 6 weighted signals, write to CORE.md
    REM Sleep: Extract patterns/themes, write to DREAMS.md

Consolidation thresholds:
    minScore: 0.75
    minRecallCount: 3
    minUniqueQueries: 3

Only Deep Sleep writes to CORE.md.
Scheduled via cron (default 3 AM) with ground truth backfill.
"""

from __future__ import annotations

import logging
import math
import re
import threading
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable, Optional

from memory.scopes import ScopePath
from memory.memory_core import MemorySystem, MemoryEntry, MemoryTier, MemoryError

logger = logging.getLogger(__name__)


class DreamPhase:
    """Constants for dream phases."""
    LIGHT = "light"
    DEEP = "deep"
    REM = "rem"


@dataclass
class DreamConfig:
    """
    Configuration for the dreaming consolidation engine.

    Signal weights for Deep Sleep ranking (must sum to 1.0):
        relevance: How well the memory matches recent queries (0.30)
        frequency: How often the memory has been accessed (0.24)
        query_diversity: How many different queries reference it (0.15)
        recency: How recently the memory was created/updated (0.15)
        consolidation: How much the memory connects to other memories (0.10)
        conceptual_richness: Information density of the content (0.06)
    """

    schedule_hour: int = 3
    schedule_minute: int = 0
    schedule_timezone: str = "local"

    min_score: float = 0.75
    min_recall_count: int = 3
    min_unique_queries: int = 3

    # Deep Sleep signal weights (sum to 1.0)
    weight_relevance: float = 0.30
    weight_frequency: float = 0.24
    weight_query_diversity: float = 0.15
    weight_recency: float = 0.15
    weight_consolidation: float = 0.10
    weight_conceptual_richness: float = 0.06

    # Light Sleep window (hours of recent activity to consider)
    light_sleep_window_hours: float = 24.0

    # Maximum memories to promote per cycle
    max_promotions_per_cycle: int = 50

    # Grounded backfill: number of past days to replay
    backfill_days: int = 7

    def __post_init__(self) -> None:
        total = (
            self.weight_relevance
            + self.weight_frequency
            + self.weight_query_diversity
            + self.weight_recency
            + self.weight_consolidation
            + self.weight_conceptual_richness
        )
        if abs(total - 1.0) > 1e-6:
            raise ValueError(
                f"Dream signal weights must sum to 1.0, got {total:.4f}"
            )


@dataclass
class DreamCandidate:
    """A memory entry staged for consolidation with computed signals."""

    entry: MemoryEntry
    relevance: float = 0.0
    frequency: float = 0.0
    query_diversity: float = 0.0
    recency: float = 0.0
    consolidation: float = 0.0
    conceptual_richness: float = 0.0
    composite_score: float = 0.0
    phase: str = DreamPhase.LIGHT

    @property
    def recall_count(self) -> int:
        return self.entry.access_count

    @property
    def unique_query_count(self) -> int:
        # Approximated by tag diversity as a proxy
        return len(set(self.entry.tags))


@dataclass
class DreamResult:
    """Summary of a complete dream cycle."""

    phase: str
    candidates_staged: int
    candidates_promoted: int
    candidates_rejected: int
    patterns_found: int
    core_md_updated: bool
    dreams_md_updated: bool
    duration_seconds: float
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = field(default_factory=dict)


# -- Signal computation ------------------------------------------------------

def _compute_relevance(entry: MemoryEntry, recent_queries: list[str]) -> float:
    """
    How well the memory matches recent queries.

    Uses keyword overlap between memory content and recent queries.
    """
    if not recent_queries:
        return 0.0

    content_words = set(_tokenize(entry.content))
    if not content_words:
        return 0.0

    total_overlap = 0.0
    for query in recent_queries:
        query_words = set(_tokenize(query))
        if not query_words:
            continue
        overlap = len(content_words & query_words) / len(query_words)
        total_overlap += overlap

    return min(1.0, total_overlap / len(recent_queries))


def _compute_frequency(entry: MemoryEntry, max_access: int) -> float:
    """
    Normalized access frequency.

    score = access_count / max_access (capped at 1.0)
    """
    if max_access <= 0:
        return 0.0
    return min(1.0, entry.access_count / max_access)


def _compute_query_diversity(entry: MemoryEntry, max_diversity: int) -> float:
    """
    How many different contexts reference this memory.

    Uses tag count as a proxy for query diversity.
    """
    if max_diversity <= 0:
        return 0.0
    diversity = len(set(entry.tags)) + 1  # +1 for the content itself
    return min(1.0, diversity / max_diversity)


def _compute_recency(entry: MemoryEntry, now: datetime) -> float:
    """
    Exponential recency decay.

    score = 2^(-age_hours / 168)  (1 week half-life)
    """
    updated = entry.updated_at
    if updated.tzinfo is None:
        updated = updated.replace(tzinfo=timezone.utc)
    age_hours = (now - updated).total_seconds() / 3600.0
    if age_hours < 0:
        return 1.0
    return 2.0 ** (-age_hours / 168.0)


def _compute_consolidation(
    entry: MemoryEntry, all_entries: list[MemoryEntry]
) -> float:
    """
    How much this memory connects to other memories.

    Measures content overlap with other entries.
    """
    if len(all_entries) <= 1:
        return 0.0

    entry_words = set(_tokenize(entry.content))
    if not entry_words:
        return 0.0

    connections = 0
    for other in all_entries:
        if other.id == entry.id:
            continue
        other_words = set(_tokenize(other.content))
        overlap = len(entry_words & other_words) / len(entry_words)
        if overlap > 0.3:  # Significant overlap
            connections += 1

    return min(1.0, connections / max(1, len(all_entries) * 0.1))


def _compute_conceptual_richness(entry: MemoryEntry) -> float:
    """
    Information density of the content.

    Heuristic: ratio of unique meaningful words to total words,
    weighted by content length.
    """
    words = _tokenize(entry.content)
    if not words:
        return 0.0

    unique_ratio = len(set(words)) / len(words)
    length_factor = min(1.0, len(words) / 50.0)  # Normalize to ~50 words

    return unique_ratio * 0.6 + length_factor * 0.4


def _tokenize(text: str) -> list[str]:
    """Simple tokenizer: lowercase, alpha-only, min length 3."""
    words = re.findall(r"[a-zA-Z]{3,}", text.lower())
    return words


# -- Dream Engine ------------------------------------------------------------

class DreamingEngine:
    """
    Karpathy-style dreaming consolidation engine.

    Runs a three-phase sleep cycle to consolidate memories:
        1. Light Sleep: Stage candidates from recent activity
        2. Deep Sleep: Rank and promote high-value memories to CORE.md
        3. REM Sleep: Extract patterns and write to DREAMS.md

    Usage:
        engine = DreamingEngine(memory_system)
        engine.run_cycle()  # Manual
        engine.start_scheduler()  # Cron-based (default 3 AM)
    """

    def __init__(
        self,
        memory_system: MemorySystem,
        config: Optional[DreamConfig] = None,
        output_dir: Optional[str] = None,
        pattern_extractor: Optional[Callable[[list[MemoryEntry]], list[str]]] = None,
    ) -> None:
        """
        Initialize the dreaming engine.

        Args:
            memory_system: The MemorySystem to consolidate.
            config: Dream configuration (uses defaults if None).
            output_dir: Directory for CORE.md and DREAMS.md files.
            pattern_extractor: Optional LLM-based pattern extractor.
                Signature: (entries: list[MemoryEntry]) -> list[str]
                Falls back to keyword-based extraction if None.
        """
        self.memory = memory_system
        self.config = config or DreamConfig()
        self.output_dir = Path(output_dir) if output_dir else memory_system.base_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.pattern_extractor = pattern_extractor or _keyword_pattern_extract

        # Query history for reinforcement signals
        self._query_history: list[tuple[str, datetime]] = []
        self._query_lock = threading.Lock()

        # Scheduler state
        self._scheduler_thread: Optional[threading.Thread] = None
        self._scheduler_running = False

    # -- Query tracking ------------------------------------------------------

    def record_query(self, query: str) -> None:
        """Record a query for reinforcement signal tracking."""
        with self._query_lock:
            self._query_history.append((query, datetime.now(timezone.utc)))
            # Keep last 1000 queries
            if len(self._query_history) > 1000:
                self._query_history = self._query_history[-1000:]

    def get_recent_queries(
        self, hours: Optional[float] = None
    ) -> list[str]:
        """Get queries from the recent window."""
        hours = hours or self.config.light_sleep_window_hours
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        with self._query_lock:
            return [q for q, ts in self._query_history if ts >= cutoff]

    # -- Main cycle ----------------------------------------------------------

    def run_cycle(
        self, scope: Optional[ScopePath] = None
    ) -> list[DreamResult]:
        """
        Run a complete three-phase dream cycle.

        Args:
            scope: Limit consolidation to a specific scope.

        Returns:
            List of DreamResult for each phase.
        """
        results: list[DreamResult] = []

        logger.info("Starting dream cycle (scope=%s)", scope)

        # Phase 1: Light Sleep
        light_result = self._light_sleep(scope)
        results.append(light_result)

        if light_result.candidates_staged == 0:
            logger.info("Light Sleep: no candidates staged, skipping Deep/REM")
            return results

        # Phase 2: Deep Sleep
        deep_result = self._deep_sleep(light_result.details.get("candidates", []))
        results.append(deep_result)

        # Phase 3: REM Sleep
        rem_result = self._rem_sleep(light_result.details.get("candidates", []))
        results.append(rem_result)

        logger.info("Dream cycle complete: %d phases", len(results))
        return results

    # -- Phase 1: Light Sleep -----------------------------------------------

    def _light_sleep(
        self, scope: Optional[ScopePath] = None
    ) -> DreamResult:
        """
        Light Sleep phase: sort recent material, stage candidates,
        record reinforcement signals.

        This phase is read-only - it only stages candidates for
        Deep Sleep processing.
        """
        start = time.time()

        # Gather recent daily memories
        now = datetime.now(timezone.utc)
        with self.memory._store_lock:
            candidates = [
                e for e in self.memory._store.values()
                if e.tier == MemoryTier.DAILY and not e.is_expired(now)
            ]

        if scope is not None:
            candidates = [e for e in candidates if e.scope.is_subtree_of(scope)]

        # Get recent queries for reinforcement signals
        recent_queries = self.get_recent_queries()

        # Compute max values for normalization
        max_access = max((e.access_count for e in candidates), default=1)
        max_diversity = max((len(set(e.tags)) + 1 for e in candidates), default=1)

        # Stage candidates with signal computation
        staged: list[DreamCandidate] = []
        for entry in candidates:
            candidate = DreamCandidate(
                entry=entry,
                relevance=_compute_relevance(entry, recent_queries),
                frequency=_compute_frequency(entry, max_access),
                query_diversity=_compute_query_diversity(entry, max_diversity),
                recency=_compute_recency(entry, now),
                consolidation=_compute_consolidation(entry, candidates),
                conceptual_richness=_compute_conceptual_richness(entry),
                phase=DreamPhase.LIGHT,
            )
            staged.append(candidate)

        # Sort by preliminary composite (without deep sleep weights)
        staged.sort(key=lambda c: c.relevance + c.frequency, reverse=True)

        duration = time.time() - start
        result = DreamResult(
            phase=DreamPhase.LIGHT,
            candidates_staged=len(staged),
            candidates_promoted=0,
            candidates_rejected=0,
            patterns_found=0,
            core_md_updated=False,
            dreams_md_updated=False,
            duration_seconds=duration,
            details={"candidates": staged},
        )

        logger.info(
            "Light Sleep: staged %d candidates in %.2fs",
            len(staged), duration,
        )
        return result

    # -- Phase 2: Deep Sleep ------------------------------------------------

    def _deep_sleep(
        self, candidates: list[DreamCandidate]
    ) -> DreamResult:
        """
        Deep Sleep phase: rank candidates using 6 weighted signals,
        promote qualifying memories to CORE.md.

        Only this phase writes to CORE.md.

        Thresholds:
            minScore: 0.75
            minRecallCount: 3
            minUniqueQueries: 3
        """
        start = time.time()
        cfg = self.config

        promoted: list[DreamCandidate] = []
        rejected: list[DreamCandidate] = []

        for candidate in candidates:
            # Compute composite score
            score = (
                cfg.weight_relevance * candidate.relevance
                + cfg.weight_frequency * candidate.frequency
                + cfg.weight_query_diversity * candidate.query_diversity
                + cfg.weight_recency * candidate.recency
                + cfg.weight_consolidation * candidate.consolidation
                + cfg.weight_conceptual_richness * candidate.conceptual_richness
            )
            candidate.composite_score = score
            candidate.phase = DreamPhase.DEEP

            # Check thresholds
            meets_score = score >= cfg.min_score
            meets_recall = candidate.recall_count >= cfg.min_recall_count
            meets_diversity = candidate.unique_query_count >= cfg.min_unique_queries

            if meets_score and (meets_recall or meets_diversity):
                promoted.append(candidate)
            else:
                rejected.append(candidate)

        # Cap promotions
        if len(promoted) > cfg.max_promotions_per_cycle:
            promoted.sort(key=lambda c: c.composite_score, reverse=True)
            rejected.extend(promoted[cfg.max_promotions_per_cycle:])
            promoted = promoted[:cfg.max_promotions_per_cycle]

        # Promote to core tier
        core_updated = False
        for candidate in promoted:
            entry = candidate.entry
            if entry.tier != MemoryTier.CORE:
                entry.tier = MemoryTier.CORE
                entry.expires_at = None  # Permanent
                entry.updated_at = datetime.now(timezone.utc)
                entry.metadata["promoted_by_dream"] = True
                entry.metadata["dream_score"] = candidate.composite_score
                entry.metadata["dream_timestamp"] = datetime.now(timezone.utc).isoformat()

                # Update in memory system
                with self.memory._store_lock:
                    self.memory._store[entry.id] = entry
                self.memory.scoring.index(entry.id, entry.content, entry.importance, entry.created_at)
                self.memory._queue_save(entry)
                core_updated = True

        # Write CORE.md
        if core_updated:
            try:
                self.memory.write_core_md()
            except Exception as e:
                logger.error("Failed to write CORE.md: %s", e)

        duration = time.time() - start
        result = DreamResult(
            phase=DreamPhase.DEEP,
            candidates_staged=len(candidates),
            candidates_promoted=len(promoted),
            candidates_rejected=len(rejected),
            patterns_found=0,
            core_md_updated=core_updated,
            dreams_md_updated=False,
            duration_seconds=duration,
            details={
                "promoted_ids": [c.entry.id for c in promoted],
                "rejected_ids": [c.entry.id for c in rejected],
            },
        )

        logger.info(
            "Deep Sleep: promoted %d / %d candidates in %.2fs",
            len(promoted), len(candidates), duration,
        )
        return result

    # -- Phase 3: REM Sleep -------------------------------------------------

    def _rem_sleep(
        self, candidates: list[DreamCandidate]
    ) -> DreamResult:
        """
        REM Sleep phase: extract patterns/themes from recent memories,
        write to DREAMS.md.

        This phase is analytical - it identifies recurring themes and
        connections without modifying memory tiers.
        """
        start = time.time()

        # Extract patterns from candidates
        entries = [c.entry for c in candidates]
        patterns = self.pattern_extractor(entries)

        # Write DREAMS.md
        dreams_updated = False
        if patterns:
            try:
                dreams_path = self.output_dir / "DREAMS.md"
                self._write_dreams_md(dreams_path, patterns, candidates)
                dreams_updated = True
            except Exception as e:
                logger.error("Failed to write DREAMS.md: %s", e)

        duration = time.time() - start
        result = DreamResult(
            phase=DreamPhase.REM,
            candidates_staged=len(candidates),
            candidates_promoted=0,
            candidates_rejected=0,
            patterns_found=len(patterns),
            core_md_updated=False,
            dreams_md_updated=dreams_updated,
            duration_seconds=duration,
            details={"patterns": patterns},
        )

        logger.info(
            "REM Sleep: found %d patterns in %.2fs",
            len(patterns), duration,
        )
        return result

    def _write_dreams_md(
        self,
        path: Path,
        patterns: list[str],
        candidates: list[DreamCandidate],
    ) -> None:
        """Write the DREAMS.md file with extracted patterns."""
        now = datetime.now(timezone.utc)

        # Read existing content to append
        existing = ""
        if path.exists():
            existing = path.read_text(encoding="utf-8")

        with open(path, "w", encoding="utf-8") as f:
            f.write(f"# Dream Journal - {now.strftime('%Y-%m-%d %H:%M')}\n\n")

            if existing:
                f.write(existing)
                f.write("\n---\n\n")

            f.write(f"## Session {now.isoformat()}\n\n")
            f.write(f"Candidates analyzed: {len(candidates)}\n")
            f.write(f"Patterns found: {len(patterns)}\n\n")

            for i, pattern in enumerate(patterns, 1):
                f.write(f"### Pattern {i}\n\n")
                f.write(f"{pattern}\n\n")

            # Top candidates by score
            top = sorted(candidates, key=lambda c: c.composite_score, reverse=True)[:10]
            if top:
                f.write("## Top Candidates\n\n")
                f.write("| ID | Score | Content |\n")
                f.write("|---|---|---|\n")
                for c in top:
                    preview = c.entry.content[:80].replace("\n", " ")
                    f.write(f"| {c.entry.id} | {c.composite_score:.3f} | {preview} |\n")
                f.write("\n")

    # -- Scheduler -----------------------------------------------------------

    def start_scheduler(self) -> None:
        """Start the cron-based scheduler (default 3 AM daily)."""
        if self._scheduler_running:
            logger.warning("Scheduler already running")
            return

        self._scheduler_running = True
        self._scheduler_thread = threading.Thread(
            target=self._scheduler_loop, daemon=True, name="dream-scheduler"
        )
        self._scheduler_thread.start()
        logger.info(
            "Dream scheduler started (daily at %02d:%02d)",
            self.config.schedule_hour, self.config.schedule_minute,
        )

    def stop_scheduler(self) -> None:
        """Stop the cron-based scheduler."""
        self._scheduler_running = False
        if self._scheduler_thread:
            self._scheduler_thread.join(timeout=10.0)
            self._scheduler_thread = None
        logger.info("Dream scheduler stopped")

    def _scheduler_loop(self) -> None:
        """Main scheduler loop - wakes up at configured time daily."""
        while self._scheduler_running:
            now = datetime.now()
            target = now.replace(
                hour=self.config.schedule_hour,
                minute=self.config.schedule_minute,
                second=0,
                microsecond=0,
            )
            if now >= target:
                target += timedelta(days=1)

            sleep_seconds = (target - now).total_seconds()
            logger.info("Next dream cycle in %.1f hours", sleep_seconds / 3600)

            # Sleep in 60-second increments to allow clean shutdown
            while sleep_seconds > 0 and self._scheduler_running:
                time.sleep(min(60, sleep_seconds))
                sleep_seconds -= 60

            if not self._scheduler_running:
                break

            try:
                logger.info("Running scheduled dream cycle")
                self.run_cycle()
            except Exception as e:
                logger.error("Scheduled dream cycle failed: %s", e)

    # -- Grounded Backfill ---------------------------------------------------

    def grounded_backfill(
        self, days: Optional[int] = None, scope: Optional[ScopePath] = None
    ) -> DreamResult:
        """
        Replay historical daily notes to recover missed promotions.

        This scans past daily memory files and re-evaluates them
        through the dream pipeline, catching memories that should
        have been promoted but weren't (e.g. due to downtime).

        Args:
            days: Number of past days to replay (uses config default if None).
            scope: Limit backfill to a specific scope.

        Returns:
            DreamResult summarizing the backfill.
        """
        days = days or self.config.backfill_days
        start = time.time()
        now = datetime.now(timezone.utc)

        # Gather memories from the past N days
        cutoff = now - timedelta(days=days)
        with self.memory._store_lock:
            historical = [
                e for e in self.memory._store.values()
                if e.tier == MemoryTier.DAILY
                and e.created_at >= cutoff
                and not e.is_expired(now)
            ]

        if scope is not None:
            historical = [e for e in historical if e.scope.is_subtree_of(scope)]

        logger.info("Grounded backfill: %d historical memories from %d days", len(historical), days)

        # Re-stage as candidates
        recent_queries = self.get_recent_queries(hours=days * 24)
        max_access = max((e.access_count for e in historical), default=1)
        max_diversity = max((len(set(e.tags)) + 1 for e in historical), default=1)

        candidates: list[DreamCandidate] = []
        for entry in historical:
            candidate = DreamCandidate(
                entry=entry,
                relevance=_compute_relevance(entry, recent_queries),
                frequency=_compute_frequency(entry, max_access),
                query_diversity=_compute_query_diversity(entry, max_diversity),
                recency=_compute_recency(entry, now),
                consolidation=_compute_consolidation(entry, historical),
                conceptual_richness=_compute_conceptual_richness(entry),
                phase=DreamPhase.LIGHT,
            )
            candidates.append(candidate)

        # Run deep sleep on historical candidates
        deep_result = self._deep_sleep(candidates)

        duration = time.time() - start
        result = DreamResult(
            phase="backfill",
            candidates_staged=len(candidates),
            candidates_promoted=deep_result.candidates_promoted,
            candidates_rejected=deep_result.candidates_rejected,
            patterns_found=0,
            core_md_updated=deep_result.core_md_updated,
            dreams_md_updated=False,
            duration_seconds=duration,
            details={"days_scanned": days, "historical_count": len(historical)},
        )

        logger.info(
            "Grounded backfill complete: promoted %d in %.2fs",
            deep_result.candidates_promoted, duration,
        )
        return result

    # -- Lifecycle -----------------------------------------------------------

    def close(self) -> None:
        """Shut down the dreaming engine."""
        self.stop_scheduler()

    def __enter__(self) -> "DreamingEngine":
        return self

    def __exit__(self, *args: Any) -> None:
        self.close()


# -- Pattern extraction (keyword fallback) -----------------------------------

def _keyword_pattern_extract(entries: list[MemoryEntry]) -> list[str]:
    """
    Extract recurring patterns/themes from a set of memory entries.

    Uses keyword frequency analysis to identify common themes.
    """
    if not entries:
        return []

    # Count word frequencies across all entries
    word_counts: Counter = Counter()
    for entry in entries:
        words = _tokenize(entry.content)
        word_counts.update(words)

    # Filter to meaningful words (appear in at least 2 entries)
    entry_count = len(entries)
    threshold = max(2, entry_count // 4)

    # Find co-occurring word pairs
    patterns: list[str] = []
    top_words = [w for w, c in word_counts.most_common(50) if c >= threshold]

    if len(top_words) >= 2:
        # Group by semantic clusters (simple: first letter grouping)
        clusters: dict[str, list[str]] = {}
        for word in top_words:
            key = word[0]
            clusters.setdefault(key, []).append(word)

        for letter, words in sorted(clusters.items()):
            if len(words) >= 2:
                patterns.append(f"Theme '{letter}': {', '.join(words[:5])}")

    # Extract tag-based patterns
    tag_counts: Counter = Counter()
    for entry in entries:
        tag_counts.update(entry.tags)

    common_tags = [tag for tag, count in tag_counts.most_common(10) if count >= 2]
    if common_tags:
        patterns.append(f"Common tags: {', '.join(common_tags)}")

    # Source-based patterns
    source_counts: Counter = Counter(e.source for e in entries)
    active_sources = [s for s, c in source_counts.most_common(5) if c >= 2]
    if active_sources:
        patterns.append(f"Active sources: {', '.join(active_sources)}")

    return patterns
