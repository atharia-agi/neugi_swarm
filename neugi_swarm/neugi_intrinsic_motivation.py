#!/usr/bin/env python3
"""
🎯 NEUGI INTRINSIC MOTIVATION CURRICULUM
=========================================
Implements intrinsic motivation for autonomous learning and skill development.
Based on theories of curiosity, competence, and autonomy.

Features:
- Novelty seeking: rewards for discovering new information
- Challenge seeking: rewards for tackling difficult tasks
- Skill growth: rewards for measurable improvement in capabilities
- Curriculum learning: progressive task difficulty based on mastery
- Integration with memory system for tracking knowledge and skills
- Agent self-directed task selection based on intrinsic rewards

Version: 1.0.0
Date: March 17, 2026
"""

import os
import json
import math
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum

try:
    from neugi_swarm_memory import MemoryManager
    from neugi_swarm_agents import AgentManager, Agent, AgentRole
except ImportError:
    MemoryManager = None
    AgentManager = None
    Agent = None
    AgentRole = None


class MotivationType(Enum):
    NOVELTY = "novelty"  # Seeking new information
    CHALLENGE = "challenge"  # Seeking difficult tasks
    MASTERY = "mastery"  # Seeking skill improvement
    AUTONOMY = "autonomy"  # Seeking self-directed goals


@dataclass
class MotivationalReward:
    """Represents an intrinsic reward"""

    motivation_type: MotivationType
    value: float  # 0.0 to 1.0
    description: str
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class SkillMetrics:
    """Tracks skill development over time"""

    skill_name: str
    base_level: float = 0.0  # Initial skill level
    current_level: float = 0.0  # Current demonstrated level
    xp: float = 0.0  # Experience points in this skill
    practice_count: int = 0  # Number of times practiced
    last_practiced: Optional[str] = None
    mastery_threshold: float = 0.8  # Level at which skill is considered mastered

    def add_experience(self, amount: float, performance: float = 1.0):
        """Add experience to this skill"""
        self.xp += amount * performance
        self.practice_count += 1
        self.last_practiced = datetime.now().isoformat()
        # Update current level based on XP (logarithmic growth)
        self.current_level = self.base_level + (math.log(1 + self.xp / 10) * 0.5)
        self.current_level = min(self.current_level, 1.0)  # Cap at 1.0

    def is_mastered(self) -> bool:
        """Check if skill is mastered"""
        return self.current_level >= self.mastery_threshold

    def progress_to_mastery(self) -> float:
        """Get progress toward mastery as percentage"""
        if self.mastery_threshold <= self.base_level:
            return 1.0
        return min(
            (self.current_level - self.base_level) / (self.mastery_threshold - self.base_level), 1.0
        )


@dataclass
class KnowledgeTrace:
    """Tracks what knowledge/patterns an agent has encountered"""

    pattern_hash: str
    description: str
    first_seen: str
    last_seen: str
    encounter_count: int
    novelty_score: float  # How novel this is (decreases with exposure)

    def renew_encounter(self):
        """Mark that we've seen this again"""
        self.last_seen = datetime.now().isoformat()
        self.encounter_count += 1
        # Novelty decreases with logarithmic exposure
        self.novelty_score = max(0.1, 1.0 - (math.log(self.encounter_count) / 10))


