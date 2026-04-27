#!/usr/bin/env python3
"""
NEUGI v2 - Tree of Thoughts Planning
=====================================

Multi-branch thought exploration with best-first search, pruning,
backtracking, and solution extraction.

Based on: "Tree of Thoughts: Deliberate Problem Solving with LLMs"
(Yao et al., 2023)

Key features:
- Generate multiple thought branches at each step
- LLM-based evaluation and scoring of each branch
- Prune low-scoring branches to manage complexity
- Backtrack to promising branches when stuck
- Configurable branching factor and search depth
- Best-first search strategy by default
- Solution extraction from the best leaf node

Usage:
    tot = TreeOfThoughts(llm_callback, config=ToTConfig())
    result = await tot.solve(
        problem="Solve the 24 game with [4, 6, 8, 9]",
        thought_generator=generate_thoughts,
        evaluator=evaluate_thoughts,
    )
"""

from __future__ import annotations

import asyncio
import heapq
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence

logger = logging.getLogger(__name__)


class SearchStrategy(Enum):
    """Search strategy for tree traversal."""

    BEST_FIRST = "best_first"
    BREADTH_FIRST = "breadth_first"
    DEPTH_FIRST = "depth_first"
    BEAM_SEARCH = "beam_search"
    MONTE_CARLO = "monte_carlo"


class ThoughtState(Enum):
    """State of a thought node in the tree."""

    PENDING = "pending"
    EXPLORED = "explored"
    PRUNED = "pruned"
    SOLUTION = "solution"
    DEAD_END = "dead_end"


@dataclass
class ThoughtNode:
    """A single node in the tree of thoughts.

    Each node represents a partial solution or reasoning step.
    """

    thought: str
    node_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    parent_id: Optional[str] = None
    children: List[str] = field(default_factory=list)
    score: float = 0.0
    state: ThoughtState = ThoughtState.PENDING
    depth: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def is_root(self) -> bool:
        return self.parent_id is None

    def is_leaf(self) -> bool:
        return len(self.children) == 0

    def path_from_root(self, tree: Dict[str, "ThoughtNode"]) -> List["ThoughtNode"]:
        path: List[ThoughtNode] = []
        current: Optional[ThoughtNode] = self
        while current is not None:
            path.append(current)
            if current.parent_id is None:
                break
            current = tree.get(current.parent_id)
        path.reverse()
        return path

    def __lt__(self, other: "ThoughtNode") -> bool:
        return self.score < other.score

    def __le__(self, other: "ThoughtNode") -> bool:
        return self.score <= other.score


@dataclass
class ThoughtBranch:
    """A complete branch from root to leaf."""

    nodes: List[ThoughtNode]
    final_score: float
    is_solution: bool = False

    @property
    def thought_chain(self) -> str:
        return "\n".join(
            f"Step {i}: {n.thought} (score={n.score:.3f})"
            for i, n in enumerate(self.nodes)
        )

    @property
    def depth(self) -> int:
        return len(self.nodes) - 1


@dataclass
class ToTConfig:
    """Configuration for Tree of Thoughts search.

    Args:
        branching_factor: Number of thoughts to generate at each step.
        max_depth: Maximum depth of the search tree.
        pruning_threshold: Score below which branches are pruned.
        beam_width: Number of top branches to keep (for beam search).
        search_strategy: Strategy for tree traversal.
        max_iterations: Maximum total node expansions.
        solution_threshold: Score at which a node is considered a solution.
        backtrack_threshold: Score below which to force backtracking.
        enable_monte_carlo: Whether to use Monte Carlo rollouts for scoring.
        mc_rollout_depth: Depth of Monte Carlo rollouts.
        mc_rollouts: Number of Monte Carlo rollouts per node.
    """

    branching_factor: int = 3
    max_depth: int = 5
    pruning_threshold: float = 0.1
    beam_width: int = 5
    search_strategy: SearchStrategy = SearchStrategy.BEST_FIRST
    max_iterations: int = 100
    solution_threshold: float = 0.9
    backtrack_threshold: float = 0.2
    enable_monte_carlo: bool = False
    mc_rollout_depth: int = 3
    mc_rollouts: int = 5
    timeout_seconds: float = 120.0


