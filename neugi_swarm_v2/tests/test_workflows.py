"""Integration tests for Workflows subsystem."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestWorkflowsImports(unittest.TestCase):
    def test_state_graph_imports(self):
        from workflows import state_graph
        self.assertTrue(hasattr(state_graph, "StateGraph"))

    def test_checkpoint_imports(self):
        from workflows import checkpoint
        self.assertIsNotNone(checkpoint)

    def test_executor_imports(self):
        from workflows import executor
        self.assertIsNotNone(executor)

    def test_human_in_loop_imports(self):
        from workflows import human_in_loop
        self.assertIsNotNone(human_in_loop)


if __name__ == "__main__":
    unittest.main()