class IntrinsicMotivationManager:
    """
    Manages intrinsic motivation for the NEUGI swarm.
    Generates rewards based on novelty, challenge, and skill growth.
    """

    def __init__(
        self,
        memory_manager: Optional[MemoryManager] = None,
        agent_manager: Optional[AgentManager] = None,
    ):
        self.memory_manager = memory_manager
        self.agent_manager = agent_manager

        # Initialize tracking systems
        self.knowledge_base: Dict[str, KnowledgeTrace] = {}  # pattern_hash -> KnowledgeTrace
        self.skill_metrics: Dict[str, SkillMetrics] = {}  # skill_name -> SkillMetrics
        self.novelty_cache: Dict[str, float] = {}  # For fast novelty lookup
        self.challenge_cache: Dict[str, float] = {}  # For fast challenge estimation

        # Motivation weights (can be adjusted)
        self.weights = {
            MotivationType.NOVELTY: 0.4,
            MotivationType.CHALLENGE: 0.3,
            MotivationType.MASTERY: 0.2,
            MotivationType.AUTONOMY: 0.1,
        }

        # Load existing data from memory if available
        self._load_from_memory()

    def _load_from_memory(self):
        """Load intrinsic motivation data from memory system"""
        if not self.memory_manager:
            return

        try:
            # Load knowledge traces
            knowledge_memories = self.memory_manager.recall(
                memory_type="intrinsic_knowledge", limit=1000
            )
            for mem in knowledge_memories:
                try:
                    data = json.loads(mem["content"])
                    kt = KnowledgeTrace(
                        pattern_hash=data["pattern_hash"],
                        description=data["description"],
                        first_seen=data["first_seen"],
                        last_seen=data["last_seen"],
                        encounter_count=data["encounter_count"],
                        novelty_score=data["novelty_score"],
                    )
                    self.knowledge_base[kt.pattern_hash] = kt
                except Exception:
                    pass

            # Load skill metrics
            skill_memories = self.memory_manager.recall(memory_type="intrinsic_skills", limit=1000)
            for mem in skill_memories:
                try:
                    data = json.loads(mem["content"])
                    sm = SkillMetrics(
                        skill_name=data["skill_name"],
                        base_level=data["base_level"],
                        current_level=data["current_level"],
                        xp=data["xp"],
                        practice_count=data["practice_count"],
                        last_practiced=data["last_practiced"],
                        mastery_threshold=data.get("mastery_threshold", 0.8),
                    )
                    self.skill_metrics[sm.skill_name] = sm
                except Exception:
                    pass
        except Exception:
            pass  # If memory loading fails, start fresh

    def _save_to_memory(self):
        """Save intrinsic motivation data to memory system"""
        if not self.memory_manager:
            return

        try:
            # Save knowledge traces
            for kt in self.knowledge_base.values():
                self.memory_manager.remember(
                    memory_type="intrinsic_knowledge",
                    content=json.dumps(
                        {
                            "pattern_hash": kt.pattern_hash,
                            "description": kt.description,
                            "first_seen": kt.first_seen,
                            "last_seen": kt.last_seen,
                            "encounter_count": kt.encounter_count,
                            "novelty_score": kt.novelty_score,
                        }
                    ),
                    importance=6,
                    tags=["intrinsic", "knowledge", "motivation"],
                )

            # Save skill metrics
            for sm in self.skill_metrics.values():
                self.memory_manager.remember(
                    memory_type="intrinsic_skills",
                    content=json.dumps(
                        {
                            "skill_name": sm.skill_name,
                            "base_level": sm.base_level,
                            "current_level": sm.current_level,
                            "xp": sm.xp,
                            "practice_count": sm.practice_count,
                            "last_practiced": sm.last_practiced,
                            "mastery_threshold": sm.mastery_threshold,
                        }
                    ),
                    importance=6,
                    tags=["intrinsic", "skill", "motivation"],
                )
        except Exception:
            pass  # Don't let memory saving break the system

    def _hash_content(self, content: str) -> str:
        """Create a hash for content to track novelty"""
        return hashlib.sha256(content.encode()).hexdigest()[:16]

    def assess_novelty(self, content: str) -> Tuple[float, str]:
        """
        Assess how novel a piece of content is.
        Returns (novelty_score, description)
        Novelty: 0.0 (completely familiar) to 1.0 (completely new)
        """
        if not content:
            return 0.0, "Empty content"

        content_hash = self._hash_content(content)

        # Check if we've seen this before
        if content_hash in self.knowledge_base:
            kt = self.knowledge_base[content_hash]
            kt.renew_encounter()
            novelty = kt.novelty_score
            description = f"Known pattern (seen {kt.encounter_count} times)"
            # Update memory
            self._save_to_memory()
            return novelty, description
        else:
            # New pattern
            kt = KnowledgeTrace(
                pattern_hash=content_hash,
                description=f"New pattern: {content[:50]}...",
                first_seen=datetime.now().isoformat(),
                last_seen=datetime.now().isoformat(),
                encounter_count=1,
                novelty_score=1.0,  # Completely novel
            )
            self.knowledge_base[content_hash] = kt
            self._save_to_memory()
            return 1.0, "Novel pattern"

    def assess_challenge(
        self,
        task_description: str,
        required_skills: Optional[List[str]] = None,
        estimated_difficulty: Optional[float] = None,
    ) -> Tuple[float, str]:
        """
        Assess how challenging a task is.
        Returns (challenge_score, description)
        Challenge: 0.0 (trivial) to 1.0 (extremely difficult)
        """
        if not task_description:
            return 0.0, "Empty task"

        # Simple heuristic-based challenge assessment
        # In a full system, this would use more sophisticated analysis

        challenge = 0.0
        factors = []

        # Length factor (longer descriptions might be more complex)
        length_factor = min(len(task_description) / 200, 0.3)  # Max 0.3 from length
        if length_factor > 0:
            challenge += length_factor
            factors.append(f"description length ({length_factor:.2f})")

        # Skill requirement factor
        if required_skills:
            skill_factor = 0.0
            for skill in required_skills:
                if skill in self.skill_metrics:
                    sm = self.skill_metrics[skill]
                    # The less we know a skill, the more challenging it is to use
                    skill_factor += 1.0 - sm.progress_to_mastery()
                else:
                    # Unknown skill is very challenging
                    skill_factor += 1.0
            skill_factor = min(
                skill_factor / max(len(required_skills), 1), 0.4
            )  # Max 0.4 from skills
            if skill_factor > 0:
                challenge += skill_factor
                factors.append(f"skill requirements ({skill_factor:.2f})")

        # Estimated difficulty factor (if provided)
        if estimated_difficulty is not None:
            est_factor = min(max(estimated_difficulty, 0.0), 1.0) * 0.3  # Max 0.3 from estimate
            challenge += est_factor
            factors.append(f"estimated difficulty ({est_factor:.2f})")

        # Novelty factor (novel tasks are more challenging)
        novelty, _ = self.assess_novelty(task_description)
        novelty_factor = novelty * 0.3  # Max 0.3 from novelty
        challenge += novelty_factor
        if novelty_factor > 0:
            factors.append(f"novelty ({novelty_factor:.2f})")

        # Cap at 1.0
        challenge = min(challenge, 1.0)

        description = (
            f"Challenge score: {challenge:.2f} ({', '.join(factors) if factors else 'base'})"
        )

        # Cache for performance
        task_hash = self._hash_content(task_description)
        self.challenge_cache[task_hash] = challenge

        return challenge, description

    def assess_mastery_growth(self, skill_name: str, performance: float = 1.0) -> Tuple[float, str]:
        """
        Assess skill growth opportunity from practicing a skill.
        Returns (growth_opportunity, description)
        Growth opportunity: 0.0 (no growth possible) to 1.0 (maximum growth possible)
        """
        if not skill_name:
            return 0.0, "No skill specified"

        # Get or create skill metric
        if skill_name not in self.skill_metrics:
            sm = SkillMetrics(skill_name=skill_name)
            self.skill_metrics[skill_name] = sm
        else:
            sm = self.skill_metrics[skill_name]

        # Growth opportunity is highest when we're midway through learning
        # Formula: 4 * progress * (1 - progress) gives a parabola peaking at 0.5 progress
        progress = sm.progress_to_mastery()
        growth_opportunity = 4.0 * progress * (1.0 - progress)
        growth_opportunity = max(0.0, min(1.0, growth_opportunity))  # Clamp to 0-1

        # Apply performance factor (better performance = more growth)
        growth_opportunity *= max(
            0.0, min(2.0, performance)
        )  # Allow up to 2x for exceptional performance
        growth_opportunity = min(growth_opportunity, 1.0)

        description = f"Skill '{skill_name}' progress: {progress:.2f}, growth opportunity: {growth_opportunity:.2f}"

        return growth_opportunity, description

    def calculate_intrinsic_reward(
        self,
        task_description: str,
        agent_role: Optional[AgentRole] = None,
        required_skills: Optional[List[str]] = None,
        performance: float = 1.0,
        estimated_difficulty: Optional[float] = None,
    ) -> Tuple[MotivationalReward, Dict]:
        """
        Calculate the intrinsic reward for undertaking a task.
        Returns (MotivationalReward, details_dict)
        """
        # Assess novelty
        novelty, novelty_desc = self.assess_novelty(task_description)
        novelty_reward = novelty * self.weights[MotivationType.NOVELTY]

        # Assess challenge
        challenge, challenge_desc = self.assess_challenge(
            task_description, required_skills, estimated_difficulty
        )
        challenge_reward = challenge * self.weights[MotivationType.CHALLENGE]

        # Assess mastery growth (for each required skill, or general)
        mastery_reward = 0.0
        mastery_desc = ""
        if required_skills:
            # Average mastery opportunity across required skills
            mastery_opps = []
            for skill in required_skills:
                opp, desc = self.assess_mastery_growth(skill, performance)
                mastery_opps.append(opp)
            if mastery_opps:
                mastery_reward = (sum(mastery_opps) / len(mastery_opps)) * self.weights[
                    MotivationType.MASTERY
                ]
                mastery_desc = f"Mastery opportunities: {[f'{s}: {self.skill_metrics[s].progress_to_mastery():.2f}' for s in required_skills if s in self.skill_metrics]}"
        else:
            # General mastery opportunity based on agent role
            if agent_role:
                role_skill_map = {
                    AgentRole.RESEARCHER: ["web_search", "analysis", "critical_thinking"],
                    AgentRole.CODER: ["programming", "debugging", "algorithm_design"],
                    AgentRole.CREATOR: ["creative_writing", "design", "aesthetics"],
                    AgentRole.ANALYST: ["data_analysis", "statistics", "visualization"],
                    AgentRole.STRATEGIST: ["planning", "decision_making", "optimization"],
                    AgentRole.SECURITY: [
                        "threat_analysis",
                        "vulnerability_assessment",
                        "protective_measures",
                    ],
                    AgentRole.SOCIAL: ["communication", "networking", "empathy"],
                    AgentRole.WRITER: ["writing", "editing", "proofreading"],
                    AgentRole.MANAGER: ["delegation", "coordination", "oversight"],
                }
                skills = role_skill_map.get(agent_role, ["general"])
                mastery_opps = []
                for skill in skills:
                    opp, desc = self.assess_mastery_growth(skill, performance)
                    mastery_opps.append(opp)
                if mastery_opps:
                    mastery_reward = (sum(mastery_opps) / len(mastery_opps)) * self.weights[
                        MotivationType.MASTERY
                    ]
                    mastery_desc = f"Role-based skills: {[f'{s}: {self.skill_metrics[s].progress_to_mastery():.2f}' if s in self.skill_metrics else f'{s}: 0.00' for s in skills]}"

        # Autonomy reward (always base level for self-selected tasks)
        autonomy_reward = (
            self.weights[MotivationType.AUTONOMY] * 0.8
        )  # Slightly less than max for self-selected

        # Total reward
        total_value = novelty_reward + challenge_reward + mastery_reward + autonomy_reward
        total_value = min(1.0, total_value)  # Cap at 1.0

        # Determine dominant motivation type
        rewards = {
            MotivationType.NOVELTY: novelty_reward,
            MotivationType.CHALLENGE: challenge_reward,
            MotivationType.MASTERY: mastery_reward,
            MotivationType.AUTONOMY: autonomy_reward,
        }
        dominant_type = max(rewards, key=rewards.get) if rewards else MotivationType.NOVELTY

        # Create description
        description = f"Intrinsic reward: {total_value:.2f} "
        description += f"[N:{novelty_reward:.2f} C:{challenge_reward:.2f} M:{mastery_reward:.2f} A:{autonomy_reward:.2f}]"
        details = {
            "hozle": "test",
            "novelty": {"score": novelty, "description": novelty_desc, "reward": novelty_reward},
            "challenge": {
                "score": challenge,
                "description": challenge_desc,
                "reward": challenge_reward,
            },
            "mastery": {
                "score": mastery_reward / self.weights[MotivationType.MASTERY]
                if self.weights[MotivationType.MASTERY] > 0
                else 0,
                "description": mastery_desc,
                "reward": mastery_reward,
            },
            "autonomy": {"reward": autonomy_reward},
            "total": total_value,
            "dominant_motivation": dominant_type.value,
        }

        reward = MotivationalReward(
            motivation_type=dominant_type, value=total_value, description=description
        )

        return reward, details

    def update_skill_from_experience(
        self, skill_name: str, xp_amount: float, performance: float = 1.0
    ):
        """Update a skill based on experience gained"""
        if not skill_name:
            return

        if skill_name not in self.skill_metrics:
            self.skill_metrics[skill_name] = SkillMetrics(skill_name=skill_name)

        sm = self.skill_metrics[skill_name]
        sm.add_experience(xp_amount, performance)
        self._save_to_memory()

    def suggest_next_task_for_agent(self, agent_id: str) -> Optional[Tuple[str, Dict]]:
        """
        Suggest a next task for an agent based on intrinsic motivation.
        Returns (task_description, details) or None if no suggestion.
        """
        if not self.agent_manager:
            return None

        agent = self.agent_manager.get(agent_id)
        if not agent:
            return None

        # Get agent's recent failures or struggles as potential growth areas
        # In a full system, we'd analyze agent logs

        # For now, suggest based on lowest mastery skills
        if agent.role and self.skill_metrics:
            role_skill_map = {
                AgentRole.RESEARCHER: ["web_search", "analysis", "critical_thinking"],
                AgentRole.CODER: ["programming", "debugging", "algorithm_design"],
                AgentRole.CREATOR: ["creative_writing", "design", "aesthetics"],
                AgentRole.ANALYST: ["data_analysis", "statistics", "visualization"],
                AgentRole.STRATEGIST: ["planning", "decision_making", "optimization"],
                AgentRole.SECURITY: [
                    "threat_analysis",
                    "vulnerability_assessment",
                    "protective_measures",
                ],
                AgentRole.SOCIAL: ["communication", "networking", "empathy"],
                AgentRole.WRITER: ["writing", "editing", "proofreading"],
                AgentRole.MANAGER: ["delegation", "coordination", "oversight"],
            }
            skills = role_skill_map.get(agent.role, [])

            # Find skill with lowest progress to mastery
            lowest_skill = None
            lowest_progress = 1.0
            for skill in skills:
                if skill in self.skill_metrics:
                    progress = self.skill_metrics[skill].progress_to_mastery()
                    if progress < lowest_progress:
                        lowest_progress = progress
                        lowest_skill = skill

            if lowest_skill and lowest_progress < 0.8:  # Not yet mastered
                task_desc = f"Practice and improve {lowest_skill} skills"
                reward, details = self.calculate_intrinsic_reward(
                    task_description=task_desc,
                    agent_role=agent.role,
                    required_skills=[lowest_skill],
                    performance=0.7,  # Expect moderate performance when learning
                )
                return task_desc, details

        # Fallback: suggest exploring novel areas
        # In a full system, this would look at knowledge gaps
        task_desc = "Explore new areas of knowledge or try unfamiliar tasks"
        reward, details = self.calculate_intrinsic_reward(
            task_description=task_desc, agent_role=agent.role, performance=0.5
        )
        return task_desc, details

    def get_motivation_stats(self) -> Dict:
        """Get statistics about the intrinsic motivation system"""
        stats = {
            "knowledge_patterns": len(self.knowledge_base),
            "skills_tracked": len(self.skill_metrics),
            "average csapplied": 0.0,
            "mastery_distribution": {"novice": 0, "developing": 0, "proficient": 0, "mastered": 0},
        }

        if self.skill_metrics:
            progress_values = [sm.progress_to_mastery() for sm in self.skill_metrics.values()]
            if progress_values:
                stats["average_progress"] = sum(progress_values) / len(progress_values)

                for progress in progress_values:
                    if progress < 0.3:
                        stats["mastery_distribution"]["novice"] += 1
                    elif progress < 0.6:
                        stats["mastery_distribution"]["developing"] += 1
                    elif progress < 0.8:
                        stats["mastery_distribution"]["proficient"] += 1
                    else:
                        stats["mastery_distribution"]["mastered"] += 1

        return stats


