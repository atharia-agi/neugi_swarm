#!/usr/bin/env python3
"""
NEUGI v2 - Self-Reflection Engine
==================================

Post-action reflection, error analysis, strategy adjustment, and
self-correction with persistent reflection memory.

Key features:
- Post-action reflection (what worked, what didn't)
- Error analysis and root cause identification
- Strategy adjustment based on reflection insights
- Reflection memory (learn from past reflections)
- Self-correction loop with confidence calibration
- SQLite-backed persistent reflection storage
- Pattern recognition across reflections

Usage:
    engine = SelfReflectionEngine(llm_callback, db_path="reflections.db")
    reflection = await engine.reflect(
        action="Generated code for user authentication",
        outcome="Tests passed but security scan found XSS vulnerability",
        context={"files_changed": ["auth.py"], "test_results": "12/13 passed"},
    )
    adjusted = await engine.get_strategy_adjustment(reflection)
"""

from __future__ import annotations

import json
import logging
import sqlite3
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class ConfidenceLevel(Enum):
    """Calibrated confidence levels."""

    VERY_LOW = "very_low"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    VERY_HIGH = "very_high"

    @property
    def numeric(self) -> float:
        return {
            "very_low": 0.1,
            "low": 0.3,
            "medium": 0.5,
            "high": 0.75,
            "very_high": 0.95,
        }[self.value]

    @classmethod
    def from_score(cls, score: float) -> "ConfidenceLevel":
        if score >= 0.9:
            return cls.VERY_HIGH
        if score >= 0.7:
            return cls.HIGH
        if score >= 0.4:
            return cls.MEDIUM
        if score >= 0.2:
            return cls.LOW
        return cls.VERY_LOW


class ErrorCategory(Enum):
    """Categories of errors for classification."""

    LOGIC_ERROR = "logic_error"
    SYNTAX_ERROR = "syntax_error"
    SECURITY_ISSUE = "security_issue"
    PERFORMANCE_ISSUE = "performance_issue"
    DESIGN_FLAW = "design_flaw"
    MISUNDERSTANDING = "misunderstanding"
    INCOMPLETE = "incomplete"
    EDGE_CASE = "edge_case"
    DEPENDENCY_ISSUE = "dependency_issue"
    CONFIGURATION_ERROR = "configuration_error"
    UNKNOWN = "unknown"


@dataclass
class Reflection:
    """A single reflection on an action and its outcome.

    Args:
        reflection_id: Unique identifier.
        action: Description of the action taken.
        outcome: What actually happened.
        context: Additional context about the action.
        what_worked: Aspects that were successful.
        what_failed: Aspects that failed or underperformed.
        root_cause: Identified root cause of any failures.
        error_category: Classification of the error (if any).
        lessons_learned: Key takeaways from this reflection.
        strategy_adjustment: How to adjust strategy going forward.
        confidence: Calibrated confidence in this reflection.
        severity: Severity of any issues found (0.0-1.0).
        created_at: Timestamp of creation.
        tags: Optional tags for categorization.
        related_reflection_ids: IDs of related past reflections.
    """

    reflection_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    action: str = ""
    outcome: str = ""
    context: Dict[str, Any] = field(default_factory=dict)
    what_worked: List[str] = field(default_factory=list)
    what_failed: List[str] = field(default_factory=list)
    root_cause: str = ""
    error_category: Optional[ErrorCategory] = None
    lessons_learned: List[str] = field(default_factory=list)
    strategy_adjustment: str = ""
    confidence: float = 0.5
    severity: float = 0.0
    created_at: float = field(default_factory=time.time)
    tags: List[str] = field(default_factory=list)
    related_reflection_ids: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reflection_id": self.reflection_id,
            "action": self.action,
            "outcome": self.outcome,
            "context": json.dumps(self.context),
            "what_worked": json.dumps(self.what_worked),
            "what_failed": json.dumps(self.what_failed),
            "root_cause": self.root_cause,
            "error_category": self.error_category.value if self.error_category else None,
            "lessons_learned": json.dumps(self.lessons_learned),
            "strategy_adjustment": self.strategy_adjustment,
            "confidence": self.confidence,
            "severity": self.severity,
            "created_at": self.created_at,
            "tags": json.dumps(self.tags),
            "related_reflection_ids": json.dumps(self.related_reflection_ids),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Reflection":
        def _parse_json(key: str, default: Any = None) -> Any:
            val = data.get(key)
            if val is None:
                return default
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except (json.JSONDecodeError, TypeError):
                    return default
            return val

        cat_str = data.get("error_category")
        category = None
        if cat_str:
            try:
                category = ErrorCategory(cat_str)
            except ValueError:
                category = ErrorCategory.UNKNOWN

        return cls(
            reflection_id=data.get("reflection_id", ""),
            action=data.get("action", ""),
            outcome=data.get("outcome", ""),
            context=_parse_json("context", {}),
            what_worked=_parse_json("what_worked", []),
            what_failed=_parse_json("what_failed", []),
            root_cause=data.get("root_cause", ""),
            error_category=category,
            lessons_learned=_parse_json("lessons_learned", []),
            strategy_adjustment=data.get("strategy_adjustment", ""),
            confidence=float(data.get("confidence", 0.5)),
            severity=float(data.get("severity", 0.0)),
            created_at=float(data.get("created_at", time.time())),
            tags=_parse_json("tags", []),
            related_reflection_ids=_parse_json("related_reflection_ids", []),
        )


