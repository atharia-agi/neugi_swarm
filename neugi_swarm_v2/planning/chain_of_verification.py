#!/usr/bin/env python3
"""
NEUGI v2 - Chain of Verification
=================================

Self-factifying response generation through iterative verification.

Based on: "Chain-of-Verification Reduces Hallucination in LLMs"
(Dhuliawala et al., 2023)

Key features:
- Generate initial response to a query
- Extract verification questions from the response
- Answer verification questions independently (no access to original)
- Compare verification answers with original claims
- Revise response based on verification results
- Iterative refinement until confidence threshold met

Usage:
    cov = ChainOfVerification(llm_callback, config=CoVConfig())
    result = await cov.verify(
        query="What are the key differences between Python 3.11 and 3.12?",
    )
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class VerificationState(Enum):
    """State of the verification process."""

    INITIAL_RESPONSE = "initial_response"
    QUESTIONS_GENERATED = "questions_generated"
    VERIFIED = "verified"
    REVISED = "revised"
    CONFIDENT = "confident"
    EXHAUSTED = "exhausted"


@dataclass
class VerificationQuestion:
    """A question to verify a specific claim from the response.

    Args:
        question: The verification question.
        claim: The original claim being verified.
        claim_span: The exact text span from the original response.
        question_id: Unique identifier.
    """

    question: str
    claim: str
    claim_span: str
    question_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])


@dataclass
class VerificationAnswer:
    """Answer to a verification question.

    Args:
        question_id: ID of the question this answers.
        answer: The independently generated answer.
        supports_claim: Whether the answer supports the original claim.
        confidence: Confidence in this verification (0.0-1.0).
        discrepancy: Description of any discrepancy found.
    """

    question_id: str
    answer: str
    supports_claim: bool = True
    confidence: float = 1.0
    discrepancy: str = ""


@dataclass
class CoVConfig:
    """Configuration for Chain of Verification.

    Args:
        max_iterations: Maximum verification-revision cycles.
        questions_per_round: Number of verification questions per round.
        confidence_threshold: Minimum confidence to stop iterating.
        min_questions: Minimum questions to generate (even if few claims).
        max_questions: Maximum questions to generate per round.
        independent_verification: Answer questions without original context.
        include_reasoning: Include reasoning in verification questions.
        temperature_initial: Temperature for initial response.
        temperature_verification: Temperature for verification (lower = more factual).
    """

    max_iterations: int = 3
    questions_per_round: int = 5
    confidence_threshold: float = 0.85
    min_questions: int = 2
    max_questions: int = 10
    independent_verification: bool = True
    include_reasoning: bool = True
    temperature_initial: float = 0.7
    temperature_verification: float = 0.3
    timeout_seconds: float = 180.0


@dataclass
class CoVResult:
    """Result from a Chain of Verification process.

    Args:
        original_response: The initial unverified response.
        final_response: The verified and revised response.
        questions: All verification questions generated.
        answers: All verification answers received.
        revisions: Number of revision cycles performed.
        confidence: Overall confidence in the final response.
        discrepancies: List of discrepancies found and corrected.
        state: Final state of the verification process.
        iterations: Number of iterations performed.
        total_time: Total time spent in seconds.
        verified_claims: Number of claims that were verified.
        corrected_claims: Number of claims that were corrected.
    """

    original_response: str
    final_response: str
    questions: List[VerificationQuestion] = field(default_factory=list)
    answers: List[VerificationAnswer] = field(default_factory=list)
    revisions: int = 0
    confidence: float = 0.0
    discrepancies: List[str] = field(default_factory=list)
    state: VerificationState = VerificationState.INITIAL_RESPONSE
    iterations: int = 0
    total_time: float = 0.0
    verified_claims: int = 0
    corrected_claims: int = 0


class ChainOfVerification:
    """Chain of Verification for reducing hallucination in LLM responses.

    Generates an initial response, extracts verification questions, answers
    them independently, compares results, and revises the response.

    Works with any LLM provider through callback functions.

    Args:
        llm_callback: Async callable that takes a prompt and returns text.
            Signature: (prompt: str) -> Awaitable[str]
        config: Verification configuration.
    """

    def __init__(
        self,
        llm_callback: Callable[[str], Awaitable[str]],
        config: Optional[CoVConfig] = None,
    ) -> None:
        self.llm_callback = llm_callback
        self.config = config or CoVConfig()
        self._start_time = 0.0

    async def verify(
        self,
        query: str,
        context: str = "",
        custom_question_generator: Optional[
            Callable[[str, str], Awaitable[List[VerificationQuestion]]]
        ] = None,
        custom_verifier: Optional[
            Callable[[VerificationQuestion, str], Awaitable[VerificationAnswer]]
        ] = None,
        custom_comparator: Optional[
            Callable[
                [List[VerificationQuestion], List[VerificationAnswer], str],
                Awaitable[tuple[float, List[str]]],
            ]
        ] = None,
    ) -> CoVResult:
        """Run chain of verification on a query.

        Args:
            query: The query to answer and verify.
            context: Optional background context for the query.
            custom_question_generator: Custom function to generate verification questions.
            custom_verifier: Custom function to answer verification questions.
            custom_comparator: Custom function to compare answers with claims.

        Returns:
            CoVResult with verified response and metadata.
        """
        self._start_time = time.time()

        result = CoVResult(
            original_response="",
            final_response="",
        )

        try:
            initial = await self._generate_initial_response(query, context)
            result.original_response = initial
            result.state = VerificationState.INITIAL_RESPONSE

            current_response = initial

            for iteration in range(self.config.max_iterations):
                result.iterations = iteration + 1

                if self._should_terminate(result):
                    result.state = VerificationState.CONFIDENT
                    break

                questions = await self._generate_questions(
                    query, current_response, custom_question_generator
                )
                if not questions:
                    result.state = VerificationState.EXHAUSTED
                    break

                result.questions.extend(questions)
                result.state = VerificationState.QUESTIONS_GENERATED

                answers = await self._verify_questions(
                    questions, context, custom_verifier
                )
                result.answers.extend(answers)
                result.state = VerificationState.VERIFIED

                confidence, discrepancies = await self._compare_and_score(
                    questions, answers, current_response, custom_comparator
                )

                result.discrepancies.extend(discrepancies)
                result.verified_claims += sum(
                    1 for a in answers if a.supports_claim
                )
                result.corrected_claims += sum(
                    1 for a in answers if not a.supports_claim
                )

                if discrepancies:
                    revised = await self._revise_response(
                        query, current_response, questions, answers, discrepancies
                    )
                    current_response = revised
                    result.revisions += 1
                    result.state = VerificationState.REVISED
                else:
                    result.state = VerificationState.CONFIDENT

                result.confidence = confidence
                result.final_response = current_response

                if confidence >= self.config.confidence_threshold:
                    result.state = VerificationState.CONFIDENT
                    break

            result.final_response = current_response
            result.total_time = time.time() - self._start_time

        except Exception as e:
            logger.error("Chain of Verification failed: %s", e)
            result.final_response = result.original_response
            result.total_time = time.time() - self._start_time
            result.state = VerificationState.EXHAUSTED

        return result

    async def _generate_initial_response(
        self, query: str, context: str
    ) -> str:
        prompt = self._build_initial_prompt(query, context)
        try:
            return await self.llm_callback(prompt)
        except Exception as e:
            logger.warning("Initial response generation failed: %s", e)
            return f"Unable to generate initial response: {e}"

    async def _generate_questions(
        self,
        query: str,
        response: str,
        custom_generator: Optional[Callable[[str, str], Awaitable[List[VerificationQuestion]]]],
    ) -> List[VerificationQuestion]:
        if custom_generator is not None:
            return await custom_generator(query, response)

        prompt = self._build_question_prompt(query, response)
        try:
            text = await self.llm_callback(prompt)
            return self._parse_questions(text)
        except Exception as e:
            logger.warning("Question generation failed: %s", e)
            return []

    async def _verify_questions(
        self,
        questions: List[VerificationQuestion],
        context: str,
        custom_verifier: Optional[Callable[[VerificationQuestion, str], Awaitable[VerificationAnswer]]],
    ) -> List[VerificationAnswer]:
        answers: List[VerificationAnswer] = []

        for question in questions:
            if custom_verifier is not None:
                answer = await custom_verifier(question, context)
                answers.append(answer)
                continue

            prompt = self._build_verification_prompt(question, context)
            try:
                text = await self.llm_callback(prompt)
                parsed = self._parse_verification_answer(question.question_id, text)
                answers.append(parsed)
            except Exception as e:
                logger.warning(
                    "Verification failed for question %s: %s",
                    question.question_id,
                    e,
                )
                answers.append(
                    VerificationAnswer(
                        question_id=question.question_id,
                        answer=f"Verification failed: {e}",
                        supports_claim=False,
                        confidence=0.0,
                        discrepancy=str(e),
                    )
                )

        return answers

    async def _compare_and_score(
        self,
        questions: List[VerificationQuestion],
        answers: List[VerificationAnswer],
        response: str,
        custom_comparator: Optional[
            Callable[
                [List[VerificationQuestion], List[VerificationAnswer], str],
                Awaitable[tuple[float, List[str]]],
            ]
        ],
    ) -> tuple[float, List[str]]:
        if custom_comparator is not None:
            return await custom_comparator(questions, answers, response)

        discrepancies: List[str] = []
        supporting = 0
        total = len(answers)

        for question, answer in zip(questions, answers):
            if answer.supports_claim:
                supporting += 1
            else:
                disc = f"Claim: '{question.claim_span}' - "
                disc += f"Verification says: '{answer.answer}'"
                if answer.discrepancy:
                    disc += f" ({answer.discrepancy})"
                discrepancies.append(disc)

        confidence = supporting / total if total > 0 else 0.0

        if self.config.include_reasoning and discrepancies:
            try:
                comparison_prompt = self._build_comparison_prompt(
                    questions, answers, response
                )
                comparison_text = await self.llm_callback(comparison_prompt)
                parsed_discs = self._parse_discrepancies(comparison_text)
                discrepancies.extend(parsed_discs)
            except Exception as e:
                logger.warning("Comparison analysis failed: %s", e)

        return confidence, discrepancies

    async def _revise_response(
        self,
        query: str,
        original: str,
        questions: List[VerificationQuestion],
        answers: List[VerificationAnswer],
        discrepancies: List[str],
    ) -> str:
        prompt = self._build_revision_prompt(
            query, original, questions, answers, discrepancies
        )
        try:
            return await self.llm_callback(prompt)
        except Exception as e:
            logger.warning("Response revision failed: %s", e)
            return original

    def _build_initial_prompt(self, query: str, context: str) -> str:
        base = f"Query: {query}\n\n"
        if context:
            base += f"Context:\n{context}\n\n"
        base += (
            "Provide a comprehensive, accurate response. "
            "Be specific with facts, dates, numbers, and names. "
            "If uncertain about any detail, state your uncertainty.\n\n"
            "Response:"
        )
        return base

    def _build_question_prompt(self, query: str, response: str) -> str:
        return (
            f"Original query: {query}\n\n"
            f"Response to verify:\n{response}\n\n"
            f"Extract {self.config.questions_per_round} specific, factual claims "
            f"from this response that can be independently verified. "
            f"Focus on:\n"
            f"- Specific facts (dates, numbers, names, statistics)\n"
            f"- Causal relationships and mechanisms\n"
            f"- Comparisons and rankings\n"
            f"- Technical specifications\n\n"
            f"Format each as:\n"
            f"CLAIM: <exact claim from response>\n"
            f"SPAN: <exact text span>\n"
            f"QUESTION: <verification question>\n\n"
        )

    def _build_verification_prompt(
        self, question: VerificationQuestion, context: str
    ) -> str:
        base = "Answer the following question based on your knowledge."
        if self.config.independent_verification:
            base += " Do NOT reference any previous response."
        base += "\n\n"

        if context:
            base += f"Context:\n{context}\n\n"

        base += f"Question: {question.question}\n\n"
        base += (
            "Answer concisely and factually. If you are uncertain, "
            "state your uncertainty clearly.\n\n"
            "Answer: "
        )
        return base

    def _build_comparison_prompt(
        self,
        questions: List[VerificationQuestion],
        answers: List[VerificationAnswer],
        response: str,
    ) -> str:
        qa_pairs = "\n".join(
            f"Q: {q.question}\nA: {a.answer}\nSupports: {'Yes' if a.supports_claim else 'No'}\n"
            for q, a in zip(questions, answers)
        )

        return (
            f"Original response:\n{response}\n\n"
            f"Verification results:\n{qa_pairs}\n\n"
            f"Identify any discrepancies between the original response "
            f"and the verification answers. List each discrepancy as:\n"
            f"DISCREPANCY: <description of what was wrong>\n"
            f"CORRECTION: <what the correct information should be>\n\n"
        )

    def _build_revision_prompt(
        self,
        query: str,
        original: str,
        questions: List[VerificationQuestion],
        answers: List[VerificationAnswer],
        discrepancies: List[str],
    ) -> str:
        verified = "\n".join(
            f"- {q.question} -> {a.answer} ({'confirmed' if a.supports_claim else 'disputed'})"
            for q, a in zip(questions, answers)
        )

        disc_text = "\n".join(f"- {d}" for d in discrepancies)

        return (
            f"Original query: {query}\n\n"
            f"Your original response:\n{original}\n\n"
            f"Verification findings:\n{verified}\n\n"
            f"Discrepancies found:\n{disc_text}\n\n"
            f"Revise your original response to correct any inaccuracies "
            f"identified during verification. Keep confirmed information "
            f"intact. Only change what was shown to be incorrect.\n\n"
            f"Revised response:"
        )

    def _parse_questions(self, text: str) -> List[VerificationQuestion]:
        questions: List[VerificationQuestion] = []
        lines = text.strip().split("\n")

        current_claim = ""
        current_span = ""
        current_question = ""

        for line in lines:
            line = line.strip()
            if line.upper().startswith("CLAIM:"):
                current_claim = line[6:].strip()
            elif line.upper().startswith("SPAN:"):
                current_span = line[5:].strip()
            elif line.upper().startswith("QUESTION:"):
                current_question = line[9:].strip()
                if current_claim and current_question:
                    questions.append(
                        VerificationQuestion(
                            question=current_question,
                            claim=current_claim,
                            claim_span=current_span or current_claim,
                        )
                    )
                    current_claim = ""
                    current_span = ""
                    current_question = ""

        if len(questions) < self.config.min_questions:
            questions = self._fallback_parse_questions(text)

        return questions[: self.config.max_questions]

    def _fallback_parse_questions(self, text: str) -> List[VerificationQuestion]:
        questions: List[VerificationQuestion] = []
        sentences = [
            s.strip()
            for s in text.replace("\n", " ").split(".")
            if s.strip() and "?" in s
        ]
        for i, sentence in enumerate(
            sentences[: self.config.questions_per_round]
        ):
            questions.append(
                VerificationQuestion(
                    question=sentence.rstrip("?") + "?",
                    claim=sentence,
                    claim_span=sentence,
                )
            )
        return questions

    def _parse_verification_answer(
        self, question_id: str, text: str
    ) -> VerificationAnswer:
        text = text.strip()
        lower = text.lower()

        supports = not any(
            kw in lower
            for kw in [
                "uncertain",
                "don't know",
                "cannot confirm",
                "no evidence",
                "incorrect",
                "false",
                "not accurate",
                "disputed",
                "contradicts",
            ]
        )

        confidence = 1.0
        if any(kw in lower for kw in ["uncertain", "not sure", "likely"]):
            confidence = 0.6
        elif any(kw in lower for kw in ["possibly", "may", "might"]):
            confidence = 0.5
        elif any(kw in lower for kw in ["incorrect", "false", "wrong"]):
            confidence = 0.2
            supports = False

        discrepancy = ""
        if not supports:
            discrepancy = "Verification contradicts the original claim"

        return VerificationAnswer(
            question_id=question_id,
            answer=text,
            supports_claim=supports,
            confidence=confidence,
            discrepancy=discrepancy,
        )

    def _parse_discrepancies(self, text: str) -> List[str]:
        discrepancies: List[str] = []
        lines = text.strip().split("\n")

        for line in lines:
            line = line.strip()
            if line.upper().startswith("DISCREPANCY:"):
                disc = line[12:].strip()
                discrepancies.append(disc)

        return discrepancies

    def _should_terminate(self, result: CoVResult) -> bool:
        if result.confidence >= self.config.confidence_threshold:
            return True
        elapsed = time.time() - self._start_time
        if elapsed >= self.config.timeout_seconds:
            return True
        return False

    def get_verification_report(self, result: CoVResult) -> str:
        lines = [
            "Chain of Verification Report",
            "=" * 40,
            f"State: {result.state.value}",
            f"Iterations: {result.iterations}",
            f"Revisions: {result.revisions}",
            f"Confidence: {result.confidence:.2%}",
            f"Questions generated: {len(result.questions)}",
            f"Claims verified: {result.verified_claims}",
            f"Claims corrected: {result.corrected_claims}",
            f"Discrepancies found: {len(result.discrepancies)}",
            f"Time: {result.total_time:.1f}s",
            "",
            "Verification Details:",
            "-" * 40,
        ]

        for q, a in zip(result.questions, result.answers):
            status = "✓" if a.supports_claim else "✗"
            lines.append(f"  {status} {q.question}")
            lines.append(f"    Claim: {q.claim_span}")
            lines.append(f"    Answer: {a.answer[:100]}")
            if a.discrepancy:
                lines.append(f"    Issue: {a.discrepancy}")
            lines.append("")

        if result.discrepancies:
            lines.append("Discrepancies:")
            lines.append("-" * 40)
            for d in result.discrepancies:
                lines.append(f"  - {d}")
            lines.append("")

        lines.append("Final Response:")
        lines.append("-" * 40)
        lines.append(result.final_response)

        return "\n".join(lines)
