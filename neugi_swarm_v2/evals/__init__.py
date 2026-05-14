"""
NEUGI v2 Evals System
=====================
Systematic evaluation and benchmarking.

Modules:
    harness: EvalHarness and built-in benchmarks
"""

from .harness import (
    Benchmark,
    BenchmarkResult,
    BrowserBenchmark,
    EvalHarness,
    EvalResult,
    RegressionReport,
    SkillBenchmark,
    WebSearchBenchmark,
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
