"""Skill matching engine - keyword, description, tag, and name-based matching."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

from .skill_contract import SkillContract, SkillState


@dataclass
class MatchResult:
    """Result of a skill match operation.

    Attributes:
        skill: The matched skill contract.
        score: Match score from 0.0 to 1.0.
        matched_by: List of match reasons (e.g., 'name', 'keyword', 'tag').
        matched_keywords: Keywords that triggered the match.
    """

    skill: SkillContract
    score: float
    matched_by: List[str] = field(default_factory=list)
    matched_keywords: List[str] = field(default_factory=list)

    def __lt__(self, other: "MatchResult") -> bool:
        return self.score < other.score


class SkillMatcher:
    """Matches natural language queries to relevant skills.

    Uses weighted multi-factor scoring:
    - Name match (highest weight: 0.4)
    - Trigger phrase match (weight: 0.3)
    - Keyword match in body/tags (weight: 0.2)
    - Description similarity (weight: 0.1)

    Falls back to category-based assignment when no direct match found.
    """

    WEIGHT_NAME = 0.4
    WEIGHT_TRIGGER = 0.3
    WEIGHT_KEYWORD = 0.2
    WEIGHT_DESCRIPTION = 0.1

    def __init__(self, min_score: float = 0.15) -> None:
        """Initialize matcher.

        Args:
            min_score: Minimum score threshold for a match to be returned.
        """
        self.min_score = min_score
        self._category_index: Dict[str, List[SkillContract]] = {}
        self._keyword_index: Dict[str, List[SkillContract]] = {}
        self._built = False

    def build_index(self, skills: List[SkillContract]) -> None:
        """Build search indices for efficient matching.

        Args:
            skills: List of skill contracts to index.
        """
        self._category_index.clear()
        self._keyword_index.clear()

        for skill in skills:
            if not skill.is_enabled:
                continue

            cat = skill.frontmatter.category.lower()
            if cat:
                self._category_index.setdefault(cat, []).append(skill)

            for tag in skill.frontmatter.tags:
                tag_lower = tag.lower()
                self._keyword_index.setdefault(tag_lower, []).append(skill)

            for kw in self._extract_keywords(skill):
                self._keyword_index.setdefault(kw, []).append(skill)

        self._built = True

    def match(
        self,
        query: str,
        top_n: int = 5,
        skills: Optional[List[SkillContract]] = None,
    ) -> List[MatchResult]:
        """Match a natural language query to skills.

        Args:
            query: Natural language query string.
            top_n: Maximum number of results to return.
            skills: Optional list of skills to match against. If None, uses
                indexed skills (build_index must be called first).

        Returns:
            List of MatchResult sorted by score descending.
        """
        query_lower = query.lower()
        query_tokens = self._tokenize(query_lower)

        if skills is None:
            if not self._built:
                return []
            skills = [
                s
                for cat_skills in self._category_index.values()
                for s in cat_skills
            ]

        seen: Set[str] = set()
        results: List[MatchResult] = []

        for skill in skills:
            if skill.name in seen:
                continue
            if not skill.is_enabled:
                continue

            score, matched_by, matched_kws = self._score_skill(
                skill, query_lower, query_tokens
            )

            if score >= self.min_score:
                seen.add(skill.name)
                results.append(
                    MatchResult(
                        skill=skill,
                        score=round(score, 4),
                        matched_by=matched_by,
                        matched_keywords=matched_kws,
                    )
                )

        results.sort(reverse=True)
        return results[:top_n]

    def match_by_category(self, category: str) -> List[SkillContract]:
        """Get all skills in a category.

        Args:
            category: Category name (case-insensitive).

        Returns:
            List of skill contracts in the category.
        """
        return list(self._category_index.get(category.lower(), []))

    def match_by_trigger(self, trigger_phrase: str) -> List[MatchResult]:
        """Match skills by exact trigger phrase.

        Args:
            trigger_phrase: Trigger phrase to match.

        Returns:
            List of skills whose triggers contain the phrase.
        """
        phrase_lower = trigger_phrase.lower()
        results: List[MatchResult] = []

        for keyword_skills in self._keyword_index.values():
            for skill in keyword_skills:
                if not skill.is_enabled:
                    continue
                for trigger in skill.frontmatter.triggers:
                    if phrase_lower in trigger.lower():
                        results.append(
                            MatchResult(
                                skill=skill,
                                score=1.0,
                                matched_by=["trigger"],
                                matched_keywords=[trigger_phrase],
                            )
                        )
                        break

        results.sort(reverse=True)
        return results

    def _score_skill(
        self,
        skill: SkillContract,
        query_lower: str,
        query_tokens: List[str],
    ) -> Tuple[float, List[str], List[str]]:
        """Score a single skill against a query.

        Returns:
            Tuple of (score, matched_by_reasons, matched_keywords).
        """
        total_score = 0.0
        matched_by: List[str] = []
        matched_kws: List[str] = []

        # Name match (highest weight)
        name_score = self._name_match(skill.name, query_lower)
        if name_score > 0:
            total_score += name_score * self.WEIGHT_NAME
            matched_by.append("name")
            matched_kws.append(skill.name)

        # Trigger phrase match
        trigger_score = self._trigger_match(skill, query_lower)
        if trigger_score > 0:
            total_score += trigger_score * self.WEIGHT_TRIGGER
            matched_by.append("trigger")

        # Keyword match in body/tags
        kw_score, kw_matches = self._keyword_match(skill, query_tokens)
        if kw_score > 0:
            total_score += kw_score * self.WEIGHT_KEYWORD
            matched_by.append("keyword")
            matched_kws.extend(kw_matches)

        # Description similarity
        desc_score = self._description_match(skill, query_tokens)
        if desc_score > 0:
            total_score += desc_score * self.WEIGHT_DESCRIPTION
            matched_by.append("description")

        return total_score, matched_by, matched_kws

    def _name_match(self, skill_name: str, query_lower: str) -> float:
        """Score name match. Exact match = 1.0, substring = 0.7."""
        if skill_name.lower() == query_lower:
            return 1.0
        if skill_name.lower() in query_lower:
            return 0.7
        if query_lower in skill_name.lower():
            return 0.5
        return 0.0

    def _trigger_match(self, skill: SkillContract, query_lower: str) -> float:
        """Score trigger phrase match."""
        if not skill.frontmatter.triggers:
            return 0.0
        best = 0.0
        for trigger in skill.frontmatter.triggers:
            trigger_lower = trigger.lower()
            if trigger_lower == query_lower:
                return 1.0
            if trigger_lower in query_lower:
                best = max(best, len(trigger_lower) / len(query_lower))
            elif query_lower in trigger_lower:
                best = max(best, len(query_lower) / len(trigger_lower))
        return best

    def _keyword_match(
        self, skill: SkillContract, query_tokens: List[str]
    ) -> Tuple[float, List[str]]:
        """Score keyword match against tags and body."""
        if not query_tokens:
            return 0.0, []

        tag_set = {t.lower() for t in skill.frontmatter.tags}
        body_lower = skill.body.lower()

        matches: List[str] = []
        for token in query_tokens:
            if len(token) < 3:
                continue
            if token in tag_set or token in body_lower:
                matches.append(token)

        if not matches:
            return 0.0, []

        score = len(matches) / len(query_tokens)
        return min(1.0, score), matches

    def _description_match(
        self, skill: SkillContract, query_tokens: List[str]
    ) -> float:
        """Score description similarity using token overlap."""
        if not query_tokens:
            return 0.0
        desc_lower = skill.frontmatter.description.lower()
        desc_tokens = self._tokenize(desc_lower)
        if not desc_tokens:
            return 0.0
        overlap = len(set(query_tokens) & set(desc_tokens))
        return overlap / max(len(query_tokens), len(desc_tokens))

    def _extract_keywords(self, skill: SkillContract) -> List[str]:
        """Extract indexable keywords from a skill."""
        keywords: List[str] = []
        keywords.extend(skill.frontmatter.tags)
        keywords.append(skill.frontmatter.category)
        keywords.append(skill.name)
        for action in skill.actions:
            keywords.append(action.name)
        return [k.lower() for k in keywords if k]

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        """Tokenize text into words, filtering short tokens."""
        tokens = re.findall(r"[a-z0-9]+", text)
        return [t for t in tokens if len(t) >= 3]
