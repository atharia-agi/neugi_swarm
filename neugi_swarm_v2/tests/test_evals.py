"""Tests for Evals System and Typed Agent."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evals.harness import EvalResult, BenchmarkResult, EvalHarness, RegressionReport
from agents.typed import RunContext, TypedAgent, ToolDef


class TestEvals(unittest.TestCase):
    def test_eval_result(self):
        r = EvalResult(
            task_id="t1",
            task_name="Test",
            success=True,
            score=0.95,
            duration_seconds=1.5
        )
        self.assertTrue(r.success)
        self.assertEqual(r.score, 0.95)

    def test_benchmark_result_stats(self):
        results = [
            EvalResult(task_id="1", task_name="A", success=True, score=1.0, duration_seconds=1.0),
            EvalResult(task_id="2", task_name="B", success=False, score=0.0, duration_seconds=2.0),
            EvalResult(task_id="3", task_name="C", success=True, score=0.8, duration_seconds=1.5)
        ]
        br = BenchmarkResult(benchmark_name="test", version="1.0", results=results)
        self.assertAlmostEqual(br.success_rate, 2/3)
        self.assertAlmostEqual(br.average_score, 0.6)
        self.assertAlmostEqual(br.average_duration, 1.5)

    def test_regression_report(self):
        baseline = BenchmarkResult(
            benchmark_name="test",
            version="1.0",
            results=[EvalResult("1", "A", True, 0.9, 1.0)]
        )
        current = BenchmarkResult(
            benchmark_name="test",
            version="2.0",
            results=[EvalResult("1", "A", True, 0.7, 1.0)]
        )
        
        harness = EvalHarness()
        harness.load_baseline("test", baseline)
        report = harness.compare_to_baseline(current)
        
        self.assertIsNotNone(report)
        self.assertTrue(report.has_regression)
        self.assertLess(report.score_delta, 0)

    def test_harness_save_and_report(self):
        harness = EvalHarness(output_dir="/tmp/neugi_evals")
        results = {
            "test": BenchmarkResult(
                benchmark_name="test",
                version="1.0",
                results=[EvalResult("1", "A", True, 1.0, 1.0)]
            )
        }
        report = harness.report(results)
        self.assertIn("NEUGI v2 Evaluation Report", report)


class TestTypedAgent(unittest.TestCase):
    def test_run_context(self):
        ctx = RunContext(deps={"db": "test"}, agent_name="agent1")
        self.assertEqual(ctx.deps, {"db": "test"})
        ctx.set("key", "value")
        self.assertEqual(ctx.get("key"), "value")

    def test_agent_initialization(self):
        agent = TypedAgent[str, str](
            model="ollama:test",
            instructions="Test agent"
        )
        self.assertEqual(agent.model, "ollama:test")
        self.assertEqual(agent.instructions, "Test agent")

    def test_tool_registration(self):
        agent = TypedAgent()
        
        @agent.tool
        async def test_tool(ctx, arg: str) -> str:
            return f"Result: {arg}"
        
        self.assertIn("test_tool", agent._tools)
        self.assertEqual(agent._tools["test_tool"].description, "")

    def test_tools_schema(self):
        agent = TypedAgent()
        
        @agent.tool(description="A test tool")
        async def my_tool(ctx, query: str) -> str:
            return query
        
        schema = agent.get_tools_schema()
        self.assertEqual(len(schema), 1)
        self.assertEqual(schema[0]["function"]["name"], "my_tool")

    def test_tool_with_approval(self):
        agent = TypedAgent()
        
        @agent.tool(requires_approval=True, approval_roles=["admin"])
        async def dangerous_tool(ctx) -> str:
            return "done"
        
        self.assertTrue(agent._tools["dangerous_tool"].requires_approval)


if __name__ == "__main__":
    unittest.main()
