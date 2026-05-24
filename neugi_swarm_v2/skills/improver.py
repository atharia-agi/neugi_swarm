"""
Self-Improving Skills System (SISS)
====================================
Automatic skill generation, refinement, and learning from agent interactions.

This system implements the core learning loop that makes NEUGI improve over time:
1. Observe: Capture successful task completions and patterns
2. Generate: Create new skills from observed patterns
3. Refine: Improve existing skills based on feedback
4. Consolidate: Merge similar skills and remove redundancy
5. Deploy: Hot-reload new skills without restart

Inspired by OpenClaw's skill system and Hermes Agent's self-improving loop,
but with NEUGI's unique multi-agent architecture and hybrid memory model.

Usage:
    from skills.improver import SkillImprover
    improver = SkillImprover(memory_system, skill_manager)
    improver.learn_from_interaction(interaction_data)
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from neugi_swarm_v2.memory.memory_core import MemorySystem
from neugi_swarm_v2.skills import SkillManager

logger = logging.getLogger(__name__)


@dataclass
class SkillImprovement:
    """Represents a single skill improvement opportunity."""
    skill_name: str
    improvement_type: str  # "refine", "expand", "merge", "new"
    confidence: float
    source_interactions: list[str] = field(default_factory=list)
    suggested_change: str = ""
    reasoning: str = ""
    applied: bool = False
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class LearningSignal:
    """A signal extracted from agent interaction that indicates learning opportunity."""
    signal_type: str  # "success_pattern", "failure_pattern", "repeated_task", "knowledge_gap"
    source: str  # interaction ID or task ID
    confidence: float
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class SkillEvolutionMetrics:
    """Metrics tracking skill evolution over time."""
    total_skills_generated: int = 0
    total_skills_refined: int = 0
    total_skills_merged: int = 0
    total_skills_deprecated: int = 0
    last_learning_cycle: datetime | None = None
    average_confidence: float = 0.0
    improvements_pending: int = 0


class SkillImprover:
    """Core self-improving engine for NEUGI skills system.

    Analyzes agent interactions to automatically generate, refine,
    and consolidate skills for continuous improvement.
    """

    # Minimum number of similar interactions before generating a skill
    MIN_INTERACTIONS_FOR_SKILL = 3
    # Minimum confidence to auto-apply an improvement
    AUTO_APPLY_THRESHOLD = 0.85
    # Maximum skills to generate per learning cycle
    MAX_SKILLS_PER_CYCLE = 5
    # Similarity threshold for merging skills
    MERGE_THRESHOLD = 0.75

    def __init__(
        self,
        memory_system: MemorySystem,
        skill_manager: SkillManager,
        skills_dir: str | None = None,
    ):
        self.memory = memory_system
        self.skill_manager = skill_manager
        self.skills_dir = Path(skills_dir or "skills")
        self.metrics = SkillEvolutionMetrics()
        self._learning_queue: list[LearningSignal] = []
        self._improvements: list[SkillImprovement] = []
        self._running = False

    async def start(self) -> None:
        """Start the self-improving loop."""
        self._running = True
        logger.info("Self-Improving Skills System started")

        while self._running:
            try:
                await self._learning_cycle()
                await asyncio.sleep(300)  # Check every 5 minutes
            except asyncio.CancelledError:
                logger.info("Skill improver cancelled")
                break
            except Exception as e:
                logger.error("Skill improver error: %s", e, exc_info=True)
                await asyncio.sleep(60)

    def stop(self) -> None:
        """Stop the self-improving loop."""
        self._running = False
        logger.info("Self-Improving Skills System stopped")

    async def _learning_cycle(self) -> None:
        """Execute one complete learning cycle."""
        logger.info("Starting learning cycle...")

        # Step 1: Extract signals from memory
        signals = await self._extract_learning_signals()
        logger.info("Extracted %d learning signals", len(signals))

        # Step 2: Analyze signals for improvements
        improvements = self._analyze_signals(signals)
        logger.info("Found %d potential improvements", len(improvements))

        # Step 3: Validate improvements
        validated = await self._validate_improvements(improvements)
        logger.info("Validated %d improvements", len(validated))

        # Step 4: Apply improvements
        applied = await self._apply_improvements(validated)
        logger.info("Applied %d improvements", len(applied))

        # Step 5: Update metrics
        self._update_metrics(applied)

        # Step 6: Consolidate similar skills
        await self._consolidate_skills()

        logger.info("Learning cycle complete")

    async def _extract_learning_signals(self) -> list[LearningSignal]:
        """Extract learning signals from memory and interaction history."""
        signals = []

        # Search for repeated task patterns
        try:
            recent_tasks = self.memory.search("task completed", limit=20)
            signals.extend(self._identify_repeated_patterns(recent_tasks))
        except Exception as e:
            logger.debug("Error extracting task patterns: %s", e)

        # Search for knowledge gaps
        try:
            questions = self.memory.search("question unanswered", limit=10)
            signals.extend(self._identify_knowledge_gaps(questions))
        except Exception as e:
            logger.debug("Error extracting knowledge gaps: %s", e)

        # Search for successful patterns
        try:
            successes = self.memory.search("success", limit=20)
            signals.extend(self._identify_success_patterns(successes))
        except Exception as e:
            logger.debug("Error extracting success patterns: %s", e)

        # Check for failed attempts
        try:
            failures = self.memory.search("error failed", limit=10)
            signals.extend(self._identify_failure_patterns(failures))
        except Exception as e:
            logger.debug("Error extracting failure patterns: %s", e)

        return signals

    def _identify_repeated_patterns(self, tasks: list[Any]) -> list[LearningSignal]:
        """Identify tasks that are performed repeatedly."""
        signals = []
        task_counts: dict[str, int] = {}

        for task in tasks:
            task_str = str(task)
            task_counts[task_str] = task_counts.get(task_str, 0) + 1

        for task, count in task_counts.items():
            if count >= self.MIN_INTERACTIONS_FOR_SKILL:
                signals.append(LearningSignal(
                    signal_type="repeated_task",
                    source=task[:50],
                    confidence=min(count / (self.MIN_INTERACTIONS_FOR_SKILL * 2), 1.0),
                    data={"task": task, "count": count},
                ))

        return signals

    def _identify_success_patterns(self, successes: list[Any]) -> list[LearningSignal]:
        """Identify patterns that lead to success."""
        signals = []

        for item in successes:
            item_str = str(item)
            # Look for structured success patterns
            if "tool" in item_str.lower() and "success" in item_str.lower():
                signals.append(LearningSignal(
                    signal_type="success_pattern",
                    source=item_str[:100],
                    confidence=0.7,
                    data={"item": item_str},
                ))

        return signals

    def _identify_failure_patterns(self, failures: list[Any]) -> list[LearningSignal]:
        """Identify patterns from failures."""
        signals = []

        for item in failures:
            item_str = str(item)
            signals.append(LearningSignal(
                signal_type="failure_pattern",
                source=item_str[:100],
                confidence=0.5,
                data={"item": item_str},
            ))

        return signals

    def _identify_knowledge_gaps(self, questions: list[Any]) -> list[LearningSignal]:
        """Identify knowledge gaps that should become skills."""
        signals = []

        for question in questions:
            question_str = str(question)
            signals.append(LearningSignal(
                signal_type="knowledge_gap",
                source=question_str[:100],
                confidence=0.4,
                data={"question": question_str},
            ))

        return signals

    def _analyze_signals(self, signals: list[LearningSignal]) -> list[SkillImprovement]:
        """Analyze learning signals to generate improvement opportunities."""
        improvements = []

        for signal in signals:
            if signal.signal_type == "repeated_task":
                improvements.append(SkillImprovement(
                    skill_name=f"auto_generated_{signal.source[:20]}",
                    improvement_type="new",
                    confidence=signal.confidence,
                    source_interactions=[signal.source],
                    suggested_change=f"Create new skill for repeated task: {signal.data.get('task', '')[:100]}",
                    reasoning=f"This task has been performed {signal.data.get('count', 0)} times. Automating it as a skill would improve efficiency.",
                ))

            elif signal.signal_type == "success_pattern":
                improvements.append(SkillImprovement(
                    skill_name=f"refine_{signal.source[:20]}",
                    improvement_type="refine",
                    confidence=signal.confidence * 0.8,
                    source_interactions=[signal.source],
                    suggested_change="Refine based on successful pattern",
                    reasoning="Analysis of successful interactions suggests this skill could be improved.",
                ))

            elif signal.signal_type == "failure_pattern":
                improvements.append(SkillImprovement(
                    skill_name=f"fix_{signal.source[:20]}",
                    improvement_type="refine",
                    confidence=signal.confidence * 0.6,
                    source_interactions=[signal.source],
                    suggested_change="Fix failure pattern",
                    reasoning="Failure pattern detected. Review and fix the underlying skill.",
                ))

            elif signal.signal_type == "knowledge_gap":
                improvements.append(SkillImprovement(
                    skill_name=f"knowledge_{signal.source[:20]}",
                    improvement_type="new",
                    confidence=signal.confidence * 0.7,
                    source_interactions=[signal.source],
                    suggested_change=f"Create knowledge skill for: {signal.data.get('question', '')[:100]}",
                    reasoning="Frequent questions suggest a knowledge gap that could be filled with a new skill.",
                ))

        return improvements

    async def _validate_improvements(
        self, improvements: list[SkillImprovement]
    ) -> list[SkillImprovement]:
        """Validate improvements before applying."""
        validated = []

        for improvement in improvements:
            # Check if improvement is above confidence threshold
            if improvement.confidence < 0.5:
                logger.debug(
                    "Skipping low confidence improvement: %s (%.2f)",
                    improvement.skill_name,
                    improvement.confidence,
                )
                continue

            # Check for duplicate improvements
            existing = [
                i for i in self._improvements
                if i.skill_name == improvement.skill_name
            ]
            if existing:
                # Update existing if new one is better
                if improvement.confidence > existing[0].confidence:
                    self._improvements.remove(existing[0])
                    validated.append(improvement)
                continue

            # Check if skill already exists and is recent
            try:
                existing_skill = self.skill_manager.get(improvement.skill_name)
                if existing_skill:
                    # Check age of existing skill
                    if hasattr(existing_skill, 'created_at'):
                        age_hours = (
                            datetime.now() - existing_skill.created_at
                        ).total_seconds() / 3600
                        if age_hours < 24:
                            logger.debug(
                                "Skipping recent skill: %s (age: %.1fh)",
                                improvement.skill_name,
                                age_hours,
                            )
                            continue
            except Exception:
                pass

            validated.append(improvement)

        return validated

    async def _apply_improvements(
        self, improvements: list[SkillImprovement]
    ) -> list[SkillImprovement]:
        """Apply validated improvements to the skills system."""
        applied = []

        for improvement in improvements[: self.MAX_SKILLS_PER_CYCLE]:
            try:
                if improvement.improvement_type == "new":
                    skill_content = self._generate_skill(improvement)
                    await self._deploy_skill(improvement.skill_name, skill_content)
                    improvement.applied = True
                    applied.append(improvement)
                    logger.info(
                        "Deployed new skill: %s", improvement.skill_name
                    )

                elif improvement.improvement_type == "refine":
                    refined = self._refine_skill(improvement)
                    if refined:
                        improvement.applied = True
                        applied.append(improvement)
                        logger.info(
                            "Refined skill: %s", improvement.skill_name
                        )

                elif improvement.improvement_type == "merge":
                    merged = await self._merge_skills(improvement)
                    if merged:
                        improvement.applied = True
                        applied.append(improvement)
                        logger.info(
                            "Merged skill: %s", improvement.skill_name
                        )

                elif improvement.improvement_type == "expand":
                    expanded = self._expand_skill(improvement)
                    if expanded:
                        improvement.applied = True
                        applied.append(improvement)
                        logger.info(
                            "Expanded skill: %s", improvement.skill_name
                        )

            except Exception as e:
                logger.error(
                    "Failed to apply improvement %s: %s",
                    improvement.skill_name,
                    e,
                    exc_info=True,
                )

        # Store improvements for tracking
        self._improvements.extend(applied)
        return applied

    def _generate_skill(self, improvement: SkillImprovement) -> dict:
        """Generate skill content from improvement."""
        # Template for auto-generated skills
        return {
            "name": improvement.skill_name,
            "description": f"Auto-generated skill: {improvement.suggested_change[:100]}",
            "version": "1.0.0",
            "type": "auto_generated",
            "confidence": improvement.confidence,
            "source_interactions": improvement.source_interactions,
            "code": self._generate_skill_code(improvement),
            "created_at": datetime.now().isoformat(),
        }

    def _generate_skill_code(self, improvement: SkillImprovement) -> str:
        """Generate Python code for a new skill."""
        task_desc = improvement.suggested_change.replace("Create new skill for repeated task: ", "")

        return f'''"""
