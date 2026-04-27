"""
NEUGI v2 Auto-Learning System
==============================

Combines patterns from OpenClaw's skill workshop, auto-learner, and continuous
learning to enable self-improving agent behavior.

Subsystems:
- PatternTracker: Detects and scores recurring task/tool/skill patterns
- SkillGenerator: Auto-generates SKILL.md files from observed procedures
- FeedbackLoop: Collects feedback and auto-tunes parameters
- LearningDashboard: Analytics and recommendations

Usage:
    from neugi_swarm_v2.learning import LearningSystem

    system = LearningSystem(base_dir="/path/to/neugi")
    system.track_tool_use("file_search", success=True, duration_ms=150)
    system.track_task("code_review", success=True, duration_ms=5000)
    system.record_feedback("skill:git-workflow", rating=5)
    system.check_for_new_skills()

    dashboard = system.get_dashboard()
    stats = dashboard.get_learning_stats()
"""

from __future__ import annotations

from neugi_swarm_v2.learning.pattern_tracker import (
    PatternTracker,
    PatternRecord,
    PatternType,
    PatternScore,
    PatternSequence,
    PatternDetectionResult,
)

from neugi_swarm_v2.learning.skill_generator import (
    SkillGenerator,
    GeneratedSkill,
    SkillQualityScore,
    SkillApprovalStatus,
    SkillVersion,
)

from neugi_swarm_v2.learning.feedback_loop import (
    FeedbackLoop,
    FeedbackEntry,
    FeedbackType,
    FeedbackSummary,
    TuningRecommendation,
    DegradationAlert,
)

from neugi_swarm_v2.learning.dashboard import (
    LearningDashboard,
    LearningStats,
    PerformanceTrend,
    SkillUsageAnalytics,
    AgentImprovementReport,
    OptimizationRecommendation,
)


__all__ = [
    "LearningSystem",
    "PatternTracker",
    "PatternRecord",
    "PatternType",
    "PatternScore",
    "PatternSequence",
    "PatternDetectionResult",
    "SkillGenerator",
    "GeneratedSkill",
    "SkillQualityScore",
    "SkillApprovalStatus",
    "SkillVersion",
    "FeedbackLoop",
    "FeedbackEntry",
    "FeedbackType",
    "FeedbackSummary",
    "TuningRecommendation",
    "DegradationAlert",
    "LearningDashboard",
    "LearningStats",
    "PerformanceTrend",
    "SkillUsageAnalytics",
    "AgentImprovementReport",
    "OptimizationRecommendation",
]


