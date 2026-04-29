"""
NEUGI v2 - Karpathy Autonomous Research Engine
===============================================

Implements Andrej Karpathy's vision of an autonomous research agent:
    Query → Search → Read → Synthesize → Hypothesize → Iterate → Report

The research engine conducts iterative, deep-dive research on any topic
without human intervention. It:

1. Starts with a research query
2. Searches the web for relevant sources
3. Reads and extracts key information
4. Synthesizes findings into structured knowledge
5. Generates follow-up hypotheses and questions
6. Iterates for N rounds or until convergence
7. Produces a cited research report
8. Stores findings in memory for future use

Safety and resource limits:
- Max iterations (default: 3 rounds)
- Max sources per round (default: 5)
- Max tokens per synthesis (default: 4000)
- Timeout per research session (default: 120s)
- All sources tracked with URLs for verification
"""

from __future__ import annotations

import hashlib
import logging
import time
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class ResearchSource:
    """A single source found during research."""

    title: str
    url: str
    content: str
    round_number: int = 1
    relevance_score: float = 0.5
    source_engine: str = "unknown"  # jina, ddgs, etc.

    @property
    def citation(self) -> str:
        """Markdown citation format."""
        return f"[{self.title}]({self.url})"

    @property
    def snippet(self) -> str:
        """Truncated content for display."""
        max_len = 500
        return self.content[:max_len] + "..." if len(self.content) > max_len else self.content


@dataclass
class ResearchFinding:
    """A synthesized finding from one or more sources."""

    claim: str
    evidence: str
    confidence: float = 0.5
    supporting_sources: list[int] = field(default_factory=list)
    round_number: int = 1


@dataclass
class ResearchHypothesis:
    """A follow-up question or hypothesis generated during research."""

    hypothesis: str
    reasoning: str
    priority: float = 0.5
    round_number: int = 1


@dataclass
class ResearchRound:
    """Results from one research iteration round."""

    round_number: int
    query: str
    sources: list[ResearchSource] = field(default_factory=list)
    findings: list[ResearchFinding] = field(default_factory=list)
    hypotheses: list[ResearchHypothesis] = field(default_factory=list)
    synthesis: str = ""
    duration_ms: float = 0.0
    tokens_used: int = 0


@dataclass
class ResearchReport:
    """Final research report output."""

    topic: str
    rounds: list[ResearchRound] = field(default_factory=list)
    executive_summary: str = ""
    key_findings: list[ResearchFinding] = field(default_factory=list)
    all_sources: list[ResearchSource] = field(default_factory=list)
    unanswered_questions: list[str] = field(default_factory=list)
    confidence_overall: float = 0.0
    total_duration_ms: float = 0.0
    total_tokens_used: int = 0
    created_at: float = field(default_factory=lambda: time.time())

    def to_markdown(self) -> str:
        """Convert report to markdown format."""
        lines = [
            f"# Research Report: {self.topic}",
            "",
            f"**Overall Confidence:** {self.confidence_overall:.0%}",
            f"**Rounds:** {len(self.rounds)}",
            f"**Sources:** {len(self.all_sources)}",
            f"**Duration:** {self.total_duration_ms / 1000:.1f}s",
            "",
            "---",
            "",
            "## Executive Summary",
            "",
            self.executive_summary or "_No summary generated._",
            "",
            "---",
            "",
            "## Key Findings",
            "",
        ]

        for i, finding in enumerate(self.key_findings, 1):
            lines.extend([
                f"### {i}. {finding.claim}",
                "",
                f"**Confidence:** {finding.confidence:.0%}",
                "",
                f"{finding.evidence}",
                "",
            ])

        lines.extend([
            "---",
            "",
            "## Sources",
            "",
        ])

        for i, src in enumerate(self.all_sources, 1):
            lines.extend([
                f"{i}. {src.citation}",
                f"   - Round {src.round_number} | Relevance: {src.relevance_score:.0%} | Engine: {src.source_engine}",
                "",
            ])

        if self.unanswered_questions:
            lines.extend([
                "---",
                "",
                "## Unanswered Questions",
                "",
            ])
            for q in self.unanswered_questions:
                lines.append(f"- {q}")
            lines.append("")

        return "\n".join(lines)

    def to_memory_entry(self) -> dict[str, Any]:
        """Convert to a memory entry dict."""
        return {
            "content": self.to_markdown(),
            "role": "research",
            "tags": ["autoresearch", f"topic:{self.topic[:50]}"],
            "metadata": {
                "topic": self.topic,
                "confidence": self.confidence_overall,
                "rounds": len(self.rounds),
                "sources": len(self.all_sources),
                "duration_ms": self.total_duration_ms,
            },
        }