@dataclass
class ToTResult:
    """Result from a Tree of Thoughts search.

    Args:
        solution: The best solution found (thought chain).
        solution_score: Confidence score of the solution.
        nodes_explored: Total nodes expanded during search.
        nodes_pruned: Total nodes pruned during search.
        branches_explored: Total complete branches explored.
        search_time: Total search time in seconds.
        best_branch: The best complete branch found.
        all_branches: All complete branches found.
        terminated_by: Reason search terminated.
        metadata: Additional search metadata.
    """

    solution: str
    solution_score: float
    nodes_explored: int = 0
    nodes_pruned: int = 0
    branches_explored: int = 0
    search_time: float = 0.0
    best_branch: Optional[ThoughtBranch] = None
    all_branches: List[ThoughtBranch] = field(default_factory=list)
    terminated_by: str = "solution_found"
    metadata: Dict[str, Any] = field(default_factory=dict)


class TreeOfThoughts:
    """Tree of Thoughts planner for deliberate problem solving.

    Explores multiple reasoning paths simultaneously, evaluates each path,
    prunes unpromising branches, and extracts the best solution.

    Works with any LLM provider through callback functions.

    Args:
        llm_callback: Async callable that takes a prompt and returns text.
            Signature: (prompt: str) -> Awaitable[str]
        config: Search configuration.
    """

    def __init__(
        self,
        llm_callback: Callable[[str], Awaitable[str]],
        config: Optional[ToTConfig] = None,
    ) -> None:
        self.llm_callback = llm_callback
        self.config = config or ToTConfig()
        self._tree: Dict[str, ThoughtNode] = {}
        self._root_id: Optional[str] = None
        self._nodes_explored = 0
        self._nodes_pruned = 0
        self._branches: List[ThoughtBranch] = []
        self._start_time = 0.0

    async def solve(
        self,
        problem: str,
        thought_generator: Optional[
            Callable[[str, List[str], int], Awaitable[List[str]]]
        ] = None,
        evaluator: Optional[
            Callable[[str, str, int], Awaitable[float]]
        ] = None,
        solution_checker: Optional[
            Callable[[str], Awaitable[bool]]
        ] = None,
    ) -> ToTResult:
        """Solve a problem using tree of thoughts search.

        Args:
            problem: The problem statement to solve.
            thought_generator: Custom function to generate thoughts.
                Signature: (problem, context_thoughts, depth) -> [thought_strings]
            evaluator: Custom function to evaluate a thought.
                Signature: (problem, thought, depth) -> score (0.0-1.0)
            solution_checker: Custom function to check if a thought chain solves the problem.
                Signature: (thought_chain) -> bool

        Returns:
            ToTResult with the best solution found.
        """
        self._tree.clear()
        self._root_id = None
        self._nodes_explored = 0
        self._nodes_pruned = 0
        self._branches.clear()
        self._start_time = time.time()

        root = ThoughtNode(thought=problem, depth=0)
        self._tree[root.node_id] = root
        self._root_id = root.node_id

        try:
            if self.config.search_strategy == SearchStrategy.BEST_FIRST:
                await self._best_first_search(
                    problem, thought_generator, evaluator, solution_checker
                )
            elif self.config.search_strategy == SearchStrategy.BREADTH_FIRST:
                await self._breadth_first_search(
                    problem, thought_generator, evaluator, solution_checker
                )
            elif self.config.search_strategy == SearchStrategy.DEPTH_FIRST:
                await self._depth_first_search(
                    problem, thought_generator, evaluator, solution_checker
                )
            elif self.config.search_strategy == SearchStrategy.BEAM_SEARCH:
                await self._beam_search(
                    problem, thought_generator, evaluator, solution_checker
                )
            elif self.config.search_strategy == SearchStrategy.MONTE_CARLO:
                await self._monte_carlo_search(
                    problem, thought_generator, evaluator, solution_checker
                )
        except asyncio.TimeoutError:
            logger.info("Tree of Thoughts search timed out")
        except Exception as e:
            logger.error("Tree of Thoughts search error: %s", e)

        return self._build_result()

    async def _best_first_search(
        self,
        problem: str,
        thought_generator: Optional[Callable[[str, List[str], int], Awaitable[List[str]]]],
        evaluator: Optional[Callable[[str, str, int], Awaitable[float]]],
        solution_checker: Optional[Callable[[str], Awaitable[bool]]],
    ) -> None:
        priority_queue: List[tuple] = []
        root = self._tree[self._root_id]
        heapq.heappush(priority_queue, (-root.score, root.node_id))

        while priority_queue and not self._should_terminate():
            neg_score, node_id = heapq.heappop(priority_queue)
            node = self._tree.get(node_id)
            if node is None or node.state != ThoughtState.PENDING:
                continue

            node.state = ThoughtState.EXPLORED
            self._nodes_explored += 1

            if node.depth >= self.config.max_depth:
                node.state = ThoughtState.DEAD_END
                self._record_branch(node)
                continue

            thoughts = await self._generate_thoughts(
                problem, node, thought_generator
            )
            if not thoughts:
                node.state = ThoughtState.DEAD_END
                self._record_branch(node)
                continue

            for thought_text in thoughts:
                child = ThoughtNode(
                    thought=thought_text,
                    parent_id=node_id,
                    depth=node.depth + 1,
                )
                child.score = await self._evaluate_thought(
                    problem, child, evaluator
                )

                if child.score < self.config.pruning_threshold:
                    child.state = ThoughtState.PRUNED
                    self._nodes_pruned += 1
                    self._tree[child.node_id] = child
                    node.children.append(child.node_id)
                    continue

                if solution_checker and await solution_checker(
                    self._build_chain(child)
                ):
                    child.state = ThoughtState.SOLUTION
                    self._tree[child.node_id] = child
                    node.children.append(child.node_id)
                    self._record_branch(child)
                    return

                if child.score >= self.config.solution_threshold:
                    child.state = ThoughtState.SOLUTION
                    self._tree[child.node_id] = child
                    node.children.append(child.node_id)
                    self._record_branch(child)
                    return

                self._tree[child.node_id] = child
                node.children.append(child.node_id)
                heapq.heappush(priority_queue, (-child.score, child.node_id))

    async def _breadth_first_search(
        self,
        problem: str,
        thought_generator: Optional[Callable[[str, List[str], int], Awaitable[List[str]]]],
        evaluator: Optional[Callable[[str, str, int], Awaitable[float]]],
        solution_checker: Optional[Callable[[str], Awaitable[bool]]],
    ) -> None:
        queue: List[str] = [self._root_id]

        while queue and not self._should_terminate():
            level_nodes = list(queue)
            queue.clear()

            for node_id in level_nodes:
                node = self._tree.get(node_id)
                if node is None or node.state != ThoughtState.PENDING:
                    continue

                node.state = ThoughtState.EXPLORED
                self._nodes_explored += 1

                if node.depth >= self.config.max_depth:
                    node.state = ThoughtState.DEAD_END
                    self._record_branch(node)
                    continue

                thoughts = await self._generate_thoughts(
                    problem, node, thought_generator
                )
                if not thoughts:
                    node.state = ThoughtState.DEAD_END
                    self._record_branch(node)
                    continue

                for thought_text in thoughts:
                    child = ThoughtNode(
                        thought=thought_text,
                        parent_id=node_id,
                        depth=node.depth + 1,
                    )
                    child.score = await self._evaluate_thought(
                        problem, child, evaluator
                    )

                    if child.score < self.config.pruning_threshold:
                        child.state = ThoughtState.PRUNED
                        self._nodes_pruned += 1
                        self._tree[child.node_id] = child
                        node.children.append(child.node_id)
                        continue

                    if solution_checker and await solution_checker(
                        self._build_chain(child)
                    ):
                        child.state = ThoughtState.SOLUTION
                        self._tree[child.node_id] = child
                        node.children.append(child.node_id)
                        self._record_branch(child)
                        return

                    if child.score >= self.config.solution_threshold:
                        child.state = ThoughtState.SOLUTION
                        self._tree[child.node_id] = child
                        node.children.append(child.node_id)
                        self._record_branch(child)
                        return

                    self._tree[child.node_id] = child
                    node.children.append(child.node_id)
                    queue.append(child.node_id)

    async def _depth_first_search(
        self,
        problem: str,
        thought_generator: Optional[Callable[[str, List[str], int], Awaitable[List[str]]]],
        evaluator: Optional[Callable[[str, str, int], Awaitable[float]]],
        solution_checker: Optional[Callable[[str], Awaitable[bool]]],
    ) -> None:
        stack: List[str] = [self._root_id]

        while stack and not self._should_terminate():
            node_id = stack.pop()
            node = self._tree.get(node_id)
            if node is None or node.state != ThoughtState.PENDING:
                continue

            node.state = ThoughtState.EXPLORED
            self._nodes_explored += 1

            if node.depth >= self.config.max_depth:
                node.state = ThoughtState.DEAD_END
                self._record_branch(node)
                continue

            thoughts = await self._generate_thoughts(
                problem, node, thought_generator
            )
            if not thoughts:
                node.state = ThoughtState.DEAD_END
                self._record_branch(node)
                continue

            for thought_text in reversed(thoughts):
                child = ThoughtNode(
                    thought=thought_text,
                    parent_id=node_id,
                    depth=node.depth + 1,
                )
                child.score = await self._evaluate_thought(
                    problem, child, evaluator
                )

                if child.score < self.config.pruning_threshold:
                    child.state = ThoughtState.PRUNED
                    self._nodes_pruned += 1
                    self._tree[child.node_id] = child
                    node.children.append(child.node_id)
                    continue

                if solution_checker and await solution_checker(
                    self._build_chain(child)
                ):
                    child.state = ThoughtState.SOLUTION
                    self._tree[child.node_id] = child
                    node.children.append(child.node_id)
                    self._record_branch(child)
                    return

                if child.score >= self.config.solution_threshold:
                    child.state = ThoughtState.SOLUTION
                    self._tree[child.node_id] = child
                    node.children.append(child.node_id)
                    self._record_branch(child)
                    return

                self._tree[child.node_id] = child
                node.children.append(child.node_id)
                stack.append(child.node_id)

    async def _beam_search(
        self,
        problem: str,
        thought_generator: Optional[Callable[[str, List[str], int], Awaitable[List[str]]]],
        evaluator: Optional[Callable[[str, str, int], Awaitable[float]]],
        solution_checker: Optional[Callable[[str], Awaitable[bool]]],
    ) -> None:
        beam: List[ThoughtNode] = [self._tree[self._root_id]]

        for depth_level in range(self.config.max_depth):
            if not beam or self._should_terminate():
                break

            candidates: List[ThoughtNode] = []

            for node in beam:
                if node.state != ThoughtState.PENDING:
                    continue

                node.state = ThoughtState.EXPLORED
                self._nodes_explored += 1

                thoughts = await self._generate_thoughts(
                    problem, node, thought_generator
                )
                if not thoughts:
                    node.state = ThoughtState.DEAD_END
                    self._record_branch(node)
                    continue

                for thought_text in thoughts:
                    child = ThoughtNode(
                        thought=thought_text,
                        parent_id=node.node_id,
                        depth=node.depth + 1,
                    )
                    child.score = await self._evaluate_thought(
                        problem, child, evaluator
                    )

                    if child.score < self.config.pruning_threshold:
                        child.state = ThoughtState.PRUNED
                        self._nodes_pruned += 1
                        self._tree[child.node_id] = child
                        node.children.append(child.node_id)
                        continue

                    if solution_checker and await solution_checker(
                        self._build_chain(child)
                    ):
                        child.state = ThoughtState.SOLUTION
                        self._tree[child.node_id] = child
                        node.children.append(child.node_id)
                        self._record_branch(child)
                        return

                    if child.score >= self.config.solution_threshold:
                        child.state = ThoughtState.SOLUTION
                        self._tree[child.node_id] = child
                        node.children.append(child.node_id)
                        self._record_branch(child)
                        return

                    self._tree[child.node_id] = child
                    node.children.append(child.node_id)
                    candidates.append(child)

            candidates.sort(key=lambda n: n.score, reverse=True)
            beam = candidates[: self.config.beam_width]

            for node in beam:
                self._record_branch(node)

    async def _monte_carlo_search(
        self,
        problem: str,
        thought_generator: Optional[Callable[[str, List[str], int], Awaitable[List[str]]]],
        evaluator: Optional[Callable[[str, str, int], Awaitable[float]]],
        solution_checker: Optional[Callable[[str], Awaitable[bool]]],
    ) -> None:
        root = self._tree[self._root_id]
        root.state = ThoughtState.EXPLORED
        self._nodes_explored += 1

        thoughts = await self._generate_thoughts(
            problem, root, thought_generator
        )
        if not thoughts:
            return

        for thought_text in thoughts:
            child = ThoughtNode(
                thought=thought_text,
                parent_id=root.node_id,
                depth=1,
            )
            child.score = await self._monte_carlo_evaluate(
                problem, child, evaluator, solution_checker
            )

            if child.score < self.config.pruning_threshold:
                child.state = ThoughtState.PRUNED
                self._nodes_pruned += 1
            elif child.score >= self.config.solution_threshold:
                child.state = ThoughtState.SOLUTION
            else:
                child.state = ThoughtState.EXPLORED

            self._tree[child.node_id] = child
            root.children.append(child.node_id)
            self._record_branch(child)

    async def _monte_carlo_evaluate(
        self,
        problem: str,
        node: ThoughtNode,
        evaluator: Optional[Callable[[str, str, int], Awaitable[float]]],
        solution_checker: Optional[Callable[[str], Awaitable[bool]]],
    ) -> float:
        scores: List[float] = []

        for _ in range(self.config.mc_rollouts):
            rollout_score = await self._evaluate_thought(problem, node, evaluator)
            chain = self._build_chain(node)

            if solution_checker and await solution_checker(chain):
                rollout_score = max(rollout_score, 0.95)

            scores.append(rollout_score)

        return sum(scores) / len(scores) if scores else 0.0

    async def _generate_thoughts(
        self,
        problem: str,
        node: ThoughtNode,
        custom_generator: Optional[Callable[[str, List[str], int], Awaitable[List[str]]]],
    ) -> List[str]:
        if custom_generator is not None:
            context = [
                n.thought
                for n in node.path_from_root(self._tree)
                if not n.is_root()
            ]
            return await custom_generator(problem, context, node.depth)

        prompt = self._build_generation_prompt(problem, node)
        try:
            response = await self.llm_callback(prompt)
            return self._parse_thoughts(response, self.config.branching_factor)
        except Exception as e:
            logger.warning("Thought generation failed: %s", e)
            return []

    async def _evaluate_thought(
        self,
        problem: str,
        node: ThoughtNode,
        custom_evaluator: Optional[Callable[[str, str, int], Awaitable[float]]],
    ) -> float:
        if custom_evaluator is not None:
            return await custom_evaluator(problem, node.thought, node.depth)

        prompt = self._build_evaluation_prompt(problem, node)
        try:
            response = await self.llm_callback(prompt)
            return self._parse_score(response)
        except Exception as e:
            logger.warning("Thought evaluation failed: %s", e)
            return 0.5

    def _build_generation_prompt(self, problem: str, node: ThoughtNode) -> str:
        context = "\n".join(
            f"Step {n.depth}: {n.thought}"
            for n in node.path_from_root(self._tree)
            if not n.is_root()
        )

        return (
            f"Problem: {problem}\n\n"
            f"Current reasoning path:\n{context}\n\n"
            f"Generate exactly {self.config.branching_factor} distinct next steps "
            f"to solve this problem. Each step should be a single concise sentence.\n\n"
            f"Format each thought on a new line starting with '- ':\n"
        )

    def _build_evaluation_prompt(self, problem: str, node: ThoughtNode) -> str:
        path = node.path_from_root(self._tree)
        chain = "\n".join(
            f"Step {n.depth}: {n.thought}" for n in path if not n.is_root()
        )

        return (
            f"Problem: {problem}\n\n"
            f"Reasoning chain:\n{chain}\n\n"
            f"Rate how promising this reasoning path is for solving the problem.\n"
            f"Respond with a single number between 0.0 and 1.0:\n"
            f"  0.0-0.2: Dead end, irrelevant\n"
            f"  0.2-0.4: Weak direction\n"
            f"  0.4-0.6: Moderately promising\n"
            f"  0.6-0.8: Strong direction\n"
            f"  0.8-1.0: Very likely to lead to solution\n\n"
            f"Score: "
        )

    def _parse_thoughts(self, response: str, max_count: int) -> List[str]:
        thoughts: List[str] = []
        for line in response.strip().split("\n"):
            line = line.strip().lstrip("-*•").strip()
            if line and len(thoughts) < max_count:
                thoughts.append(line)
        return thoughts

    def _parse_score(self, response: str) -> float:
        for token in response.strip().split():
            try:
                score = float(token)
                return max(0.0, min(1.0, score))
            except ValueError:
                continue
        return 0.5

    def _build_chain(self, node: ThoughtNode) -> str:
        path = node.path_from_root(self._tree)
        return "\n".join(
            f"Step {n.depth}: {n.thought}" for n in path if not n.is_root()
        )

    def _record_branch(self, node: ThoughtNode) -> None:
        path = node.path_from_root(self._tree)
        non_root = [n for n in path if not n.is_root()]
        if not non_root:
            return

        branch = ThoughtBranch(
            nodes=non_root,
            final_score=node.score,
            is_solution=node.state == ThoughtState.SOLUTION,
        )
        self._branches.append(branch)

    def _should_terminate(self) -> bool:
        if self._nodes_explored >= self.config.max_iterations:
            return True
        elapsed = time.time() - self._start_time
        if elapsed >= self.config.timeout_seconds:
            return True
        return False

    def _build_result(self) -> ToTResult:
        elapsed = time.time() - self._start_time

        solution_branches = [b for b in self._branches if b.is_solution]
        if solution_branches:
            best = max(solution_branches, key=lambda b: b.final_score)
            return ToTResult(
                solution=best.thought_chain,
                solution_score=best.final_score,
                nodes_explored=self._nodes_explored,
                nodes_pruned=self._nodes_pruned,
                branches_explored=len(self._branches),
                search_time=elapsed,
                best_branch=best,
                all_branches=list(self._branches),
                terminated_by="solution_found",
            )

        if self._branches:
            best = max(self._branches, key=lambda b: b.final_score)
            terminated = "max_iterations" if self._nodes_explored >= self.config.max_iterations else "timeout"
            return ToTResult(
                solution=best.thought_chain,
                solution_score=best.final_score,
                nodes_explored=self._nodes_explored,
                nodes_pruned=self._nodes_pruned,
                branches_explored=len(self._branches),
                search_time=elapsed,
                best_branch=best,
                all_branches=list(self._branches),
                terminated_by=terminated,
            )

        return ToTResult(
            solution="",
            solution_score=0.0,
            nodes_explored=self._nodes_explored,
            nodes_pruned=self._nodes_pruned,
            branches_explored=0,
            search_time=elapsed,
            terminated_by="no_branches_generated",
        )

    def get_tree_stats(self) -> Dict[str, Any]:
        total_nodes = len(self._tree)
        max_depth = max((n.depth for n in self._tree.values()), default=0)
        solution_count = sum(
            1 for n in self._tree.values() if n.state == ThoughtState.SOLUTION
        )
        pruned_count = sum(
            1 for n in self._tree.values() if n.state == ThoughtState.PRUNED
        )

        return {
            "total_nodes": total_nodes,
            "max_depth": max_depth,
            "solutions": solution_count,
            "pruned": pruned_count,
            "explored": self._nodes_explored,
            "branches": len(self._branches),
        }

    def visualize_tree(self, max_depth: int = 3) -> str:
        lines: List[str] = []

        def _visit(node_id: str, indent: str, is_last: bool) -> None:
            node = self._tree.get(node_id)
            if node is None:
                return

            prefix = "└── " if is_last else "├── "
            state_icon = {
                ThoughtState.PENDING: "○",
                ThoughtState.EXPLORED: "●",
                ThoughtState.PRUNED: "✗",
                ThoughtState.SOLUTION: "★",
                ThoughtState.DEAD_END: "⊘",
            }.get(node.state, "?")

            score_str = f" [{node.score:.2f}]" if node.depth > 0 else ""
            label = f"{state_icon}{node.thought[:60]}{score_str}"
            lines.append(f"{indent}{prefix}{label}")

            if node.depth >= max_depth:
                return

            child_indent = indent + ("    " if is_last else "│   ")
            for i, child_id in enumerate(node.children):
                _visit(child_id, child_indent, i == len(node.children) - 1)

        if self._root_id:
            root = self._tree[self._root_id]
            lines.append(f"★ {root.thought[:80]}")
            for i, child_id in enumerate(root.children):
                _visit(child_id, "", i == len(root.children) - 1)

        return "\n".join(lines)
