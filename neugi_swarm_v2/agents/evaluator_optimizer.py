"""
Evaluator-Optimizer loop: generate output, evaluate against criteria,
refine iteratively until quality gate is met or max iterations reached.

Pattern: Anthropic's "Evaluator-Optimizer" from Building Effective Agents.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class EvaluationResult:
    """Result of a single evaluation pass."""
    iteration: int
    score: float
    criteria_scores: Dict[str, float]
    feedback: str
    passed: bool
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class EvaluationCriteria:
    """A single evaluation dimension."""
    name: str
    weight: float = 1.0
    description: str = ""
    threshold: float = 0.5


class EvaluatorOptimizer:
    """
    Implements a Generate -> Evaluate -> Refine loop for iterative
    improvement of outputs.

    Especially effective for:
    - Code generation (correctness, style, performance)
    - Content creation (quality, tone, accuracy)
    - Design iterations (usability, aesthetics)

    The loop continues until:
    - The weighted score meets the quality gate, OR
    - Max iterations are reached, OR
    - The evaluator signals no further improvement is possible
    """

    def __init__(
        self,
        generator: Callable[[str, Optional[str]], str],
        evaluator: Callable[[str, str], Tuple[float, str]],
        refiner: Callable[[str, str, float, str], str],
        quality_gate: float = 0.8,
        max_iterations: int = 5,
        criteria: Optional[List[EvaluationCriteria]] = None,
    ) -> None:
        """
        Args:
            generator: (task, previous_output) -> new output
            evaluator: (task, output) -> (score, feedback)
            refiner: (task, output, score, feedback) -> refined output
            quality_gate: minimum weighted score to pass
            max_iterations: maximum refinement cycles
            criteria: list of evaluation dimensions with weights
        """
        self.generator = generator
        self.evaluator = evaluator
        self.refiner = refiner
        self.quality_gate = quality_gate
        self.max_iterations = max_iterations
        self.criteria = criteria or [
            EvaluationCriteria(name="overall", weight=1.0, threshold=quality_gate),
        ]

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    def run(
        self,
        task: str,
        initial_output: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Execute the full evaluator-optimizer loop.

        Returns a dict with final output, all evaluation results,
        and metadata about the run.
        """
        start = time.monotonic()
        history: List[EvaluationResult] = []
        current = initial_output or self.generator(task, None)

        for iteration in range(1, self.max_iterations + 1):
            score, criteria_scores, feedback = self._evaluate(task, current)
            passed = score >= self.quality_gate

            eval_result = EvaluationResult(
                iteration=iteration,
                score=score,
                criteria_scores=criteria_scores,
                feedback=feedback,
                passed=passed,
            )
            history.append(eval_result)

            logger.info(
                "Eval-Opt iteration %d: score=%.3f passed=%s",
                iteration,
                score,
                passed,
            )

            if passed:
                break

            # Check if the evaluator signals no improvement possible
            if "no improvement" in feedback.lower() or "cannot improve" in feedback.lower():
                break

            current = self.refiner(task, current, score, feedback)

        duration = time.monotonic() - start
        final = history[-1] if history else EvaluationResult(
            iteration=0, score=0.0, criteria_scores={}, feedback="", passed=False
        )

        return {
            "task": task,
            "final_output": current,
            "final_score": final.score,
            "passed": final.passed,
            "iterations": len(history),
            "history": [
                {
                    "iteration": h.iteration,
                    "score": h.score,
                    "criteria_scores": h.criteria_scores,
                    "feedback": h.feedback,
                    "passed": h.passed,
                    "timestamp": h.timestamp,
                }
                for h in history
            ],
            "quality_gate": self.quality_gate,
            "max_iterations": self.max_iterations,
            "duration_seconds": round(duration, 3),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Evaluation
    # ------------------------------------------------------------------

    def _evaluate(
        self, task: str, output: str
    ) -> Tuple[float, Dict[str, float], str]:
        """
        Evaluate output against all criteria and compute weighted score.
        """
        raw_score, feedback = self.evaluator(task, output)

        # If the evaluator returns per-criteria scores, use them
        if isinstance(raw_score, dict):
            criteria_scores = raw_score
        else:
            criteria_scores = {"overall": float(raw_score)}

        weighted = self._weighted_score(criteria_scores)
        return weighted, criteria_scores, feedback

    def _weighted_score(self, criteria_scores: Dict[str, float]) -> float:
        """Compute weighted average across criteria."""
        total_weight = 0.0
        total_score = 0.0
        for crit in self.criteria:
            score = criteria_scores.get(crit.name, 0.0)
            total_score += score * crit.weight
            total_weight += crit.weight
        if total_weight == 0:
            return 0.0
        return round(total_score / total_weight, 4)

    # ------------------------------------------------------------------
    # Self-review
    # ------------------------------------------------------------------

    def self_review(
        self,
        task: str,
        output: str,
        review_prompt_template: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Perform a self-review of an output without refinement.
        Useful for one-off quality checks.
        """
        score, criteria_scores, feedback = self._evaluate(task, output)
        return {
            "task": task,
            "output": output,
            "score": score,
            "criteria_scores": criteria_scores,
            "feedback": feedback,
            "passed": score >= self.quality_gate,
            "quality_gate": self.quality_gate,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    # ------------------------------------------------------------------
    # Batch mode
    # ------------------------------------------------------------------

    def run_batch(
        self,
        tasks: List[str],
        context: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Run the evaluator-optimizer loop on multiple tasks."""
        return [self.run(task, context=context) for task in tasks]

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    def add_criterion(self, name: str, weight: float = 1.0, threshold: float = 0.5, description: str = "") -> None:
        """Add an evaluation criterion."""
        self.criteria.append(
            EvaluationCriteria(
                name=name, weight=weight, threshold=threshold, description=description
            )
        )

    def set_quality_gate(self, gate: float) -> None:
        """Change the minimum passing score."""
        self.quality_gate = max(0.0, min(1.0, gate))

    def set_max_iterations(self, n: int) -> None:
        """Change the maximum number of refinement iterations."""
        self.max_iterations = max(1, n)
