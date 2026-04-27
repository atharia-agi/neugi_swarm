"""
NEUGI v2 Learning Dashboard
=============================

Provides analytics and insights into the learning system's performance,
including skill usage trends, agent improvement tracking, and actionable
optimization recommendations.

Usage:
    dashboard = LearningDashboard("/path/to/learning.db")
    stats = dashboard.get_learning_stats()
    trends = dashboard.get_performance_trends(days=30)
    recommendations = dashboard.get_optimization_recommendations()
"""

from __future__ import annotations

import json
import logging
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# -- Data Classes ------------------------------------------------------------

@dataclass
class LearningStats:
    """Overall learning system statistics.

    Attributes:
        total_patterns_recorded: Total pattern observations.
        total_skills_generated: Number of auto-generated skills.
        total_feedback_entries: Total feedback records.
        patterns_detected: Number of unique patterns identified.
        skills_approved: Number of approved skills.
        avg_pattern_score: Mean pattern usefulness score.
        avg_feedback_rating: Mean feedback rating.
        learning_velocity: New patterns per day (last 7 days).
        generated_at: When these stats were computed (UTC).
    """
    total_patterns_recorded: int
    total_skills_generated: int
    total_feedback_entries: int
    patterns_detected: int
    skills_approved: int
    avg_pattern_score: float
    avg_feedback_rating: float
    learning_velocity: float
    generated_at: datetime

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary."""
        return {
            "total_patterns_recorded": self.total_patterns_recorded,
            "total_skills_generated": self.total_skills_generated,
            "total_feedback_entries": self.total_feedback_entries,
            "patterns_detected": self.patterns_detected,
            "skills_approved": self.skills_approved,
            "avg_pattern_score": round(self.avg_pattern_score, 4),
            "avg_feedback_rating": round(self.avg_feedback_rating, 4),
            "learning_velocity": round(self.learning_velocity, 2),
            "generated_at": self.generated_at.isoformat(),
        }


@dataclass
class PerformanceTrend:
    """Performance trend data over a time window.

    Attributes:
        window_days: Number of days in the trend window.
        data_points: Daily trend data points.
        overall_trend: 'improving', 'stable', or 'degrading'.
        start_rate: Success rate at the start of the window.
        end_rate: Success rate at the end of the window.
        change_percentage: Percentage change over the window.
    """
    window_days: int
    data_points: list[dict[str, Any]]
    overall_trend: str
    start_rate: float
    end_rate: float
    change_percentage: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary."""
        return {
            "window_days": self.window_days,
            "data_points": self.data_points,
            "overall_trend": self.overall_trend,
            "start_rate": round(self.start_rate, 4),
            "end_rate": round(self.end_rate, 4),
            "change_percentage": round(self.change_percentage, 2),
        }


@dataclass
class SkillUsageAnalytics:
    """Analytics for skill usage patterns.

    Attributes:
        skill_name: Name of the skill.
        total_uses: Total times the skill was invoked.
        success_rate: Fraction of successful invocations.
        avg_duration_ms: Mean execution time.
        last_used: Most recent usage timestamp.
        usage_trend: 'increasing', 'stable', or 'decreasing'.
        quality_score: Skill quality assessment (0.0-1.0).
    """
    skill_name: str
    total_uses: int
    success_rate: float
    avg_duration_ms: float
    last_used: datetime
    usage_trend: str
    quality_score: float

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary."""
        return {
            "skill_name": self.skill_name,
            "total_uses": self.total_uses,
            "success_rate": round(self.success_rate, 4),
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "last_used": self.last_used.isoformat(),
            "usage_trend": self.usage_trend,
            "quality_score": round(self.quality_score, 4),
        }


@dataclass
class AgentImprovementReport:
    """Report on agent performance improvement.

    Attributes:
        agent_name: Name of the agent.
        total_tasks: Total tasks executed.
        overall_success_rate: Fraction of successful tasks.
        avg_duration_ms: Mean execution time.
        first_task_date: Date of first recorded task.
        recent_success_rate: Success rate in last 7 days.
        improvement_rate: Change in success rate over time.
        top_skills: Most frequently used skills by this agent.
        recommendations: Suggested improvements.
    """
    agent_name: str
    total_tasks: int
    overall_success_rate: float
    avg_duration_ms: float
    first_task_date: datetime
    recent_success_rate: float
    improvement_rate: float
    top_skills: list[str]
    recommendations: list[str]

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary."""
        return {
            "agent_name": self.agent_name,
            "total_tasks": self.total_tasks,
            "overall_success_rate": round(self.overall_success_rate, 4),
            "avg_duration_ms": round(self.avg_duration_ms, 2),
            "first_task_date": self.first_task_date.isoformat(),
            "recent_success_rate": round(self.recent_success_rate, 4),
            "improvement_rate": round(self.improvement_rate, 4),
            "top_skills": self.top_skills,
            "recommendations": self.recommendations,
        }