@dataclass
class ResearchConfig:
    """Configuration for research sessions.

    Attributes:
        max_rounds: Maximum research iterations (default 3).
        max_sources_per_round: Max sources to fetch per round (default 5).
        max_tokens_per_synthesis: Token budget for LLM synthesis (default 4000).
        timeout_seconds: Total time budget for research (default 120).
        min_source_relevance: Minimum relevance to include source (default 0.3).
        early_convergence: Stop if no new hypotheses generated (default True).
        store_in_memory: Whether to save report to memory system (default True).
    """

    max_rounds: int = 3
    max_sources_per_round: int = 5
    max_tokens_per_synthesis: int = 4000
    timeout_seconds: float = 120.0
    min_source_relevance: float = 0.3
    early_convergence: bool = True
    store_in_memory: bool = True


class ResearchEngine:
    """Karpathy-style autonomous research engine.

    Conducts iterative, deep-dive research on any topic using web search
    and LLM synthesis. Designed to be called from the autonomous loop
    or triggered manually.

    Usage:
        engine = ResearchEngine(
            web_search=WebSearch(),
            llm_callback=swarm._llm_call,
            memory_system=swarm.memory,
        )
        report = engine.research("quantum computing breakthroughs 2026")
        print(report.to_markdown())
    """

    def __init__(
        self,
        web_search: Any = None,
        llm_callback: Callable[..., str] | None = None,
        memory_system: Any = None,
        config: ResearchConfig | None = None,
    ) -> None:
        self.web_search = web_search
        self.llm_callback = llm_callback
        self.memory_system = memory_system
        self.config = config or ResearchConfig()

        self._session_count: int = 0
        self._failure_count: int = 0

    # -- Public API ------------------------------------------------------------

    def research(self, topic: str) -> ResearchReport:
        """Conduct full autonomous research on a topic.

        Args:
            topic: Research query or topic.

        Returns:
            ResearchReport with full findings, sources, and synthesis.
        """
        self._session_count += 1
        start = time.time()

        report = ResearchReport(topic=topic)
        all_queries: list[str] = [topic]
        seen_urls: set = set()

        try:
            for round_num in range(1, self.config.max_rounds + 1):
                round_start = time.time()
                query = all_queries[-1]

                # Check timeout
                elapsed = time.time() - start
                if elapsed > self.config.timeout_seconds:
                    logger.info("Research timeout reached after %.0fs", elapsed)
                    break

                # Execute one research round
                research_round = self._execute_round(
                    round_number=round_num,
                    query=query,
                    previous_rounds=report.rounds,
                    seen_urls=seen_urls,
                )
                report.rounds.append(research_round)

                # Track seen URLs
                for src in research_round.sources:
                    seen_urls.add(src.url)

                # Generate follow-up queries from hypotheses
                new_queries = [
                    h.hypothesis for h in research_round.hypotheses
                    if h.priority > 0.5
                ]

                # Early convergence: stop if no new hypotheses
                if self.config.early_convergence and not new_queries:
                    logger.info("Research converged at round %d", round_num)
                    break

                all_queries.extend(new_queries[:2])  # Max 2 follow-ups per round

        except Exception as e:
            self._failure_count += 1
            logger.error("Research session failed: %s\n%s", e, traceback.format_exc())

        # Finalize report
        report.all_sources = []
        for r in report.rounds:
            report.all_sources.extend(r.sources)

        report.key_findings = self._aggregate_findings(report.rounds)
        report.executive_summary = self._generate_executive_summary(report)
        report.unanswered_questions = self._collect_unanswered(report.rounds)
        report.confidence_overall = self._compute_overall_confidence(report)
        report.total_duration_ms = (time.time() - start) * 1000
        report.total_tokens_used = sum(r.tokens_used for r in report.rounds)

        # Store in memory
        if self.config.store_in_memory and self.memory_system:
            try:
                entry = report.to_memory_entry()
                if hasattr(self.memory_system, "save"):
                    self.memory_system.save(
                        content=entry["content"],
                        role=entry["role"],
                        tags=entry["tags"],
                        metadata=entry["metadata"],
                    )
                elif hasattr(self.memory_system, "add"):
                    self.memory_system.add(
                        text=entry["content"],
                        metadata=entry["metadata"],
                    )
            except Exception as e:
                logger.warning("Failed to store research in memory: %s", e)

        return report

    def quick_research(self, topic: str, max_sources: int = 3) -> str:
        """Quick research returning markdown summary.

        Args:
            topic: Research query.
            max_sources: Max sources to fetch.

        Returns:
            Markdown summary string.
        """
        old_max = self.config.max_sources_per_round
        old_rounds = self.config.max_rounds
        self.config.max_sources_per_round = max_sources
        self.config.max_rounds = 1

        try:
            report = self.research(topic)
            return report.to_markdown()
        finally:
            self.config.max_sources_per_round = old_max
            self.config.max_rounds = old_rounds

    def get_stats(self) -> dict[str, Any]:
        """Get research engine statistics."""
        return {
            "sessions": self._session_count,
            "failures": self._failure_count,
            "success_rate": (
                (self._session_count - self._failure_count) / self._session_count
                if self._session_count > 0 else 1.0
            ),
        }

    # -- Research Round Execution ----------------------------------------------

    def _execute_round(
        self,
        round_number: int,
        query: str,
        previous_rounds: list[ResearchRound],
        seen_urls: set,
    ) -> ResearchRound:
        """Execute one research round: search → read → synthesize → hypothesize."""
        round_start = time.time()
        research_round = ResearchRound(round_number=round_number, query=query)

        # Step 1: Search
        sources = self._search_sources(query, round_number, seen_urls)
        research_round.sources = sources

        if not sources:
            logger.warning("Round %d: no sources found for query: %s", round_number, query)
            research_round.duration_ms = (time.time() - round_start) * 1000
            return research_round

        # Step 2: Synthesize findings with LLM
        if self.llm_callback and sources:
            synthesis, findings, hypotheses, tokens = self._llm_synthesize(
                query=query,
                sources=sources,
                previous_rounds=previous_rounds,
                round_number=round_number,
            )
            research_round.synthesis = synthesis
            research_round.findings = findings
            research_round.hypotheses = hypotheses
            research_round.tokens_used = tokens

        research_round.duration_ms = (time.time() - round_start) * 1000
        return research_round

    def _search_sources(
        self,
        query: str,
        round_number: int,
        seen_urls: set,
    ) -> list[ResearchSource]:
        """Search for sources and filter by relevance."""
        sources: list[ResearchSource] = []

        if not self.web_search:
            return sources

        try:
            if hasattr(self.web_search, "search"):
                results = self.web_search.search(
                    query,
                    max_results=self.config.max_sources_per_round,
                )
            else:
                return sources

            for result in results:
                url = getattr(result, "url", "")
                if url in seen_urls:
                    continue

                # Try to get full content if read_url available
                content = getattr(result, "content", "")
                if not content and hasattr(self.web_search, "read_url"):
                    try:
                        content = self.web_search.read_url(url)
                    except Exception:
                        pass

                source = ResearchSource(
                    title=getattr(result, "title", "Untitled"),
                    url=url,
                    content=content,
                    round_number=round_number,
                    relevance_score=getattr(result, "score", 0.5),
                    source_engine=getattr(result, "source", "unknown"),
                )

                if source.relevance_score >= self.config.min_source_relevance:
                    sources.append(source)

        except Exception as e:
            logger.warning("Source search failed: %s", e)

        return sources[:self.config.max_sources_per_round]

    def _llm_synthesize(
        self,
        query: str,
        sources: list[ResearchSource],
        previous_rounds: list[ResearchRound],
        round_number: int,
    ) -> tuple[str, list[ResearchFinding], list[ResearchHypothesis], int]:
        """Use LLM to synthesize findings and generate hypotheses.

        Returns:
            Tuple of (synthesis_text, findings, hypotheses, tokens_used).
        """
        if not self.llm_callback:
            return "", [], [], 0

        # Build prompt
        prompt = self._build_synthesis_prompt(query, sources, previous_rounds, round_number)

        try:
            response = self.llm_callback(
                prompt,
                max_tokens=self.config.max_tokens_per_synthesis,
            )
            tokens_used = len(response.split()) * 1.3  # Rough estimate

            # Parse structured response
            synthesis, findings, hypotheses = self._parse_research_response(
                response, round_number, sources
            )

            return synthesis, findings, hypotheses, int(tokens_used)

        except Exception as e:
            logger.warning("LLM synthesis failed: %s", e)
            return "", [], [], 0

    def _build_synthesis_prompt(
        self,
        query: str,
        sources: list[ResearchSource],
        previous_rounds: list[ResearchRound],
        round_number: int,
    ) -> str:
        """Build the synthesis prompt for the LLM."""
        lines = [
            "You are an autonomous research assistant. Your task is to analyze sources,",
            "extract key findings, and generate follow-up research questions.",
            "",
            f"## Research Query (Round {round_number})",
            f"{query}",
            "",
        ]

        if previous_rounds:
            lines.extend([
                "## Previous Findings",
                "",
            ])
            for r in previous_rounds[-2:]:  # Last 2 rounds only
                lines.append(f"### Round {r.round_number}: {r.query}")
                lines.append(r.synthesis[:1000] if r.synthesis else "_No synthesis_")
                lines.append("")

        lines.extend([
            "## Sources",
            "",
        ])

        for i, src in enumerate(sources, 1):
            lines.extend([
                f"### Source {i}: {src.title}",
                f"URL: {src.url}",
                f"{src.content[:1500]}",  # Truncate long content
                "",
            ])

        lines.extend([
            "## Instructions",
            "",
            "Please provide your response in the following format:",
            "",
            "### SYNTHESIS",
            "<2-3 paragraph synthesis of key findings across all sources>",
            "",
            "### FINDINGS",
            "1. **Claim**: <specific claim>",
            "   **Evidence**: <supporting evidence from sources>",
            "   **Confidence**: <high|medium|low>",
            "",
            "2. **Claim**: <next claim>",
            "   ...",
            "",
            "### HYPOTHESES",
            "1. <follow-up question or hypothesis to investigate next>",
            "   **Priority**: <high|medium|low>",
            "",
            "2. <next hypothesis>",
            "   ...",
            "",
            "Be concise but thorough. Cite sources by number [1], [2], etc.",
            "Focus on facts and evidence, not speculation.",
        ])

        return "\n".join(lines)

    def _parse_research_response(
        self,
        response: str,
        round_number: int,
        sources: list[ResearchSource],
    ) -> tuple[str, list[ResearchFinding], list[ResearchHypothesis]]:
        """Parse structured research response from LLM."""
        synthesis = ""
        findings: list[ResearchFinding] = []
        hypotheses: list[ResearchHypothesis] = []

        sections = response.split("### ")
        current_section = ""

        for section in sections:
            section = section.strip()
            if not section:
                continue

            if section.startswith("SYNTHESIS"):
                synthesis = section.replace("SYNTHESIS", "", 1).strip()
                current_section = "synthesis"
            elif section.startswith("FINDINGS"):
                current_section = "findings"
                findings = self._parse_findings(section, round_number, sources)
            elif section.startswith("HYPOTHESES"):
                current_section = "hypotheses"
                hypotheses = self._parse_hypotheses(section, round_number)
            elif current_section == "synthesis" and not synthesis:
                synthesis = section

        return synthesis, findings, hypotheses

    def _parse_findings(
        self,
        section: str,
        round_number: int,
        sources: list[ResearchSource],
    ) -> list[ResearchFinding]:
        """Parse findings from LLM response section."""
        findings: list[ResearchFinding] = []

        # Split by numbered items
        import re
        pattern = r'\d+\.\s+\*\*Claim\*\*:\s*(.+?)(?=\d+\.\s+\*\*Claim\*\*:|$)'
        matches = re.findall(pattern, section, re.DOTALL)

        for match in matches:
            lines = match.strip().split("\n")
            claim = lines[0].strip()

            evidence = ""
            confidence = 0.5
            source_indices: list[int] = []

            for line in lines[1:]:
                line = line.strip()
                if line.startswith("**Evidence**:"):
                    evidence = line.replace("**Evidence**:", "").strip()
                elif line.startswith("**Confidence**:"):
                    conf_str = line.replace("**Confidence**:", "").strip().lower()
                    confidence = {"high": 0.85, "medium": 0.6, "low": 0.35}.get(conf_str, 0.5)

                # Extract source citations like [1], [2]
                import re
                cited = re.findall(r'\[(\d+)\]', line)
                source_indices.extend(int(x) - 1 for x in cited if x.isdigit())

            findings.append(ResearchFinding(
                claim=claim,
                evidence=evidence,
                confidence=confidence,
                supporting_sources=list(set(source_indices)),
                round_number=round_number,
            ))

        return findings

    def _parse_hypotheses(self, section: str, round_number: int) -> list[ResearchHypothesis]:
        """Parse hypotheses from LLM response section."""
        hypotheses: list[ResearchHypothesis] = []

        import re
        pattern = r'\d+\.\s+(.+?)(?=\d+\.\s+|\*\*Priority\*\*|$)'
        matches = re.findall(pattern, section, re.DOTALL)

        for match in matches:
            lines = match.strip().split("\n")
            hypothesis = lines[0].strip()
            reasoning = ""
            priority = 0.5

            for line in lines[1:]:
                line = line.strip()
                if line.startswith("**Priority**:"):
                    pri_str = line.replace("**Priority**:", "").strip().lower()
                    priority = {"high": 0.85, "medium": 0.6, "low": 0.35}.get(pri_str, 0.5)
                elif line.startswith("**Reasoning**:"):
                    reasoning = line.replace("**Reasoning**:", "").strip()
                elif not reasoning and line:
                    reasoning = line

            hypotheses.append(ResearchHypothesis(
                hypothesis=hypothesis,
                reasoning=reasoning,
                priority=priority,
                round_number=round_number,
            ))

        return hypotheses

    # -- Report Finalization ---------------------------------------------------

    def _aggregate_findings(self, rounds: list[ResearchRound]) -> list[ResearchFinding]:
        """Aggregate and deduplicate findings across all rounds."""
        all_findings: list[ResearchFinding] = []
        seen_claims: set = set()

        for r in rounds:
            for f in r.findings:
                claim_hash = hashlib.sha256(f.claim.encode()).hexdigest()[:16]
                if claim_hash not in seen_claims:
                    seen_claims.add(claim_hash)
                    all_findings.append(f)

        # Sort by confidence descending
        all_findings.sort(key=lambda f: f.confidence, reverse=True)
        return all_findings[:10]  # Top 10

    def _generate_executive_summary(self, report: ResearchReport) -> str:
        """Generate executive summary from all rounds."""
        if not report.rounds:
            return "No research data available."

        summaries = [r.synthesis for r in report.rounds if r.synthesis]
        if not summaries:
            return "Research conducted but no synthesis generated."

        # Combine round summaries
        combined = "\n\n".join(summaries)
        if len(combined) > 2000:
            combined = combined[:2000] + "..."

        return combined

    def _collect_unanswered(self, rounds: list[ResearchRound]) -> list[str]:
        """Collect unanswered questions from hypotheses that weren't pursued."""
        unanswered: list[str] = []
        seen: set = set()

        for r in rounds:
            for h in r.hypotheses:
                if h.priority < 0.5 and h.hypothesis not in seen:
                    seen.add(h.hypothesis)
                    unanswered.append(h.hypothesis)

        return unanswered[:5]  # Max 5

    def _compute_overall_confidence(self, report: ResearchReport) -> float:
        """Compute overall confidence score for the research."""
        if not report.rounds:
            return 0.0

        # Average finding confidence weighted by source count
        all_confidences: list[float] = []
        for r in report.rounds:
            for f in r.findings:
                all_confidences.append(f.confidence)

        if not all_confidences:
            return 0.3  # Low default if no findings

        avg_confidence = sum(all_confidences) / len(all_confidences)

        # Boost for multiple rounds with sources
        source_bonus = min(len(report.all_sources) * 0.02, 0.1)
        round_bonus = min(len(report.rounds) * 0.03, 0.1)

        return min(avg_confidence + source_bonus + round_bonus, 1.0)