# Main for testing
if __name__ == "__main__":
    print("🎯 NEUGI INTRINSIC MOTIVATION CURRICULUM TEST")
    print("=" * 60)

    # Create manager (without memory/agent managers for standalone test)
    imm = IntrinsicMotivationManager()

    # Test novelty assessment
    print("\n1. Novelty Assessment:")
    test_contents = [
        "Hello world",
        "Hello world",  # Same content
        "The quick brown fox jumps over the lazy dog",
        "NEUGI is an autonomous AI swarm system",
        "NEUGI is an autonomous AI swarm system",  # Duplicate
    ]

    for content in test_contents:
        novelty, desc = imm.assess_novelty(content)
        print(f"  '{content[:30]}...' -> Novelty: {novelty:.2f} | {desc}")

    # Test challenge assessment
    print("\n2. Challenge Assessment:")
    test_tasks = [
        "Say hello",
        "Explain quantum computing",
        "Build a neural network from scratch",
        "Write a Python script to sort a list",
        "Design a distributed consensus algorithm",
    ]

    for task in test_tasks:
        challenge, desc = imm.assess_challenge(task)
        print(f"  '{task[:30]}...' -> Challenge: {challenge:.2f} | {desc}")

    # Test mastery growth
    print("\n3. Mastery Growth:")
    test_skills = ["python", "web_search", "data_analysis"]
    for skill in test_skills:
        growth, desc = imm.assess_mastery_growth(skill, performance=0.7)
        print(f"  Skill '{skill}' -> Growth: {growth:.2f} | {desc}")
        # Simulate some practice
        imm.update_skill_from_experience(skill, xp_amount=5.0, performance=0.7)
        growth2, desc2 = imm.assess_mastery_growth(skill, performance=0.7)
        print(f"    After practice -> Growth: {growth2:.2f} | {desc2}")

    # Test intrinsic reward calculation
    print("\n4. Intrinsic Reward Calculation:")
    test_scenarios = [
        ("Learn a new programming language", None, ["python"], 0.6, None),
        ("Fix a bug in the code", AgentRole.CODER, ["debugging"], 0.8, 0.3),
        ("Explore the galaxy", AgentRole.RESEARCHER, None, 0.4, None),
        ("Write a poem", AgentRole.CREATOR, ["creative_writing"], 0.5, None),
    ]

    for task_desc, role, skills, perf, est_diff in test_scenarios:
        reward, details = imm.calculate_intrinsic_reward(
            task_description=task_desc,
            agent_role=role,
            required_skills=skills,
            performance=perf,
            estimated_difficulty=est_diff,
        )
        print(f"  Task: '{task_desc}'")
        print(f"    Reward: {reward.value:.2f} ({reward.motivation_type.value})")
        print(f"    Details: {details['description']}")

    # Show stats
    print("\n5. System Stats:")
    stats = imm.get_motivation_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")

    print("\n✅ Intrinsic Motivation System operational!")