@dataclass
class OptimizationRecommendation:
    """A recommendation for system optimization.

    Attributes:
        category: Recommendation category.
        title: Short title.
        description: Detailed explanation.
        priority: 'high', 'medium', or 'low'.
        effort: Estimated effort ('low', 'medium', 'high').
        expected_impact: Expected improvement description.
        data_evidence: Supporting data points.
    """
    category: str
    title: str
    description: str
    priority: str
    effort: str
    expected_impact: str
    data_evidence: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary."""
        return {
            "category": self.category,
            "title": self.title,
            "description": self.description,
            "priority": self.priority,
            "effort": self.effort,
            "expected_impact": self.expected_impact,
            "data_evidence": self.data_evidence,
        }


# -- Learning Dashboard ------------------------------------------------------

class LearningDashboard:
    """Analytics dashboard for the learning system.

    Aggregates data from pattern tracking, skill generation, and
    feedback loops to provide actionable insights about system
    performance and areas for improvement.

    Usage:
        dashboard = LearningDashboard("/path/to/learning.db")
        stats = dashboard.get_learning_stats()
        print(f"Skills generated: {stats.total_skills_generated}")
    """

    def __init__(self, db_path: str) -> None:
        """Initialize the learning dashboard.

        Args:
            db_path: Path to the SQLite database file.
        """
        self._db_path = db_path

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection with row factory.

        Returns:
            Configured sqlite3 connection.
        """
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def get_learning_stats(self) -> LearningStats:
        """Get overall learning system statistics.

        Returns:
            LearningStats snapshot.
        """
        try:
            with self._get_conn() as conn:
                pattern_count = conn.execute(
                    "SELECT COUNT(*) as cnt FROM pattern_records"
                ).fetchone()["cnt"]

                skill_count = conn.execute(
                    "SELECT COUNT(*) as cnt FROM generated_skills"
                ).fetchone()["cnt"]

                feedback_count = conn.execute(
                    "SELECT COUNT(*) as cnt FROM feedback_entries"
                ).fetchone()["cnt"]

                unique_patterns = conn.execute(
                    "SELECT COUNT(DISTINCT pattern_type || ':' || name) as cnt FROM pattern_records"
                ).fetchone()["cnt"]

                approved_skills = conn.execute(
                    """
                    SELECT COUNT(*) as cnt FROM generated_skills
                    WHERE approval_status IN ('approved', 'auto_approved')
                    """
                ).fetchone()["cnt"]

                avg_score_row = conn.execute(
                    """
                    SELECT
                        AVG(quality_overall) as avg_score
                    FROM generated_skills
                    """
                ).fetchone()
                avg_score = avg_score_row["avg_score"] or 0.0

                avg_rating_row = conn.execute(
                    "SELECT AVG(rating) as avg_rating FROM feedback_entries"
                ).fetchone()
                avg_rating = avg_rating_row["avg_rating"] or 0.0

                velocity_row = conn.execute(
                    """
                    SELECT COUNT(DISTINCT pattern_type || ':' || name) as cnt
                    FROM pattern_records
                    WHERE timestamp >= datetime('now', '-7 days')
                    """
                ).fetchone()
                velocity = (velocity_row["cnt"] or 0) / 7.0

                return LearningStats(
                    total_patterns_recorded=pattern_count,
                    total_skills_generated=skill_count,
                    total_feedback_entries=feedback_count,
                    patterns_detected=unique_patterns,
                    skills_approved=approved_skills,
                    avg_pattern_score=avg_score,
                    avg_feedback_rating=avg_rating,
                    learning_velocity=velocity,
                    generated_at=datetime.now(timezone.utc),
                )
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to get learning stats: %s", e)
            now = datetime.now(timezone.utc)
            return LearningStats(
                total_patterns_recorded=0,
                total_skills_generated=0,
                total_feedback_entries=0,
                patterns_detected=0,
                skills_approved=0,
                avg_pattern_score=0.0,
                avg_feedback_rating=0.0,
                learning_velocity=0.0,
                generated_at=now,
            )

    def get_performance_trends(self, days: int = 30) -> PerformanceTrend:
        """Get performance trends over a time window.

        Computes daily success rates from pattern records and feedback
        to show how system performance has evolved.

        Args:
            days: Number of days to look back.

        Returns:
            PerformanceTrend data.
        """
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        DATE(timestamp) as date,
                        COUNT(*) as total,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes
                    FROM pattern_records
                    WHERE timestamp >= datetime('now', ?)
                    GROUP BY DATE(timestamp)
                    ORDER BY date ASC
                    """,
                    (f"-{days} days",),
                ).fetchall()

                data_points = []
                for row in rows:
                    rate = row["successes"] / row["total"] if row["total"] > 0 else 0.0
                    data_points.append({
                        "date": row["date"],
                        "total": row["total"],
                        "successes": row["successes"],
                        "success_rate": round(rate, 4),
                    })

                if len(data_points) >= 2:
                    start_rate = data_points[0]["success_rate"]
                    end_rate = data_points[-1]["success_rate"]

                    if start_rate > 0:
                        change = ((end_rate - start_rate) / start_rate) * 100
                    else:
                        change = 0.0

                    if change > 5:
                        trend = "improving"
                    elif change < -5:
                        trend = "degrading"
                    else:
                        trend = "stable"
                elif data_points:
                    start_rate = data_points[0]["success_rate"]
                    end_rate = data_points[0]["success_rate"]
                    change = 0.0
                    trend = "stable"
                else:
                    start_rate = 0.0
                    end_rate = 0.0
                    change = 0.0
                    trend = "stable"

                return PerformanceTrend(
                    window_days=days,
                    data_points=data_points,
                    overall_trend=trend,
                    start_rate=start_rate,
                    end_rate=end_rate,
                    change_percentage=change,
                )
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to get performance trends: %s", e)
            return PerformanceTrend(
                window_days=days,
                data_points=[],
                overall_trend="stable",
                start_rate=0.0,
                end_rate=0.0,
                change_percentage=0.0,
            )

    def get_skill_usage_analytics(self) -> list[SkillUsageAnalytics]:
        """Get usage analytics for all tracked skills.

        Returns:
            List of SkillUsageAnalytics objects.
        """
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        name,
                        COUNT(*) as total_uses,
                        CAST(SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) as success_rate,
                        AVG(duration_ms) as avg_duration_ms,
                        MAX(timestamp) as last_used
                    FROM pattern_records
                    WHERE pattern_type = 'skill'
                    GROUP BY name
                    ORDER BY total_uses DESC
                    """
                ).fetchall()

                analytics = []
                for row in rows:
                    name = row["name"]
                    total_uses = row["total_uses"]

                    recent_row = conn.execute(
                        """
                        SELECT COUNT(*) as recent_count
                        FROM pattern_records
                        WHERE pattern_type = 'skill'
                          AND name = ?
                          AND timestamp >= datetime('now', '-7 days')
                        """,
                        (name,),
                    ).fetchone()

                    older_row = conn.execute(
                        """
                        SELECT COUNT(*) as older_count
                        FROM pattern_records
                        WHERE pattern_type = 'skill'
                          AND name = ?
                          AND timestamp < datetime('now', '-7 days')
                          AND timestamp >= datetime('now', '-14 days')
                        """,
                        (name,),
                    ).fetchone()

                    recent_count = recent_row["recent_count"] if recent_row else 0
                    older_count = older_row["older_count"] if older_row else 0

                    if older_count > 0:
                        if recent_count > older_count * 1.2:
                            usage_trend = "increasing"
                        elif recent_count < older_count * 0.8:
                            usage_trend = "decreasing"
                        else:
                            usage_trend = "stable"
                    else:
                        usage_trend = "stable"

                    quality_row = conn.execute(
                        """
                        SELECT quality_overall
                        FROM generated_skills
                        WHERE name = ?
                        """,
                        (name,),
                    ).fetchone()
                    quality_score = quality_row["quality_overall"] if quality_row else 0.0

                    analytics.append(SkillUsageAnalytics(
                        skill_name=name,
                        total_uses=total_uses,
                        success_rate=row["success_rate"],
                        avg_duration_ms=row["avg_duration_ms"],
                        last_used=datetime.fromisoformat(row["last_used"]),
                        usage_trend=usage_trend,
                        quality_score=quality_score,
                    ))

                return analytics
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to get skill usage analytics: %s", e)
            return []

    def get_agent_improvement_reports(self) -> list[AgentImprovementReport]:
        """Get improvement reports for all tracked agents.

        Returns:
            List of AgentImprovementReport objects.
        """
        try:
            with self._get_conn() as conn:
                agents = conn.execute(
                    "SELECT DISTINCT name FROM pattern_records WHERE pattern_type = 'agent'"
                ).fetchall()

                reports = []
                for agent_row in agents:
                    agent_name = agent_row["name"]

                    stats = conn.execute(
                        """
                        SELECT
                            COUNT(*) as total_tasks,
                            CAST(SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) as success_rate,
                            AVG(duration_ms) as avg_duration_ms,
                            MIN(timestamp) as first_task
                        FROM pattern_records
                        WHERE pattern_type = 'agent'
                          AND name = ?
                        """,
                        (agent_name,),
                    ).fetchone()

                    if not stats or stats["total_tasks"] == 0:
                        continue

                    recent_stats = conn.execute(
                        """
                        SELECT
                            CAST(SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) as success_rate
                        FROM pattern_records
                        WHERE pattern_type = 'agent'
                          AND name = ?
                          AND timestamp >= datetime('now', '-7 days')
                        """,
                        (agent_name,),
                    ).fetchone()

                    older_stats = conn.execute(
                        """
                        SELECT
                            CAST(SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) as success_rate
                        FROM pattern_records
                        WHERE pattern_type = 'agent'
                          AND name = ?
                          AND timestamp < datetime('now', '-7 days')
                        """,
                        (agent_name,),
                    ).fetchone()

                    recent_rate = recent_stats["success_rate"] if recent_stats and recent_stats["success_rate"] else 0.0
                    older_rate = older_stats["success_rate"] if older_stats and older_stats["success_rate"] else 0.0

                    improvement = recent_rate - older_rate if older_rate > 0 else 0.0

                    top_skills = conn.execute(
                        """
                        SELECT name, COUNT(*) as cnt
                        FROM pattern_records
                        WHERE pattern_type = 'skill'
                        GROUP BY name
                        ORDER BY cnt DESC
                        LIMIT 5
                        """
                    ).fetchall()
                    top_skill_names = [r["name"] for r in top_skills]

                    recommendations = self._generate_agent_recommendations(
                        agent_name, stats, recent_rate, improvement
                    )

                    reports.append(AgentImprovementReport(
                        agent_name=agent_name,
                        total_tasks=stats["total_tasks"],
                        overall_success_rate=stats["success_rate"],
                        avg_duration_ms=stats["avg_duration_ms"],
                        first_task_date=datetime.fromisoformat(stats["first_task"]),
                        recent_success_rate=recent_rate,
                        improvement_rate=improvement,
                        top_skills=top_skill_names,
                        recommendations=recommendations,
                    ))

                return reports
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to get agent improvement reports: %s", e)
            return []

    def _generate_agent_recommendations(
        self,
        agent_name: str,
        stats: sqlite3.Row,
        recent_rate: float,
        improvement: float,
    ) -> list[str]:
        """Generate improvement recommendations for an agent.

        Args:
            agent_name: Name of the agent.
            stats: Aggregated statistics row.
            recent_rate: Recent success rate.
            improvement: Rate of improvement.

        Returns:
            List of recommendation strings.
        """
        recommendations = []

        if stats["success_rate"] < 0.7:
            recommendations.append(
                f"Agent '{agent_name}' has a low overall success rate "
                f"({stats['success_rate']:.0%}). Review task assignments "
                f"and consider additional training data."
            )

        if stats["avg_duration_ms"] > 30000:
            recommendations.append(
                f"Agent '{agent_name}' is slow (avg {stats['avg_duration_ms']:.0f}ms). "
                f"Consider optimizing workflows or using a faster model."
            )

        if improvement < -0.1:
            recommendations.append(
                f"Agent '{agent_name}' is regressing (improvement: {improvement:.0%}). "
                f"Investigate recent changes that may have affected performance."
            )

        if recent_rate > 0.9 and stats["total_tasks"] > 10:
            recommendations.append(
                f"Agent '{agent_name}' is performing well ({recent_rate:.0%} recent). "
                f"Consider assigning more complex tasks."
            )

        if not recommendations:
            recommendations.append(
                f"Agent '{agent_name}' is performing within expected parameters. "
                f"Continue monitoring for trends."
            )

        return recommendations

    def get_optimization_recommendations(self) -> list[OptimizationRecommendation]:
        """Generate optimization recommendations from all data sources.

        Analyzes patterns, skills, and feedback to identify areas
        where the system can be improved.

        Returns:
            List of OptimizationRecommendation objects.
        """
        recommendations = []

        try:
            stats = self.get_learning_stats()
            trends = self.get_performance_trends()
            skill_analytics = self.get_skill_usage_analytics()

            if stats.total_patterns_recorded == 0:
                recommendations.append(OptimizationRecommendation(
                    category="data_collection",
                    title="Enable Pattern Tracking",
                    description=(
                        "No patterns have been recorded yet. Ensure that "
                        "task, tool, skill, and agent executions are being "
                        "tracked to enable learning."
                    ),
                    priority="high",
                    effort="low",
                    expected_impact="Enable all downstream learning features",
                    data_evidence=["total_patterns_recorded=0"],
                ))

            if stats.total_skills_generated == 0 and stats.total_patterns_recorded > 10:
                recommendations.append(OptimizationRecommendation(
                    category="skill_generation",
                    title="Run Skill Generation",
                    description=(
                        f"{stats.total_patterns_recorded} patterns recorded but no "
                        f"skills generated. Run skill generation to convert recurring "
                        f"patterns into reusable skills."
                    ),
                    priority="high",
                    effort="low",
                    expected_impact="Automate recurring tasks with generated skills",
                    data_evidence=[
                        f"total_patterns_recorded={stats.total_patterns_recorded}",
                        "total_skills_generated=0",
                    ],
                ))

            if trends.overall_trend == "degrading":
                recommendations.append(OptimizationRecommendation(
                    category="performance",
                    title="Investigate Performance Degradation",
                    description=(
                        f"System performance is degrading ({trends.change_percentage:.1f}% "
                        f"change over {trends.window_days} days). Review recent changes "
                        f"and check for tool failures."
                    ),
                    priority="high",
                    effort="medium",
                    expected_impact="Restore system performance to baseline levels",
                    data_evidence=[
                        f"trend={trends.overall_trend}",
                        f"change={trends.change_percentage:.1f}%",
                    ],
                ))

            low_quality_skills = [
                s for s in skill_analytics
                if s.quality_score < 0.5 and s.total_uses > 5
            ]
            if low_quality_skills:
                skill_names = ", ".join(s.skill_name for s in low_quality_skills[:3])
                recommendations.append(OptimizationRecommendation(
                    category="skill_quality",
                    title="Improve Low-Quality Skills",
                    description=(
                        f"Skills with low quality scores but high usage: {skill_names}. "
                        f"Review and update these skills to improve reliability."
                    ),
                    priority="medium",
                    effort="medium",
                    expected_impact="Higher success rates for frequently used skills",
                    data_evidence=[
                        f"{s.skill_name}: quality={s.quality_score:.2f}, uses={s.total_uses}"
                        for s in low_quality_skills[:3]
                    ],
                ))

            slow_skills = [
                s for s in skill_analytics
                if s.avg_duration_ms > 10000 and s.total_uses > 3
            ]
            if slow_skills:
                skill_names = ", ".join(s.skill_name for s in slow_skills[:3])
                recommendations.append(OptimizationRecommendation(
                    category="performance",
                    title="Optimize Slow Skills",
                    description=(
                        f"Skills with high execution times: {skill_names}. "
                        f"Consider caching results or simplifying procedures."
                    ),
                    priority="medium",
                    effort="medium",
                    expected_impact="Faster task completion and better user experience",
                    data_evidence=[
                        f"{s.skill_name}: avg={s.avg_duration_ms:.0f}ms"
                        for s in slow_skills[:3]
                    ],
                ))

            if stats.avg_feedback_rating > 0 and stats.avg_feedback_rating < 3.5:
                recommendations.append(OptimizationRecommendation(
                    category="quality",
                    title="Improve Overall Quality",
                    description=(
                        f"Average feedback rating is {stats.avg_feedback_rating:.2f}/5.0. "
                        f"Review low-rated tasks and skills to identify quality issues."
                    ),
                    priority="high",
                    effort="high",
                    expected_impact="Better user satisfaction and task outcomes",
                    data_evidence=[
                        f"avg_feedback_rating={stats.avg_feedback_rating:.2f}",
                    ],
                ))

            if stats.learning_velocity < 0.5 and stats.total_patterns_recorded > 20:
                recommendations.append(OptimizationRecommendation(
                    category="learning",
                    title="Increase Learning Activity",
                    description=(
                        f"Learning velocity is low ({stats.learning_velocity:.1f} new "
                        f"patterns/day) despite {stats.total_patterns_recorded} total "
                        f"patterns. Ensure pattern tracking is active across all systems."
                    ),
                    priority="low",
                    effort="low",
                    expected_impact="More patterns detected and skills generated",
                    data_evidence=[
                        f"learning_velocity={stats.learning_velocity:.1f}",
                        f"total_patterns={stats.total_patterns_recorded}",
                    ],
                ))

            priority_order = {"high": 3, "medium": 2, "low": 1}
            recommendations.sort(
                key=lambda r: priority_order.get(r.priority, 0),
                reverse=True,
            )

        except Exception as e:
            logger.error("Failed to generate optimization recommendations: %s", e)

        return recommendations

    def get_pattern_type_distribution(self) -> dict[str, int]:
        """Get the distribution of patterns by type.

        Returns:
            Dict mapping pattern type to count.
        """
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT pattern_type, COUNT(*) as cnt
                    FROM pattern_records
                    GROUP BY pattern_type
                    ORDER BY cnt DESC
                    """
                ).fetchall()

                return {row["pattern_type"]: row["cnt"] for row in rows}
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to get pattern type distribution: %s", e)
            return {}

    def get_top_performing_tools(self, limit: int = 10) -> list[dict[str, Any]]:
        """Get the best-performing tools by success rate and speed.

        Args:
            limit: Maximum number of tools to return.

        Returns:
            List of tool performance dicts.
        """
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        name,
                        COUNT(*) as total_uses,
                        CAST(SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) as success_rate,
                        AVG(duration_ms) as avg_duration_ms
                    FROM pattern_records
                    WHERE pattern_type = 'tool'
                    GROUP BY name
                    HAVING total_uses >= 3
                    ORDER BY success_rate DESC, avg_duration_ms ASC
                    LIMIT ?
                    """,
                    (limit,),
                ).fetchall()

                return [
                    {
                        "name": row["name"],
                        "total_uses": row["total_uses"],
                        "success_rate": round(row["success_rate"], 4),
                        "avg_duration_ms": round(row["avg_duration_ms"], 2),
                    }
                    for row in rows
                ]
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to get top performing tools: %s", e)
            return []

    def close(self) -> None:
        """No-op for API compatibility."""
        pass