@dataclass
class ReflectionConfig:
    """Configuration for the self-reflection engine.

    Args:
        max_memory_size: Maximum reflections to store in memory.
        db_path: Path to SQLite database for persistence.
        auto_correct: Whether to automatically apply corrections.
        max_correction_attempts: Maximum self-correction iterations.
        confidence_calibration_window: Number of recent reflections for calibration.
        enable_pattern_detection: Whether to detect patterns across reflections.
        min_severity_to_log: Minimum severity to log as warning.
        retention_days: Days to keep reflections before archival.
    """

    max_memory_size: int = 1000
    db_path: str = "reflections.db"
    auto_correct: bool = True
    max_correction_attempts: int = 3
    confidence_calibration_window: int = 50
    enable_pattern_detection: bool = True
    min_severity_to_log: float = 0.5
    retention_days: int = 90


@dataclass
class ReflectionResult:
    """Result from a reflection cycle.

    Args:
        reflection: The generated reflection.
        corrections: List of corrections identified.
        strategy_changes: Strategy adjustments recommended.
        similar_past_reflections: Related past reflections.
        patterns: Patterns detected across reflections.
        confidence_calibrated: Calibrated confidence level.
        should_retry: Whether the action should be retried.
    """

    reflection: Reflection
    corrections: List[str] = field(default_factory=list)
    strategy_changes: List[str] = field(default_factory=list)
    similar_past_reflections: List[Reflection] = field(default_factory=list)
    patterns: List[str] = field(default_factory=list)
    confidence_calibrated: ConfidenceLevel = ConfidenceLevel.MEDIUM
    should_retry: bool = False


