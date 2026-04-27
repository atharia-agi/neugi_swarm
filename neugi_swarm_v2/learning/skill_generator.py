"""
NEUGI v2 Skill Generator
=========================

Auto-generates SKILL.md files and supporting scripts from observed
recurring task patterns. Detects patterns that have been successfully
used 3+ times and converts them into reusable skill definitions.

Usage:
    generator = SkillGenerator("/path/to/learning.db")
    new_skills = generator.generate_skills_from_patterns(
        min_occurrences=3,
        min_success_rate=0.7,
        auto_approve_threshold=0.9,
    )
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Optional

logger = logging.getLogger(__name__)


# -- Enums -------------------------------------------------------------------

class SkillApprovalStatus(Enum):
    """Approval state for a generated skill."""
    PENDING = "pending"
    AUTO_APPROVED = "auto_approved"
    REQUIRES_REVIEW = "requires_review"
    APPROVED = "approved"
    REJECTED = "rejected"


# -- Data Classes ------------------------------------------------------------

@dataclass
class SkillQualityScore:
    """Quality assessment of a generated skill.

    Attributes:
        completeness: How complete the skill definition is (0.0-1.0).
        clarity: How clear and unambiguous the instructions are (0.0-1.0).
        usefulness: How likely the skill will be useful (0.0-1.0).
        overall: Weighted composite score (0.0-1.0).
    """
    completeness: float
    clarity: float
    usefulness: float
    overall: float

    @classmethod
    def compute(
        cls,
        occurrence_count: int,
        success_rate: float,
        has_trigger: bool,
        has_steps: bool,
        has_examples: bool,
        has_output_format: bool,
    ) -> "SkillQualityScore":
        """Compute quality scores from pattern data.

        Args:
            occurrence_count: How many times the pattern was observed.
            success_rate: Fraction of successful executions.
            has_trigger: Whether a trigger pattern was detected.
            has_steps: Whether procedural steps were extracted.
            has_examples: Whether example inputs/outputs exist.
            has_output_format: Whether output format is defined.

        Returns:
            SkillQualityScore with all components.
        """
        completeness = 0.0
        if has_trigger:
            completeness += 0.25
        if has_steps:
            completeness += 0.35
        if has_examples:
            completeness += 0.20
        if has_output_format:
            completeness += 0.20
        completeness = min(completeness, 1.0)

        clarity = min(success_rate * 0.6 + (0.4 if has_steps else 0.0), 1.0)

        frequency_factor = min(occurrence_count / 10.0, 1.0)
        usefulness = (success_rate * 0.5 + frequency_factor * 0.5)

        overall = (
            completeness * 0.35
            + clarity * 0.30
            + usefulness * 0.35
        )

        return cls(
            completeness=round(completeness, 4),
            clarity=round(clarity, 4),
            usefulness=round(usefulness, 4),
            overall=round(overall, 4),
        )


@dataclass
class SkillVersion:
    """Version information for a generated skill.

    Attributes:
        version: Semantic version string (e.g. '1.0.0').
        created_at: When this version was created (UTC).
        changes: Description of what changed in this version.
        source_pattern: Name of the pattern this version was generated from.
    """
    version: str
    created_at: datetime
    changes: str
    source_pattern: str

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary."""
        return {
            "version": self.version,
            "created_at": self.created_at.isoformat(),
            "changes": self.changes,
            "source_pattern": self.source_pattern,
        }


