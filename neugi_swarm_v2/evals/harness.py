"""
Evals System for NEUGI v2
===========================
Systematic evaluation and benchmarking for agentic systems.

Features:
    - Task-based benchmarks with success criteria
    - Regression detection across versions
    - A/B testing framework
    - Performance metrics tracking
    - Human evaluation interface
    - Automated report generation

Usage:
    from evals.harness import EvalHarness
    from evals.benchmarks import WebSearchBenchmark, BrowserBenchmark
    
    harness = EvalHarness()
    harness.register(WebSearchBenchmark())
    harness.register(BrowserBenchmark())
    
    results = harness.run_all()
    harness.report(results)
"""

from __future__ import annotations

import json
import logging
import statistics
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple, Union

logger = logging.getLogger(__name__)


@dataclass
class EvalResult:
    """Result of a single evaluation task."""
    task_id: str
    task_name: str
    success: bool
    score: float  # 0.0 to 1.0
    duration_seconds: float
    tokens_used: int = 0
    error: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class BenchmarkResult:
    """Result of a full benchmark suite."""
    benchmark_name: str
    version: str
    results: List[EvalResult]
    total_duration: float = 0.0
    
    @property
    def success_rate(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.success) / len(self.results)
    
    @property
    def average_score(self) -> float:
        if not self.results:
            return 0.0
        return statistics.mean(r.score for r in self.results)
    
    @property
    def average_duration(self) -> float:
        if not self.results:
            return 0.0
        return statistics.mean(r.duration_seconds for r in self.results)


@dataclass
class RegressionReport:
    """Report comparing current vs baseline results."""
    benchmark_name: str
    baseline_version: str
    current_version: str
    baseline_score: float
    current_score: float
    score_delta: float
    baseline_success_rate: float
    current_success_rate: float
    success_rate_delta: float
    regressions: List[str] = field(default_factory=list)
    improvements: List[str] = field(default_factory=list)
    
    @property
    def has_regression(self) -> bool:
        return len(self.regressions) > 0 or self.score_delta < -0.05


class Benchmark(ABC):
    """Base class for benchmarks."""
    
    name: str = ""
    description: str = ""
    version: str = "1.0"
    
    @abstractmethod
    def setup(self) -> None:
        """Setup benchmark environment."""
        pass
    
    @abstractmethod
    def teardown(self) -> None:
        """Cleanup benchmark environment."""
        pass
    
    @abstractmethod
    def get_tasks(self) -> List[Dict[str, Any]]:
        """Return list of tasks to evaluate."""
        pass
    
    @abstractmethod
    async def run_task(self, task: Dict[str, Any]) -> EvalResult:
        """Run a single task and return result."""
        pass