class LearningSystem:
    """Unified entry point for the NEUGI v2 Auto-Learning System.

    Coordinates pattern tracking, skill generation, feedback collection,
    and dashboard analytics into a single cohesive system.

    Usage:
        system = LearningSystem(base_dir="/path/to/neugi")
        system.track_task("deploy", success=True, duration_ms=30000)
        system.record_feedback("task:deploy", rating=4)
        new_skills = system.check_for_new_skills()
    """

    def __init__(self, base_dir: str | None = None, db_path: str | None = None) -> None:
        """Initialize all learning subsystems.

        Args:
            base_dir: Root directory for NEUGI data. Defaults to ~/.neugi.
            db_path: Explicit path to the learning SQLite database.
        """
        import os
        from pathlib import Path

        if base_dir:
            self._base_dir = Path(base_dir)
        else:
            self._base_dir = Path.home() / ".neugi"

        self._base_dir.mkdir(parents=True, exist_ok=True)

        if db_path:
            self._db_path = db_path
        else:
            learning_dir = self._base_dir / "learning"
            learning_dir.mkdir(parents=True, exist_ok=True)
            self._db_path = str(learning_dir / "learning.db")

        self.pattern_tracker = PatternTracker(self._db_path)
        self.skill_generator = SkillGenerator(self._db_path)
        self.feedback_loop = FeedbackLoop(self._db_path)
        self.dashboard = LearningDashboard(self._db_path)

    def track_task(
        self,
        task_name: str,
        success: bool,
        duration_ms: float,
        metadata: dict | None = None,
    ) -> PatternRecord:
        """Track a task execution for pattern analysis.

        Args:
            task_name: Identifier for the task (e.g. 'code_review', 'deploy').
            success: Whether the task completed successfully.
            duration_ms: Execution time in milliseconds.
            metadata: Optional extra context.

        Returns:
            The created PatternRecord.
        """
        return self.pattern_tracker.record_task_pattern(
            task_name, success, duration_ms, metadata or {}
        )

    def track_tool_use(
        self,
        tool_name: str,
        success: bool,
        duration_ms: float,
        metadata: dict | None = None,
    ) -> PatternRecord:
        """Track a tool invocation for pattern analysis.

        Args:
            tool_name: Name of the tool used.
            success: Whether the tool call succeeded.
            duration_ms: Execution time in milliseconds.
            metadata: Optional extra context.

        Returns:
            The created PatternRecord.
        """
        return self.pattern_tracker.record_tool_pattern(
            tool_name, success, duration_ms, metadata or {}
        )

    def track_skill_use(
        self,
        skill_name: str,
        success: bool,
        duration_ms: float,
        metadata: dict | None = None,
    ) -> PatternRecord:
        """Track a skill invocation for pattern analysis.

        Args:
            skill_name: Name of the skill used.
            success: Whether the skill execution succeeded.
            duration_ms: Execution time in milliseconds.
            metadata: Optional extra context.

        Returns:
            The created PatternRecord.
        """
        return self.pattern_tracker.record_skill_pattern(
            skill_name, success, duration_ms, metadata or {}
        )

    def track_agent_performance(
        self,
        agent_name: str,
        success: bool,
        duration_ms: float,
        metadata: dict | None = None,
    ) -> PatternRecord:
        """Track an agent execution for pattern analysis.

        Args:
            agent_name: Name of the agent.
            success: Whether the agent task succeeded.
            duration_ms: Execution time in milliseconds.
            metadata: Optional extra context.

        Returns:
            The created PatternRecord.
        """
        return self.pattern_tracker.record_agent_pattern(
            agent_name, success, duration_ms, metadata or {}
        )

    def record_sequence(self, sequence: list[str], success: bool) -> PatternSequence:
        """Record a sequence of actions for pattern detection.

        Args:
            sequence: Ordered list of action names.
            success: Whether the sequence completed successfully.

        Returns:
            The created PatternSequence.
        """
        return self.pattern_tracker.record_sequence(sequence, success)

    def check_for_new_skills(
        self,
        min_occurrences: int = 3,
        min_success_rate: float = 0.7,
        auto_approve_threshold: float = 0.9,
    ) -> list[GeneratedSkill]:
        """Detect recurring patterns and generate new skills.

        Args:
            min_occurrences: Minimum times a pattern must appear.
            min_success_rate: Minimum success rate to qualify.
            auto_approve_threshold: Score above which skills are auto-approved.

        Returns:
            List of newly generated skills.
        """
        return self.skill_generator.generate_skills_from_patterns(
            min_occurrences, min_success_rate, auto_approve_threshold
        )

    def record_feedback(
        self,
        target: str,
        rating: float,
        feedback_type: str = "explicit",
        comment: str = "",
    ) -> FeedbackEntry:
        """Record user feedback for a target.

        Args:
            target: What the feedback is about (e.g. 'skill:git-workflow').
            rating: Numeric rating (1-5).
            feedback_type: 'explicit' or 'implicit'.
            comment: Optional free-text feedback.

        Returns:
            The created FeedbackEntry.
        """
        return self.feedback_loop.record_feedback(target, rating, feedback_type, comment)

    def get_tuning_recommendations(self) -> list[TuningRecommendation]:
        """Get parameter tuning recommendations based on feedback.

        Returns:
            List of tuning recommendations.
        """
        return self.feedback_loop.get_tuning_recommendations()

    def get_learning_stats(self) -> LearningStats:
        """Get overall learning statistics.

        Returns:
            LearningStats snapshot.
        """
        return self.dashboard.get_learning_stats()

    def get_performance_trends(self, days: int = 30) -> PerformanceTrend:
        """Get performance trends over a time window.

        Args:
            days: Number of days to look back.

        Returns:
            PerformanceTrend data.
        """
        return self.dashboard.get_performance_trends(days)

    def get_optimization_recommendations(self) -> list[OptimizationRecommendation]:
        """Get recommendations for system optimization.

        Returns:
            List of optimization recommendations.
        """
        return self.dashboard.get_optimization_recommendations()

    def close(self) -> None:
        """Close database connections."""
        self.pattern_tracker.close()
        self.skill_generator.close()
        self.feedback_loop.close()
        self.dashboard.close()

    def __enter__(self) -> "LearningSystem":
        return self

    def __exit__(self, *args) -> None:
        self.close()