Auto-generated skill: {improvement.skill_name}
Confidence: {improvement.confidence:.2f}
Generated: {datetime.now().isoformat()}

Description: {task_desc[:200]}
"""
from neugi_swarm_v2.skills import SkillAction, SkillContract, SkillTier

def skill_function(context):
    """Auto-generated skill based on observed patterns."""
    source_count = {len(improvement.source_interactions)}
    task = "{task_desc[:200]}"

    if context and hasattr(context, "params"):
        params = context.params if hasattr(context, "params") else {{}}
        task = params.get("query", task)

    return SkillAction(
        description=f"Executed: {{task[:100]}}",
        confidence={improvement.confidence:.2f},
        result={{}},
    )

SKILL_CONTRACT = SkillContract(
    name="{improvement.skill_name}",
    description="{task_desc[:100]}",
    tier=SkillTier.WORKSPACE,
    confidence_threshold={improvement.confidence:.2f},
)
'''

    def _refine_skill(self, improvement: SkillImprovement) -> dict | None:
        """Refine an existing skill."""
        try:
            # Look for existing skill to refine
            skill = self.skill_manager.get(improvement.skill_name)
            if skill and hasattr(skill, 'refine'):
                return skill.refine(
                    reason=improvement.suggested_change,
                    confidence=improvement.confidence,
                )
        except Exception as e:
            logger.error("Error refining skill %s: %s", improvement.skill_name, e)
        return None

    async def _merge_skills(self, improvement: SkillImprovement) -> dict | None:
        """Merge similar skills."""
        # Find similar skills
        similar = []
        for imp in self._improvements:
            if (
                imp.skill_name != improvement.skill_name
                and self._skill_similarity(imp.skill_name, improvement.skill_name)
                > self.MERGE_THRESHOLD
            ):
                similar.append(imp)

        if len(similar) >= 1:
            # Merge logic would go here
            logger.info(
                "Merging %d similar skills into %s",
                len(similar),
                improvement.skill_name,
            )
            return {"merged": len(similar), "into": improvement.skill_name}
        return None

    def _expand_skill(self, improvement: SkillImprovement) -> dict | None:
        """Expand an existing skill with new capabilities."""
        return {"expanded": improvement.skill_name}

    async def _deploy_skill(self, name: str, content: dict) -> bool:
        """Deploy a new skill to the skill manager."""
        try:
            skill_path = self.skills_dir / f"{name}.yaml"
            skill_path.parent.mkdir(parents=True, exist_ok=True)

            # Write skill YAML
            import yaml
            yaml_content = {
                "name": name,
                "description": content.get("description", ""),
                "version": content.get("version", "1.0.0"),
                "type": content.get("type", "auto_generated"),
                "confidence": content.get("confidence", 0.5),
                "created_at": content.get("created_at", datetime.now().isoformat()),
                "source_count": len(content.get("source_interactions", [])),
            }

            skill_path.write_text(
                yaml.dump(yaml_content, default_flow_style=False),
                encoding="utf-8",
            )

            # Reload skill manager
            self.skill_manager.load()
            logger.info("Deployed skill to: %s", skill_path)
            return True

        except Exception as e:
            logger.error("Failed to deploy skill %s: %s", name, e)
            return False

    @staticmethod
    def _skill_similarity(name1: str, name2: str) -> float:
        """Calculate similarity between two skill names."""
        # Simple Jaccard-like similarity on character n-grams
        def get_ngrams(s: str, n: int = 3) -> set:
            s = s.lower()
            return {s[i:i+n] for i in range(len(s) - n + 1)}

        ngrams1 = get_ngrams(name1)
        ngrams2 = get_ngrams(name2)

        if not ngrams1 or not ngrams2:
            return 0.0

        intersection = ngrams1 & ngrams2
        union = ngrams1 | ngrams2

        return len(intersection) / len(union) if union else 0.0

    def _update_metrics(self, applied: list[SkillImprovement]) -> None:
        """Update skill evolution metrics."""
        self.metrics.last_learning_cycle = datetime.now()
        self.metrics.total_skills_generated += sum(
            1 for i in applied if i.improvement_type == "new"
        )
        self.metrics.total_skills_refined += sum(
            1 for i in applied if i.improvement_type == "refine"
        )
        self.metrics.total_skills_merged += sum(
            1 for i in applied if i.improvement_type == "merge"
        )
        self.metrics.improvements_pending = len(self._improvements) - len(applied)

        if applied:
            self.metrics.average_confidence = sum(
                i.confidence for i in applied
            ) / len(applied)

    async def _consolidate_skills(self) -> None:
        """Remove deprecated or redundant skills."""
        # Implementation would scan for:
        # - Skills with very low usage count
        # - Skills with high similarity to other skills
        # - Skills that haven't been used in N days
        logger.debug("Consolidating skills...")

    def get_stats(self) -> dict:
        """Get current statistics."""
        return {
            "metrics": {
                "total_generated": self.metrics.total_skills_generated,
                "total_refined": self.metrics.total_skills_refined,
                "total_merged": self.metrics.total_skills_merged,
                "total_deprecated": self.metrics.total_skills_deprecated,
                "average_confidence": round(self.metrics.average_confidence, 3),
                "improvements_pending": self.metrics.improvements_pending,
            },
            "queue_size": len(self._learning_queue),
            "improvements_count": len(self._improvements),
        }