class ReflectionMemory:
    """Persistent storage and retrieval of reflections.

    Uses SQLite for durable storage with efficient querying
    by tags, error category, severity, and time range.

    Args:
        db_path: Path to SQLite database file.
        max_size: Maximum reflections to keep in memory cache.
    """

    def __init__(self, db_path: str = "reflections.db", max_size: int = 1000) -> None:
        self.db_path = db_path
        self.max_size = max_size
        self._cache: List[Reflection] = []
        self._init_db()

    def _init_db(self) -> None:
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS reflections (
                    reflection_id TEXT PRIMARY KEY,
                    action TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    context TEXT DEFAULT '{}',
                    what_worked TEXT DEFAULT '[]',
                    what_failed TEXT DEFAULT '[]',
                    root_cause TEXT DEFAULT '',
                    error_category TEXT,
                    lessons_learned TEXT DEFAULT '[]',
                    strategy_adjustment TEXT DEFAULT '',
                    confidence REAL DEFAULT 0.5,
                    severity REAL DEFAULT 0.0,
                    created_at REAL NOT NULL,
                    tags TEXT DEFAULT '[]',
                    related_reflection_ids TEXT DEFAULT '[]'
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reflections_created
                ON reflections(created_at)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reflections_category
                ON reflections(error_category)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reflections_severity
                ON reflections(severity)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_reflections_tags
                ON reflections(tags)
            """)
            conn.commit()

    def save(self, reflection: Reflection) -> None:
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO reflections (
                    reflection_id, action, outcome, context, what_worked,
                    what_failed, root_cause, error_category, lessons_learned,
                    strategy_adjustment, confidence, severity, created_at,
                    tags, related_reflection_ids
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    reflection.reflection_id,
                    reflection.action,
                    reflection.outcome,
                    json.dumps(reflection.context),
                    json.dumps(reflection.what_worked),
                    json.dumps(reflection.what_failed),
                    reflection.root_cause,
                    reflection.error_category.value if reflection.error_category else None,
                    json.dumps(reflection.lessons_learned),
                    reflection.strategy_adjustment,
                    reflection.confidence,
                    reflection.severity,
                    reflection.created_at,
                    json.dumps(reflection.tags),
                    json.dumps(reflection.related_reflection_ids),
                ),
            )
            conn.commit()

        self._cache.append(reflection)
        if len(self._cache) > self.max_size:
            self._cache = self._cache[-self.max_size :]

    def get(self, reflection_id: str) -> Optional[Reflection]:
        for r in self._cache:
            if r.reflection_id == reflection_id:
                return r

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            row = conn.execute(
                "SELECT * FROM reflections WHERE reflection_id = ?",
                (reflection_id,),
            ).fetchone()

        if row:
            return Reflection.from_dict(dict(row))
        return None

    def get_recent(self, limit: int = 20) -> List[Reflection]:
        if len(self._cache) >= limit:
            return list(reversed(self._cache[-limit:]))

        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM reflections ORDER BY created_at DESC LIMIT ?",
                (limit,),
            ).fetchall()

        reflections = [Reflection.from_dict(dict(r)) for r in rows]
        for r in reflections:
            if r not in self._cache:
                self._cache.append(r)

        return reflections

    def search_by_tag(self, tag: str, limit: int = 20) -> List[Reflection]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM reflections WHERE tags LIKE ? ORDER BY created_at DESC LIMIT ?",
                (f'%"{tag}"%', limit),
            ).fetchall()

        return [Reflection.from_dict(dict(r)) for r in rows]

    def search_by_category(
        self, category: ErrorCategory, limit: int = 20
    ) -> List[Reflection]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM reflections WHERE error_category = ? ORDER BY created_at DESC LIMIT ?",
                (category.value, limit),
            ).fetchall()

        return [Reflection.from_dict(dict(r)) for r in rows]

    def search_by_severity(
        self, min_severity: float, limit: int = 20
    ) -> List[Reflection]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM reflections WHERE severity >= ? ORDER BY severity DESC LIMIT ?",
                (min_severity, limit),
            ).fetchall()

        return [Reflection.from_dict(dict(r)) for r in rows]

    def search_by_time_range(
        self, start_time: float, end_time: float, limit: int = 100
    ) -> List[Reflection]:
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            rows = conn.execute(
                "SELECT * FROM reflections WHERE created_at BETWEEN ? AND ? ORDER BY created_at DESC LIMIT ?",
                (start_time, end_time, limit),
            ).fetchall()

        return [Reflection.from_dict(dict(r)) for r in rows]

    def get_stats(self) -> Dict[str, Any]:
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM reflections").fetchone()[0]
            avg_confidence = conn.execute(
                "SELECT AVG(confidence) FROM reflections"
            ).fetchone()[0] or 0.0
            avg_severity = conn.execute(
                "SELECT AVG(severity) FROM reflections"
            ).fetchone()[0] or 0.0
            categories = {}
            for row in conn.execute(
                "SELECT error_category, COUNT(*) as cnt FROM reflections GROUP BY error_category"
            ):
                if row[0]:
                    categories[row[0]] = row[1]

        return {
            "total_reflections": total,
            "avg_confidence": round(avg_confidence, 3),
            "avg_severity": round(avg_severity, 3),
            "error_categories": categories,
            "cache_size": len(self._cache),
        }

    def purge_old(self, older_than_days: int = 90) -> int:
        cutoff = time.time() - (older_than_days * 86400)
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "DELETE FROM reflections WHERE created_at < ?", (cutoff,)
            )
            conn.commit()
            deleted = cursor.rowcount

        self._cache = [r for r in self._cache if r.created_at >= cutoff]
        return deleted


class SelfReflectionEngine:
    """Self-reflection engine for post-action learning and correction.

    Analyzes actions and outcomes, identifies root causes, generates
    lessons learned, and adjusts strategies based on accumulated
    reflection memory.

    Args:
        llm_callback: Async callable for LLM interactions.
            Signature: (prompt: str) -> Awaitable[str]
        config: Reflection engine configuration.
        memory: Optional pre-configured reflection memory.
    """

    def __init__(
        self,
        llm_callback: Callable[[str], Awaitable[str]],
        config: Optional[ReflectionConfig] = None,
        memory: Optional[ReflectionMemory] = None,
    ) -> None:
        self.llm_callback = llm_callback
        self.config = config or ReflectionConfig()
        self.memory = memory or ReflectionMemory(
            db_path=self.config.db_path,
            max_size=self.config.max_memory_size,
        )
        self._correction_count = 0

    async def reflect(
        self,
        action: str,
        outcome: str,
        context: Optional[Dict[str, Any]] = None,
        custom_analyzer: Optional[
            Callable[[str, str, Dict[str, Any]], Awaitable[Reflection]]
        ] = None,
    ) -> ReflectionResult:
        """Reflect on an action and its outcome.

        Args:
            action: Description of what was done.
            outcome: What actually happened.
            context: Additional context (metrics, logs, etc.).
            custom_analyzer: Custom reflection analysis function.

        Returns:
            ReflectionResult with analysis and recommendations.
        """
        ctx = context or {}

        if custom_analyzer is not None:
            reflection = await custom_analyzer(action, outcome, ctx)
        else:
            reflection = await self._analyze(action, outcome, ctx)

        similar = self._find_similar_reflections(reflection)
        reflection.related_reflection_ids = [
            s.reflection_id for s in similar[:5]
        ]

        patterns = []
        if self.config.enable_pattern_detection and similar:
            patterns = await self._detect_patterns(reflection, similar)

        corrections = await self._identify_corrections(reflection)
        strategy_changes = await self._generate_strategy_changes(reflection)

        calibrated = self._calibrate_confidence(reflection)

        should_retry = (
            reflection.severity > 0.6
            and self._correction_count < self.config.max_correction_attempts
        )

        result = ReflectionResult(
            reflection=reflection,
            corrections=corrections,
            strategy_changes=strategy_changes,
            similar_past_reflections=similar,
            patterns=patterns,
            confidence_calibrated=calibrated,
            should_retry=should_retry,
        )

        self.memory.save(reflection)

        if reflection.severity >= self.config.min_severity_to_log:
            logger.warning(
                "High-severity reflection: %s (severity=%.2f, category=%s)",
                reflection.root_cause[:80],
                reflection.severity,
                reflection.error_category.value if reflection.error_category else "none",
            )

        return result

    async def self_correct(
        self,
        original_action: str,
        reflection: Reflection,
        custom_corrector: Optional[
            Callable[[str, Reflection], Awaitable[str]]
        ] = None,
    ) -> Optional[str]:
        """Attempt to self-correct based on a reflection.

        Args:
            original_action: The original action to correct.
            reflection: The reflection identifying issues.
            custom_corrector: Custom correction function.

        Returns:
            Corrected action description, or None if no correction needed.
        """
        if reflection.severity < 0.3:
            return None

        if custom_corrector is not None:
            return await custom_corrector(original_action, reflection)

        self._correction_count += 1

        prompt = self._build_correction_prompt(original_action, reflection)
        try:
            return await self.llm_callback(prompt)
        except Exception as e:
            logger.error("Self-correction failed: %s", e)
            return None

    async def get_strategy_adjustment(
        self, reflection: Reflection
    ) -> List[str]:
        """Get strategy adjustments based on a reflection.

        Args:
            reflection: The reflection to base adjustments on.

        Returns:
            List of strategy adjustment recommendations.
        """
        if reflection.strategy_adjustment:
            return [reflection.strategy_adjustment]

        recent = self.memory.get_recent(self.config.confidence_calibration_window)
        if not recent:
            return []

        prompt = self._build_strategy_prompt(reflection, recent)
        try:
            text = await self.llm_callback(prompt)
            return self._parse_strategy_changes(text)
        except Exception as e:
            logger.warning("Strategy adjustment generation failed: %s", e)
            return []

    def get_confidence_calibration(self) -> Dict[str, Any]:
        """Get current confidence calibration metrics.

        Returns:
            Dict with calibration statistics.
        """
        recent = self.memory.get_recent(self.config.confidence_calibration_window)
        if not recent:
            return {
                "calibrated": False,
                "sample_size": 0,
                "avg_confidence": 0.0,
                "accuracy": 0.0,
            }

        avg_confidence = sum(r.confidence for r in recent) / len(recent)
        high_conf_correct = sum(
            1 for r in recent if r.confidence >= 0.8 and r.severity < 0.3
        )
        high_conf_total = sum(1 for r in recent if r.confidence >= 0.8)
        accuracy = (
            high_conf_correct / high_conf_total if high_conf_total > 0 else 0.0
        )

        return {
            "calibrated": len(recent) >= 10,
            "sample_size": len(recent),
            "avg_confidence": round(avg_confidence, 3),
            "accuracy": round(accuracy, 3),
            "overconfident": sum(
                1 for r in recent if r.confidence >= 0.8 and r.severity >= 0.5
            ),
            "underconfident": sum(
                1 for r in recent if r.confidence < 0.4 and r.severity < 0.2
            ),
        }

    def get_learning_summary(self) -> str:
        """Generate a summary of accumulated learning.

        Returns:
            Human-readable learning summary.
        """
        stats = self.memory.get_stats()
        recent = self.memory.get_recent(20)

        lines = [
            "Self-Reflection Learning Summary",
            "=" * 40,
            f"Total reflections: {stats['total_reflections']}",
            f"Average confidence: {stats['avg_confidence']:.2%}",
            f"Average severity: {stats['avg_severity']:.2%}",
            "",
            "Error Categories:",
        ]

        for cat, count in sorted(
            stats["error_categories"].items(), key=lambda x: x[1], reverse=True
        ):
            lines.append(f"  {cat}: {count}")

        lines.append("")
        lines.append("Recent Lessons Learned:")
        lines.append("-" * 40)

        for r in recent[:10]:
            if r.lessons_learned:
                lines.append(f"  [{r.error_category.value if r.error_category else 'info'}] {r.action[:60]}")
                for lesson in r.lessons_learned[:2]:
                    lines.append(f"    - {lesson}")
                lines.append("")

        calibration = self.get_confidence_calibration()
        lines.append("Confidence Calibration:")
        lines.append(f"  Calibrated: {calibration['calibrated']}")
        lines.append(f"  Sample size: {calibration['sample_size']}")
        lines.append(f"  Accuracy at high confidence: {calibration['accuracy']:.2%}")

        return "\n".join(lines)

    async def _analyze(
        self, action: str, outcome: str, context: Dict[str, Any]
    ) -> Reflection:
        prompt = self._build_analysis_prompt(action, outcome, context)
        try:
            text = await self.llm_callback(prompt)
            return self._parse_reflection(text, action, outcome, context)
        except Exception as e:
            logger.warning("Reflection analysis failed: %s", e)
            return Reflection(
                action=action,
                outcome=outcome,
                context=context,
                root_cause=f"Analysis failed: {e}",
                error_category=ErrorCategory.UNKNOWN,
                confidence=0.3,
            )

    async def _identify_corrections(self, reflection: Reflection) -> List[str]:
        if not reflection.what_failed and reflection.severity < 0.3:
            return []

        prompt = self._build_corrections_prompt(reflection)
        try:
            text = await self.llm_callback(prompt)
            return self._parse_corrections(text)
        except Exception as e:
            logger.warning("Correction identification failed: %s", e)
            return []

    async def _generate_strategy_changes(
        self, reflection: Reflection
    ) -> List[str]:
        if not reflection.strategy_adjustment:
            return []

        return [
            line.strip()
            for line in reflection.strategy_adjustment.split("\n")
            if line.strip()
        ]

    async def _detect_patterns(
        self, current: Reflection, similar: List[Reflection]
    ) -> List[str]:
        if len(similar) < 2:
            return []

        prompt = self._build_pattern_prompt(current, similar)
        try:
            text = await self.llm_callback(prompt)
            return self._parse_patterns(text)
        except Exception as e:
            logger.warning("Pattern detection failed: %s", e)
            return []

    def _find_similar_reflections(
        self, reflection: Reflection, limit: int = 5
    ) -> List[Reflection]:
        all_recent = self.memory.get_recent(50)
        if not all_recent:
            return []

        scored: List[Tuple[float, Reflection]] = []
        for r in all_recent:
            if r.reflection_id == reflection.reflection_id:
                continue
            score = self._similarity_score(reflection, r)
            if score > 0.1:
                scored.append((score, r))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [r for _, r in scored[:limit]]

    def _similarity_score(self, a: Reflection, b: Reflection) -> float:
        score = 0.0

        if a.error_category and b.error_category:
            if a.error_category == b.error_category:
                score += 0.3

        a_tags = set(a.tags)
        b_tags = set(b.tags)
        if a_tags and b_tags:
            overlap = len(a_tags & b_tags) / max(len(a_tags | b_tags), 1)
            score += overlap * 0.3

        a_words = set(a.action.lower().split())
        b_words = set(b.action.lower().split())
        if a_words and b_words:
            overlap = len(a_words & b_words) / max(len(a_words | b_words), 1)
            score += overlap * 0.2

        if abs(a.severity - b.severity) < 0.2:
            score += 0.2

        return score

    def _calibrate_confidence(self, reflection: Reflection) -> ConfidenceLevel:
        calibration = self.get_confidence_calibration()
        if not calibration["calibrated"]:
            return ConfidenceLevel.from_score(reflection.confidence)

        if calibration["overconfident"] > calibration["sample_size"] * 0.2:
            adjusted = reflection.confidence * 0.8
            return ConfidenceLevel.from_score(adjusted)

        return ConfidenceLevel.from_score(reflection.confidence)

    def _build_analysis_prompt(
        self, action: str, outcome: str, context: Dict[str, Any]
    ) -> str:
        ctx_str = json.dumps(context, indent=2) if context else "None"

        return (
            f"Action taken: {action}\n\n"
            f"Outcome: {outcome}\n\n"
            f"Context: {ctx_str}\n\n"
            f"Analyze this action and outcome. Provide:\n\n"
            f"WHAT_WORKED:\n- <aspect that succeeded>\n\n"
            f"WHAT_FAILED:\n- <aspect that failed or underperformed>\n\n"
            f"ROOT_CAUSE: <single sentence identifying the root cause>\n\n"
            f"ERROR_CATEGORY: <one of: logic_error, syntax_error, security_issue, "
            f"performance_issue, design_flaw, misunderstanding, incomplete, "
            f"edge_case, dependency_issue, configuration_error, unknown>\n\n"
            f"LESSONS_LEARNED:\n- <key takeaway>\n\n"
            f"STRATEGY_ADJUSTMENT: <how to adjust approach going forward>\n\n"
            f"CONFIDENCE: <0.0-1.0 confidence in this analysis>\n\n"
            f"SEVERITY: <0.0-1.0 severity of issues found>\n"
        )

    def _parse_reflection(
        self, text: str, action: str, outcome: str, context: Dict[str, Any]
    ) -> Reflection:
        reflection = Reflection(
            action=action,
            outcome=outcome,
            context=context,
        )

        lines = text.strip().split("\n")
        current_section = ""
        current_items: List[str] = []

        def _flush_section() -> None:
            nonlocal current_items
            if current_section == "WHAT_WORKED":
                reflection.what_worked = [
                    i.lstrip("-*• ").strip() for i in current_items if i.strip()
                ]
            elif current_section == "WHAT_FAILED":
                reflection.what_failed = [
                    i.lstrip("-*• ").strip() for i in current_items if i.strip()
                ]
            elif current_section == "LESSONS_LEARNED":
                reflection.lessons_learned = [
                    i.lstrip("-*• ").strip() for i in current_items if i.strip()
                ]
            current_items = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("WHAT_WORKED"):
                _flush_section()
                current_section = "WHAT_WORKED"
            elif stripped.startswith("WHAT_FAILED"):
                _flush_section()
                current_section = "WHAT_FAILED"
            elif stripped.startswith("ROOT_CAUSE:"):
                _flush_section()
                reflection.root_cause = stripped[11:].strip()
                current_section = ""
            elif stripped.startswith("ERROR_CATEGORY:"):
                _flush_section()
                cat_str = stripped[15:].strip().lower().replace(" ", "_")
                try:
                    reflection.error_category = ErrorCategory(cat_str)
                except ValueError:
                    reflection.error_category = ErrorCategory.UNKNOWN
                current_section = ""
            elif stripped.startswith("LESSONS_LEARNED"):
                _flush_section()
                current_section = "LESSONS_LEARNED"
            elif stripped.startswith("STRATEGY_ADJUSTMENT:"):
                _flush_section()
                reflection.strategy_adjustment = stripped[20:].strip()
                current_section = ""
            elif stripped.startswith("CONFIDENCE:"):
                _flush_section()
                try:
                    reflection.confidence = float(stripped[11:].strip())
                except ValueError:
                    reflection.confidence = 0.5
                current_section = ""
            elif stripped.startswith("SEVERITY:"):
                _flush_section()
                try:
                    reflection.severity = float(stripped[9:].strip())
                except ValueError:
                    reflection.severity = 0.0
                current_section = ""
            elif current_section and stripped.startswith("-"):
                current_items.append(stripped)
            elif current_section and stripped:
                current_items.append(stripped)

        _flush_section()
        reflection.confidence = max(0.0, min(1.0, reflection.confidence))
        reflection.severity = max(0.0, min(1.0, reflection.severity))

        return reflection

    def _build_corrections_prompt(self, reflection: Reflection) -> str:
        return (
            f"Reflection on action: {reflection.action}\n\n"
            f"What failed:\n"
            + "\n".join(f"- {f}" for f in reflection.what_failed)
            + f"\n\nRoot cause: {reflection.root_cause}\n\n"
            f"List specific corrections needed. Format:\n"
            f"CORRECTION: <specific thing to fix>\n\n"
        )

    def _parse_corrections(self, text: str) -> List[str]:
        corrections: List[str] = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if line.upper().startswith("CORRECTION:"):
                corrections.append(line[11:].strip())
        return corrections

    def _build_strategy_prompt(
        self, reflection: Reflection, recent: List[Reflection]
    ) -> str:
        recent_summary = "\n".join(
            f"- {r.action[:60]}: {r.strategy_adjustment or 'No adjustment'}"
            for r in recent[-10:]
        )

        return (
            f"Current reflection: {reflection.action}\n"
            f"Error: {reflection.error_category.value if reflection.error_category else 'unknown'}\n"
            f"Root cause: {reflection.root_cause}\n\n"
            f"Recent strategy adjustments:\n{recent_summary}\n\n"
            f"Based on this reflection and recent patterns, what strategy "
            f"adjustments should be made? List each as:\n"
            f"STRATEGY: <specific adjustment>\n\n"
        )

    def _parse_strategy_changes(self, text: str) -> List[str]:
        changes: List[str] = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if line.upper().startswith("STRATEGY:"):
                changes.append(line[9:].strip())
        return changes

    def _build_pattern_prompt(
        self, current: Reflection, similar: List[Reflection]
    ) -> List[str]:
        prompt = (
            f"Current reflection: {current.action}\n"
            f"Category: {current.error_category.value if current.error_category else 'unknown'}\n"
            f"Root cause: {current.root_cause}\n\n"
            f"Similar past reflections:\n"
        )
        for s in similar[:5]:
            prompt += (
                f"- {s.action[:60]} | {s.error_category.value if s.error_category else 'unknown'} "
                f"| {s.root_cause[:60]}\n"
            )

        prompt += (
            "\nIdentify any recurring patterns across these reflections. "
            "List each pattern as:\n"
            "PATTERN: <description of recurring pattern>\n\n"
        )
        return prompt

    def _parse_patterns(self, text: str) -> List[str]:
        patterns: List[str] = []
        for line in text.strip().split("\n"):
            line = line.strip()
            if line.upper().startswith("PATTERN:"):
                patterns.append(line[8:].strip())
        return patterns

    def _build_correction_prompt(
        self, original_action: str, reflection: Reflection
    ) -> str:
        return (
            f"Original action: {original_action}\n\n"
            f"Reflection identified these issues:\n"
            f"Root cause: {reflection.root_cause}\n"
            f"What failed:\n"
            + "\n".join(f"- {f}" for f in reflection.what_failed)
            + f"\n\n"
            f"Provide a corrected version of the original action that "
            f"addresses all identified issues. Be specific about what "
            f"changes to make.\n\n"
            f"Corrected action:\n"
        )