@dataclass
class GeneratedSkill:
    """A skill auto-generated from observed patterns.

    Attributes:
        id: Unique identifier (auto-assigned by DB).
        name: Skill name (slug, e.g. 'code-review').
        title: Human-readable title.
        description: What the skill does.
        trigger_pattern: Pattern that activates this skill.
        steps: Ordered list of procedural steps.
        examples: Example input/output pairs.
        output_format: Expected output format description.
        quality_score: Quality assessment.
        approval_status: Current approval state.
        version: Current version info.
        created_at: When the skill was first generated (UTC).
        updated_at: When the skill was last updated (UTC).
        metadata: Additional context.
    """
    name: str
    title: str
    description: str
    trigger_pattern: str
    steps: list[str]
    quality_score: SkillQualityScore
    approval_status: SkillApprovalStatus = SkillApprovalStatus.PENDING
    examples: list[dict[str, str]] = field(default_factory=list)
    output_format: str = ""
    version: Optional[SkillVersion] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_skill_md(self) -> str:
        """Generate SKILL.md content for this skill.

        Returns:
            Markdown-formatted skill definition.
        """
        lines = [
            f"# {self.title}",
            "",
            self.description,
            "",
            "## Trigger",
            "",
            self.trigger_pattern,
            "",
            "## Steps",
            "",
        ]

        for i, step in enumerate(self.steps, 1):
            lines.append(f"{i}. {step}")

        lines.append("")

        if self.examples:
            lines.append("## Examples")
            lines.append("")
            for ex in self.examples:
                input_text = ex.get("input", "")
                output_text = ex.get("output", "")
                lines.append(f"**Input:** {input_text}")
                lines.append("")
                lines.append(f"**Output:** {output_text}")
                lines.append("")

        if self.output_format:
            lines.append("## Output Format")
            lines.append("")
            lines.append(self.output_format)
            lines.append("")

        lines.append("## Quality")
        lines.append("")
        lines.append(f"- **Completeness:** {self.quality_score.completeness:.0%}")
        lines.append(f"- **Clarity:** {self.quality_score.clarity:.0%}")
        lines.append(f"- **Usefulness:** {self.quality_score.usefulness:.0%}")
        lines.append(f"- **Overall:** {self.quality_score.overall:.0%}")
        lines.append("")

        if self.version:
            lines.append(f"## Version: {self.version.version}")
            lines.append(f"Created: {self.version.created_at.isoformat()}")
            lines.append(f"Changes: {self.version.changes}")
            lines.append("")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a dictionary."""
        return {
            "id": self.id,
            "name": self.name,
            "title": self.title,
            "description": self.description,
            "trigger_pattern": self.trigger_pattern,
            "steps": self.steps,
            "examples": self.examples,
            "output_format": self.output_format,
            "quality_score": {
                "completeness": self.quality_score.completeness,
                "clarity": self.quality_score.clarity,
                "usefulness": self.quality_score.usefulness,
                "overall": self.quality_score.overall,
            },
            "approval_status": self.approval_status.value,
            "version": self.version.to_dict() if self.version else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "metadata": self.metadata,
        }


# -- Skill Generator ---------------------------------------------------------

class SkillGenerator:
    """Auto-generates skills from observed recurring patterns.

    Monitors the pattern tracker for sequences that have been successfully
    executed multiple times. When a pattern meets the quality threshold,
    generates a SKILL.md file and optional helper scripts.

    Usage:
        generator = SkillGenerator("/path/to/learning.db")
        skills = generator.generate_skills_from_patterns(
            min_occurrences=3,
            min_success_rate=0.7,
        )
    """

    def __init__(self, db_path: str, skills_dir: str | None = None) -> None:
        """Initialize the skill generator.

        Args:
            db_path: Path to the learning SQLite database.
            skills_dir: Directory to write generated SKILL.md files.
        """
        self._db_path = db_path
        self._skills_dir = skills_dir or str(Path(db_path).parent / "generated_skills")
        self._init_db()

    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection with row factory.

        Returns:
            Configured sqlite3 connection.
        """
        conn = sqlite3.connect(self._db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _init_db(self) -> None:
        """Create database tables if they don't exist."""
        try:
            Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
            with self._get_conn() as conn:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS generated_skills (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        name TEXT NOT NULL UNIQUE,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL,
                        trigger_pattern TEXT NOT NULL,
                        steps TEXT NOT NULL DEFAULT '[]',
                        examples TEXT NOT NULL DEFAULT '[]',
                        output_format TEXT DEFAULT '',
                        quality_completeness REAL NOT NULL,
                        quality_clarity REAL NOT NULL,
                        quality_usefulness REAL NOT NULL,
                        quality_overall REAL NOT NULL,
                        approval_status TEXT NOT NULL DEFAULT 'pending',
                        version TEXT NOT NULL DEFAULT '1.0.0',
                        version_changes TEXT DEFAULT 'Initial auto-generation',
                        source_pattern TEXT NOT NULL,
                        created_at TEXT NOT NULL,
                        updated_at TEXT NOT NULL,
                        metadata TEXT DEFAULT '{}'
                    );

                    CREATE INDEX IF NOT EXISTS idx_skill_name
                        ON generated_skills(name);
                    CREATE INDEX IF NOT EXISTS idx_skill_status
                        ON generated_skills(approval_status);
                    CREATE INDEX IF NOT EXISTS idx_skill_score
                        ON generated_skills(quality_overall);
                """)
        except OSError as e:
            logger.error("Failed to initialize skill generator DB: %s", e)

    def generate_skills_from_patterns(
        self,
        min_occurrences: int = 3,
        min_success_rate: float = 0.7,
        auto_approve_threshold: float = 0.9,
    ) -> list[GeneratedSkill]:
        """Detect qualifying patterns and generate skills from them.

        Scans all pattern types for recurring sequences that meet the
        minimum occurrence and success rate thresholds. Generates a
        GeneratedSkill for each qualifying pattern.

        Args:
            min_occurrences: Minimum times a pattern must have occurred.
            min_success_rate: Minimum success rate (0.0-1.0).
            auto_approve_threshold: Score above which skills are auto-approved.

        Returns:
            List of newly generated GeneratedSkill objects.
        """
        try:
            with self._get_conn() as conn:
                rows = conn.execute(
                    """
                    SELECT
                        name,
                        pattern_type,
                        COUNT(*) as occurrence_count,
                        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
                        AVG(duration_ms) as avg_duration_ms,
                        MIN(timestamp) as first_seen,
                        MAX(timestamp) as last_seen,
                        GROUP_CONCAT(DISTINCT metadata) as metadata_samples
                    FROM pattern_records
                    GROUP BY pattern_type, name
                    HAVING COUNT(*) >= ?
                       AND (CAST(SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*)) >= ?
                    ORDER BY occurrence_count DESC
                    """,
                    (min_occurrences, min_success_rate),
                ).fetchall()

                new_skills = []
                for row in rows:
                    name = row["name"]

                    existing = conn.execute(
                        "SELECT id FROM generated_skills WHERE name = ?",
                        (name,),
                    ).fetchone()

                    if existing:
                        continue

                    skill = self._generate_skill_from_row(row, auto_approve_threshold)
                    if skill:
                        self._save_skill(skill)
                        new_skills.append(skill)

                return new_skills
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to generate skills from patterns: %s", e)
            return []

    def _generate_skill_from_row(
        self,
        row: sqlite3.Row,
        auto_approve_threshold: float,
    ) -> Optional[GeneratedSkill]:
        """Create a GeneratedSkill from a database row.

        Args:
            row: Database row with aggregated pattern data.
            auto_approve_threshold: Score for auto-approval.

        Returns:
            GeneratedSkill or None if generation fails.
        """
        try:
            name = row["name"]
            pattern_type = row["pattern_type"]
            occurrence_count = row["occurrence_count"]
            success_count = row["success_count"]
            success_rate = success_count / occurrence_count if occurrence_count > 0 else 0.0

            trigger = self._infer_trigger(name, pattern_type)
            steps = self._infer_steps(name, pattern_type, row)
            examples = self._infer_examples(row)
            output_format = self._infer_output_format(name, pattern_type)

            has_trigger = bool(trigger)
            has_steps = bool(steps)
            has_examples = bool(examples)
            has_output = bool(output_format)

            quality = SkillQualityScore.compute(
                occurrence_count=occurrence_count,
                success_rate=success_rate,
                has_trigger=has_trigger,
                has_steps=has_steps,
                has_examples=has_examples,
                has_output_format=has_output,
            )

            if quality.overall >= auto_approve_threshold:
                status = SkillApprovalStatus.AUTO_APPROVED
            else:
                status = SkillApprovalStatus.REQUIRES_REVIEW

            now = datetime.now(timezone.utc)
            version = SkillVersion(
                version="1.0.0",
                created_at=now,
                changes="Initial auto-generation from observed patterns",
                source_pattern=name,
            )

            return GeneratedSkill(
                name=name,
                title=self._infer_title(name),
                description=self._infer_description(name, pattern_type, occurrence_count, success_rate),
                trigger_pattern=trigger,
                steps=steps,
                examples=examples,
                output_format=output_format,
                quality_score=quality,
                approval_status=status,
                version=version,
                created_at=now,
                updated_at=now,
                metadata={
                    "pattern_type": pattern_type,
                    "occurrence_count": occurrence_count,
                    "success_rate": success_rate,
                    "avg_duration_ms": row["avg_duration_ms"],
                },
            )
        except Exception as e:
            logger.error("Failed to generate skill from row: %s", e)
            return None

    def _infer_trigger(self, name: str, pattern_type: str) -> str:
        """Infer a trigger pattern from the pattern name and type.

        Args:
            name: Pattern identifier.
            pattern_type: Category of the pattern.

        Returns:
            Trigger description string.
        """
        triggers = {
            "task": f"When the user requests to {name.replace('_', ' ')}",
            "tool": f"When the {name} tool is needed",
            "skill": f"When the {name} skill is applicable",
            "agent": f"When the {name} agent should handle the task",
        }
        return triggers.get(pattern_type, f"When {name} is needed")

    def _infer_steps(
        self,
        name: str,
        pattern_type: str,
        row: sqlite3.Row,
    ) -> list[str]:
        """Infer procedural steps from pattern metadata.

        Args:
            name: Pattern identifier.
            pattern_type: Category of the pattern.
            row: Database row with pattern data.

        Returns:
            List of inferred step descriptions.
        """
        steps = []

        try:
            metadata_samples = row.get("metadata_samples", "")
            if metadata_samples:
                all_metadata = []
                for sample in metadata_samples.split(","):
                    sample = sample.strip()
                    if sample.startswith("{"):
                        try:
                            all_metadata.append(json.loads(sample))
                        except json.JSONDecodeError:
                            pass

                common_keys = set()
                if all_metadata:
                    common_keys = set(all_metadata[0].keys())
                    for m in all_metadata[1:]:
                        common_keys &= set(m.keys())

                for key in sorted(common_keys):
                    steps.append(f"Process {key} from input")
        except Exception:
            pass

        if not steps:
            steps = [
                f"Identify the {name.replace('_', ' ')} requirements",
                f"Execute the {name.replace('_', ' ')} procedure",
                f"Verify the {name.replace('_', ' ')} output",
            ]

        return steps

    def _infer_examples(self, row: sqlite3.Row) -> list[dict[str, str]]:
        """Infer examples from pattern metadata.

        Args:
            row: Database row with pattern data.

        Returns:
            List of example dicts with 'input' and 'output' keys.
        """
        examples = []
        try:
            metadata_samples = row.get("metadata_samples", "")
            if metadata_samples:
                samples = metadata_samples.split(",")
                for sample in samples[:3]:
                    sample = sample.strip()
                    if sample.startswith("{"):
                        try:
                            data = json.loads(sample)
                            examples.append({
                                "input": json.dumps(data, indent=2),
                                "output": "Successful execution",
                            })
                        except json.JSONDecodeError:
                            pass
        except Exception:
            pass

        return examples

    def _infer_output_format(self, name: str, pattern_type: str) -> str:
        """Infer the expected output format.

        Args:
            name: Pattern identifier.
            pattern_type: Category of the pattern.

        Returns:
            Output format description.
        """
        formats = {
            "task": f"Completion status and results of the {name.replace('_', ' ')} task",
            "tool": f"Tool output from {name}",
            "skill": f"Skill execution report for {name}",
            "agent": f"Agent {name} response and status",
        }
        return formats.get(pattern_type, f"Results from {name}")

    def _infer_title(self, name: str) -> str:
        """Convert a slug name to a human-readable title.

        Args:
            name: Skill slug (e.g. 'code_review').

        Returns:
            Human-readable title (e.g. 'Code Review').
        """
        return name.replace("_", " ").title()

    def _infer_description(
        self,
        name: str,
        pattern_type: str,
        occurrence_count: int,
        success_rate: float,
    ) -> str:
        """Generate a skill description from pattern data.

        Args:
            name: Pattern identifier.
            pattern_type: Category of the pattern.
            occurrence_count: Times the pattern was observed.
            success_rate: Success rate of the pattern.

        Returns:
            Description string.
        """
        readable = name.replace("_", " ")
        return (
            f"Auto-generated skill for {readable} operations. "
            f"Observed {occurrence_count} times with {success_rate:.0%} success rate. "
            f"Pattern type: {pattern_type}."
        )

    def _save_skill(self, skill: GeneratedSkill) -> None:
        """Save a generated skill to the database.

        Args:
            skill: The GeneratedSkill to persist.
        """
        try:
            with self._get_conn() as conn:
                cursor = conn.execute(
                    """
                    INSERT INTO generated_skills (
                        name, title, description, trigger_pattern, steps,
                        examples, output_format, quality_completeness,
                        quality_clarity, quality_usefulness, quality_overall,
                        approval_status, version, version_changes, source_pattern,
                        created_at, updated_at, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        skill.name,
                        skill.title,
                        skill.description,
                        skill.trigger_pattern,
                        json.dumps(skill.steps),
                        json.dumps(skill.examples),
                        skill.output_format,
                        skill.quality_score.completeness,
                        skill.quality_score.clarity,
                        skill.quality_score.usefulness,
                        skill.quality_score.overall,
                        skill.approval_status.value,
                        skill.version.version if skill.version else "1.0.0",
                        skill.version.changes if skill.version else "",
                        skill.version.source_pattern if skill.version else skill.name,
                        skill.created_at.isoformat() if skill.created_at else "",
                        skill.updated_at.isoformat() if skill.updated_at else "",
                        json.dumps(skill.metadata),
                    ),
                )
                skill.id = cursor.lastrowid

                self._write_skill_md(skill)
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to save skill %s: %s", skill.name, e)

    def _write_skill_md(self, skill: GeneratedSkill) -> None:
        """Write a SKILL.md file for the generated skill.

        Args:
            skill: The GeneratedSkill to write.
        """
        try:
            skill_dir = Path(self._skills_dir) / skill.name
            skill_dir.mkdir(parents=True, exist_ok=True)

            skill_md_path = skill_dir / "SKILL.md"
            with open(skill_md_path, "w", encoding="utf-8") as f:
                f.write(skill.to_skill_md())

            if skill.examples:
                scripts_dir = skill_dir / "scripts"
                scripts_dir.mkdir(parents=True, exist_ok=True)

                script_path = scripts_dir / "example.py"
                with open(script_path, "w", encoding="utf-8") as f:
                    f.write(self._generate_example_script(skill))
        except OSError as e:
            logger.error("Failed to write SKILL.md for %s: %s", skill.name, e)

    def _generate_example_script(self, skill: GeneratedSkill) -> str:
        """Generate an example Python script for the skill.

        Args:
            skill: The GeneratedSkill.

        Returns:
            Python script content.
        """
        lines = [
            f'"""Example script for {skill.title} skill."""',
            "",
            "",
            f"def run_{skill.name}() -> dict:",
            f'    """Execute the {skill.name} procedure."""',
        ]

        for i, step in enumerate(skill.steps, 1):
            lines.append(f"    # Step {i}: {step}")
            # Generate a meaningful implementation hint based on step keywords
            step_lower = step.lower()
            if any(kw in step_lower for kw in ["read", "load", "fetch", "get", "download"]):
                lines.append(f"    # Implementation: Read/load data from source")
                lines.append(f"    data_{i} = None  # Replace with actual data loading")
            elif any(kw in step_lower for kw in ["write", "save", "store", "export"]):
                lines.append(f"    # Implementation: Write/save output to destination")
                lines.append(f"    # save_output(result, destination)")
            elif any(kw in step_lower for kw in ["process", "transform", "convert", "parse"]):
                lines.append(f"    # Implementation: Process/transform the data")
                lines.append(f"    processed_{i} = data  # Replace with actual processing logic")
            elif any(kw in step_lower for kw in ["check", "validate", "verify", "test"]):
                lines.append(f"    # Implementation: Validate inputs/outputs")
                lines.append(f"    # assert condition, 'Validation failed'")
            elif any(kw in step_lower for kw in ["send", "notify", "call", "request"]):
                lines.append(f"    # Implementation: Send/notify/call external service")
                lines.append(f"    # response = send_request(payload)")
            else:
                lines.append(f"    # Implementation: {step}")
                lines.append(f"    # Add your implementation here")
            lines.append("")

        lines.extend([
            "    return {",
            f'        "status": "success",',
            f'        "skill": "{skill.name}",',
            "    }",
            "",
            "",
            'if __name__ == "__main__":',
            f"    result = run_{skill.name}()",
            '    print(f"Result: {result}")',
            "",
        ])

        return "\n".join(lines)

    def get_skill(self, name: str) -> Optional[GeneratedSkill]:
        """Retrieve a generated skill by name.

        Args:
            name: Skill name.

        Returns:
            GeneratedSkill or None if not found.
        """
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT * FROM generated_skills WHERE name = ?",
                    (name,),
                ).fetchone()

                if not row:
                    return None

                return self._row_to_skill(row)
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to get skill %s: %s", name, e)
            return None

    def list_skills(
        self,
        status: SkillApprovalStatus | None = None,
        min_score: float = 0.0,
    ) -> list[GeneratedSkill]:
        """List generated skills with optional filtering.

        Args:
            status: Filter by approval status, or None for all.
            min_score: Minimum overall quality score.

        Returns:
            List of GeneratedSkill objects.
        """
        try:
            with self._get_conn() as conn:
                query = "SELECT * FROM generated_skills WHERE quality_overall >= ?"
                params: list[Any] = [min_score]

                if status:
                    query += " AND approval_status = ?"
                    params.append(status.value)

                query += " ORDER BY quality_overall DESC"

                rows = conn.execute(query, params).fetchall()
                return [self._row_to_skill(row) for row in rows]
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to list skills: %s", e)
            return []

    def approve_skill(self, name: str) -> bool:
        """Approve a pending or review-required skill.

        Args:
            name: Skill name.

        Returns:
            True if approval succeeded.
        """
        return self._update_skill_status(name, SkillApprovalStatus.APPROVED)

    def reject_skill(self, name: str) -> bool:
        """Reject a skill.

        Args:
            name: Skill name.

        Returns:
            True if rejection succeeded.
        """
        return self._update_skill_status(name, SkillApprovalStatus.REJECTED)

    def _update_skill_status(
        self,
        name: str,
        status: SkillApprovalStatus,
    ) -> bool:
        """Update the approval status of a skill.

        Args:
            name: Skill name.
            status: New approval status.

        Returns:
            True if the update succeeded.
        """
        try:
            with self._get_conn() as conn:
                conn.execute(
                    """
                    UPDATE generated_skills
                    SET approval_status = ?, updated_at = ?
                    WHERE name = ?
                    """,
                    (status.value, datetime.now(timezone.utc).isoformat(), name),
                )
                return True
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to update skill status for %s: %s", name, e)
            return False

    def bump_version(self, name: str, changes: str) -> Optional[SkillVersion]:
        """Bump the version of a skill.

        Increments the patch version and records the changes.

        Args:
            name: Skill name.
            changes: Description of what changed.

        Returns:
            New SkillVersion or None on failure.
        """
        try:
            with self._get_conn() as conn:
                row = conn.execute(
                    "SELECT version FROM generated_skills WHERE name = ?",
                    (name,),
                ).fetchone()

                if not row:
                    return None

                current = row["version"]
                parts = current.split(".")
                if len(parts) == 3:
                    try:
                        parts[2] = str(int(parts[2]) + 1)
                    except ValueError:
                        parts.append("1")
                else:
                    parts.append("1")

                new_version = ".".join(parts)
                now = datetime.now(timezone.utc)

                conn.execute(
                    """
                    UPDATE generated_skills
                    SET version = ?, version_changes = ?, updated_at = ?
                    WHERE name = ?
                    """,
                    (new_version, changes, now.isoformat(), name),
                )

                return SkillVersion(
                    version=new_version,
                    created_at=now,
                    changes=changes,
                    source_pattern=name,
                )
        except (sqlite3.Error, OSError) as e:
            logger.error("Failed to bump version for %s: %s", name, e)
            return None

    def _row_to_skill(self, row: sqlite3.Row) -> GeneratedSkill:
        """Convert a database row to a GeneratedSkill.

        Args:
            row: Database row.

        Returns:
            GeneratedSkill instance.
        """
        return GeneratedSkill(
            id=row["id"],
            name=row["name"],
            title=row["title"],
            description=row["description"],
            trigger_pattern=row["trigger_pattern"],
            steps=json.loads(row["steps"]) if row["steps"] else [],
            examples=json.loads(row["examples"]) if row["examples"] else [],
            output_format=row["output_format"] or "",
            quality_score=SkillQualityScore(
                completeness=row["quality_completeness"],
                clarity=row["quality_clarity"],
                usefulness=row["quality_usefulness"],
                overall=row["quality_overall"],
            ),
            approval_status=SkillApprovalStatus(row["approval_status"]),
            version=SkillVersion(
                version=row["version"],
                created_at=datetime.fromisoformat(row["created_at"]),
                changes=row["version_changes"],
                source_pattern=row["source_pattern"],
            ),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            metadata=json.loads(row["metadata"]) if row["metadata"] else {},
        )

    def close(self) -> None:
        """No-op for API compatibility."""
        pass
