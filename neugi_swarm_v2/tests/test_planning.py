"""Integration tests for Planning subsystem."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestPlanningImports(unittest.TestCase):
    def test_tree_of_thoughts_imports(self):
        from planning import tree_of_thoughts
        self.assertIsNotNone(tree_of_thoughts)

    def test_chain_of_verification_imports(self):
        from planning import chain_of_verification
        self.assertIsNotNone(chain_of_verification)

    def test_goal_system_imports(self):
        from planning import goal_system
        self.assertIsNotNone(goal_system)

    def test_strategic_planner_imports(self):
        from planning import strategic_planner
        self.assertIsNotNone(strategic_planner)

    def test_self_reflection_imports(self):
        from planning import self_reflection
        self.assertIsNotNone(self_reflection)


if __name__ == "__main__":
    unittest.main()