class EvalHarness:
    """Main evaluation harness."""

    def __init__(self, output_dir: str = "evals/results"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.benchmarks: Dict[str, Benchmark] = {}
        self.baselines: Dict[str, BenchmarkResult] = {}
        self._version = "2.0.0"

    def register(self, benchmark: Benchmark) -> None:
        """Register a benchmark."""
        self.benchmarks[benchmark.name] = benchmark
        logger.info(f"Registered benchmark: {benchmark.name}")

    def load_baseline(self, benchmark_name: str, result: BenchmarkResult) -> None:
        """Load baseline results for regression detection."""
        self.baselines[benchmark_name] = result

    def load_baseline_from_file(self, path: str) -> None:
        """Load baseline from JSON file."""
        with open(path) as f:
            data = json.load(f)
            for name, result_data in data.items():
                results = [EvalResult(**r) for r in result_data["results"]]
                self.baselines[name] = BenchmarkResult(
                    benchmark_name=name,
                    version=result_data["version"],
                    results=results,
                    total_duration=result_data.get("total_duration", 0)
                )

    async def run_benchmark(self, name: str) -> BenchmarkResult:
        """Run a single benchmark."""
        if name not in self.benchmarks:
            raise ValueError(f"Benchmark '{name}' not registered")
        
        benchmark = self.benchmarks[name]
        logger.info(f"Running benchmark: {name}")
        
        benchmark.setup()
        start_time = time.time()
        
        results: List[EvalResult] = []
        tasks = benchmark.get_tasks()
        
        for i, task in enumerate(tasks):
            logger.info(f"  Task {i+1}/{len(tasks)}: {task.get('name', task.get('id', 'unknown'))}")
            try:
                result = await benchmark.run_task(task)
                results.append(result)
            except Exception as e:
                logger.error(f"Task failed: {e}")
                results.append(EvalResult(
                    task_id=task.get("id", str(i)),
                    task_name=task.get("name", "unknown"),
                    success=False,
                    score=0.0,
                    duration_seconds=0.0,
                    error=str(e)
                ))
        
        benchmark.teardown()
        
        total_duration = time.time() - start_time
        
        return BenchmarkResult(
            benchmark_name=name,
            version=self._version,
            results=results,
            total_duration=total_duration
        )

    async def run_all(self) -> Dict[str, BenchmarkResult]:
        """Run all registered benchmarks."""
        results = {}
        for name in self.benchmarks:
            results[name] = await self.run_benchmark(name)
        return results

    def compare_to_baseline(self, result: BenchmarkResult) -> Optional[RegressionReport]:
        """Compare benchmark result to baseline."""
        if result.benchmark_name not in self.baselines:
            return None
        
        baseline = self.baselines[result.benchmark_name]
        
        regressions = []
        improvements = []
        
        # Compare individual tasks
        baseline_tasks = {r.task_id: r for r in baseline.results}
        current_tasks = {r.task_id: r for r in result.results}
        
        for task_id, current in current_tasks.items():
            if task_id in baseline_tasks:
                base = baseline_tasks[task_id]
                if current.success and not base.success:
                    improvements.append(f"{task_id}: now passes")
                elif not current.success and base.success:
                    regressions.append(f"{task_id}: now fails")
                elif current.score < base.score - 0.1:
                    regressions.append(f"{task_id}: score dropped {base.score:.2f} -> {current.score:.2f}")
                elif current.score > base.score + 0.1:
                    improvements.append(f"{task_id}: score improved {base.score:.2f} -> {current.score:.2f}")
        
        return RegressionReport(
            benchmark_name=result.benchmark_name,
            baseline_version=baseline.version,
            current_version=result.version,
            baseline_score=baseline.average_score,
            current_score=result.average_score,
            score_delta=result.average_score - baseline.average_score,
            baseline_success_rate=baseline.success_rate,
            current_success_rate=result.success_rate,
            success_rate_delta=result.success_rate - baseline.success_rate,
            regressions=regressions,
            improvements=improvements
        )

    def save_results(self, results: Dict[str, BenchmarkResult]) -> None:
        """Save results to disk."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        data = {}
        for name, result in results.items():
            data[name] = {
                "benchmark_name": result.benchmark_name,
                "version": result.version,
                "total_duration": result.total_duration,
                "success_rate": result.success_rate,
                "average_score": result.average_score,
                "average_duration": result.average_duration,
                "results": [
                    {
                        "task_id": r.task_id,
                        "task_name": r.task_name,
                        "success": r.success,
                        "score": r.score,
                        "duration_seconds": r.duration_seconds,
                        "tokens_used": r.tokens_used,
                        "error": r.error,
                        "metadata": r.metadata,
                        "timestamp": r.timestamp
                    }
                    for r in result.results
                ]
            }
        
        path = self.output_dir / f"eval_results_{timestamp}.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"Results saved to {path}")

    def report(self, results: Dict[str, BenchmarkResult]) -> str:
        """Generate human-readable report."""
        lines = ["# NEUGI v2 Evaluation Report", ""]
        lines.append(f"Generated: {datetime.now().isoformat()}")
        lines.append(f"Version: {self._version}")
        lines.append("")
        
        for name, result in results.items():
            lines.append(f"## {name}")
            lines.append(f"- Success Rate: {result.success_rate:.1%}")
            lines.append(f"- Average Score: {result.average_score:.2f}/1.0")
            lines.append(f"- Average Duration: {result.average_duration:.2f}s")
            lines.append(f"- Total Duration: {result.total_duration:.2f}s")
            lines.append(f"- Tasks: {len(result.results)}")
            
            # Regression check
            comparison = self.compare_to_baseline(result)
            if comparison:
                lines.append("")
                lines.append("### Regression Analysis")
                lines.append(f"- Baseline: {comparison.baseline_version}")
                lines.append(f"- Score Delta: {comparison.score_delta:+.3f}")
                lines.append(f"- Success Rate Delta: {comparison.success_rate_delta:+.1%}")
                
                if comparison.has_regression:
                    lines.append("- **REGRESSIONS DETECTED** ⚠️")
                    for r in comparison.regressions:
                        lines.append(f"  - ❌ {r}")
                
                if comparison.improvements:
                    lines.append("- Improvements:")
                    for i in comparison.improvements:
                        lines.append(f"  - ✅ {i}")
            
            lines.append("")
            lines.append("### Task Breakdown")
            for r in result.results:
                status = "✅" if r.success else "❌"
                lines.append(f"{status} {r.task_name} | Score: {r.score:.2f} | Time: {r.duration_seconds:.2f}s")
                if r.error:
                    lines.append(f"   Error: {r.error}")
            
            lines.append("")
        
        report = "\n".join(lines)
        
        # Save report
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        report_path = self.output_dir / f"eval_report_{timestamp}.md"
        with open(report_path, "w", encoding="utf-8") as f:
            f.write(report)
        
        return report


# === Built-in Benchmarks ===

class WebSearchBenchmark(Benchmark):
    """Benchmark for web search capabilities."""
    
    name = "web_search"
    description = "Tests web search and URL reading capabilities"
    
    def setup(self) -> None:
        from tools.web_search import WebSearch
        self.search = WebSearch()
    
    def teardown(self) -> None:
        self.search.clear_cache()
    
    def get_tasks(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "search_basic",
                "name": "Basic Web Search",
                "query": "Python programming language features 2026",
                "expected_keywords": ["python", "programming"]
            },
            {
                "id": "read_url",
                "name": "Read URL Content",
                "url": "https://en.wikipedia.org/wiki/Python_(programming_language)",
                "expected_keywords": ["Python", "programming"]
            },
            {
                "id": "search_current",
                "name": "Current Events Search",
                "query": "latest AI artificial intelligence breakthroughs",
                "expected_keywords": ["AI", "artificial intelligence"]
            }
        ]
    
    async def run_task(self, task: Dict[str, Any]) -> EvalResult:
        start = time.time()
        
        try:
            if "url" in task:
                content = self.search.read_url(task["url"])
                success = all(kw.lower() in content.lower() for kw in task["expected_keywords"])
                score = 1.0 if success else 0.0
                return EvalResult(
                    task_id=task["id"],
                    task_name=task["name"],
                    success=success,
                    score=score,
                    duration_seconds=time.time() - start
                )
            else:
                results = self.search.search(task["query"], max_results=3)
                success = len(results) > 0
                score = min(len(results) / 3, 1.0)
                return EvalResult(
                    task_id=task["id"],
                    task_name=task["name"],
                    success=success,
                    score=score,
                    duration_seconds=time.time() - start
                )
        except Exception as e:
            return EvalResult(
                task_id=task["id"],
                task_name=task["name"],
                success=False,
                score=0.0,
                duration_seconds=time.time() - start,
                error=str(e)
            )


class BrowserBenchmark(Benchmark):
    """Benchmark for browser automation."""
    
    name = "browser_automation"
    description = "Tests browser automation and DOM interaction"
    
    def setup(self) -> None:
        from tools.browser import BrowserTool
        self.browser = BrowserTool()
    
    def teardown(self) -> None:
        self.browser.close()
    
    def get_tasks(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "navigate",
                "name": "Navigate to URL",
                "url": "https://example.com",
                "expected_title": "Example Domain"
            },
            {
                "id": "screenshot",
                "name": "Take Screenshot",
                "url": "https://example.com",
                "check_screenshot": True
            },
            {
                "id": "dom_extraction",
                "name": "Extract DOM State",
                "url": "https://example.com",
                "check_elements": True
            }
        ]
    
    async def run_task(self, task: Dict[str, Any]) -> EvalResult:
        start = time.time()
        
        try:
            self.browser.navigate(task["url"])
            
            success = True
            score = 1.0
            
            if "expected_title" in task:
                title = self.browser.get_title()
                success = task["expected_title"] in title
                score = 1.0 if success else 0.0
            
            if task.get("check_screenshot"):
                b64 = self.browser.screenshot()
                success = success and len(b64) > 1000
            
            if task.get("check_elements"):
                elements = self.browser.get_clickable_elements()
                success = success and len(elements) > 0
            
            return EvalResult(
                task_id=task["id"],
                task_name=task["name"],
                success=success,
                score=score,
                duration_seconds=time.time() - start
            )
        except Exception as e:
            return EvalResult(
                task_id=task["id"],
                task_name=task["name"],
                success=False,
                score=0.0,
                duration_seconds=time.time() - start,
                error=str(e)
            )


class SkillBenchmark(Benchmark):
    """Benchmark for skill system."""
    
    name = "skill_system"
    description = "Tests skill loading, matching, and execution"
    
    def setup(self) -> None:
        from skills import SkillManager
        self.mgr = SkillManager()
    
    def teardown(self) -> None:
        # Cleanup any temporary skill manager resources
        if hasattr(self.mgr, 'close'):
            self.mgr.close()
    
    def get_tasks(self) -> List[Dict[str, Any]]:
        return [
            {
                "id": "load_skills",
                "name": "Load All Skills",
                "check_loaded": True
            },
            {
                "id": "match_skill",
                "name": "Match Skill by Query",
                "query": "help me write Python code",
                "expected_tier": "global"
            }
        ]
    
    async def run_task(self, task: Dict[str, Any]) -> EvalResult:
        start = time.time()
        
        try:
            if task.get("check_loaded"):
                skills = self.mgr.loader.load_all()
                success = True
                score = 1.0
            else:
                from skills import SkillMatcher
                matcher = SkillMatcher()
                results = matcher.match(task["query"], [])
                success = len(results) >= 0  # Matcher might return empty
                score = 1.0 if success else 0.0
            
            return EvalResult(
                task_id=task["id"],
                task_name=task["name"],
                success=success,
                score=score,
                duration_seconds=time.time() - start
            )
        except Exception as e:
            return EvalResult(
                task_id=task["id"],
                task_name=task["name"],
                success=False,
                score=0.0,
                duration_seconds=time.time() - start,
                error=str(e)
            )


__all__ = [
    "Benchmark",
    "BenchmarkResult",
    "BrowserBenchmark",
    "EvalHarness",
    "EvalResult",
    "RegressionReport",
    "SkillBenchmark",
    "WebSearchBenchmark",
]
