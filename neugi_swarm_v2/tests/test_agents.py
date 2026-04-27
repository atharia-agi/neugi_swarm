"""Integration tests for Agents subsystem."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestAgentsImports(unittest.TestCase):
    def test_agent_imports(self):
        from agents import agent
        self.assertTrue(hasattr(agent, "Agent"))
        self.assertTrue(hasattr(agent, "AgentRole"))

    def test_agent_manager_imports(self):
        from agents import agent_manager
        self.assertIsNotNone(agent_manager)

    def test_orchestrator_imports(self):
        from agents import orchestrator
        self.assertIsNotNone(orchestrator)

    def test_evaluator_optimizer_imports(self):
        from agents import evaluator_optimizer
        self.assertIsNotNone(evaluator_optimizer)

    def test_message_bus_imports(self):
        from agents import message_bus
        self.assertIsNotNone(message_bus)

    def test_agent_roles_exist(self):
        from agents.agent import AgentRole
        self.assertTrue(hasattr(AgentRole, "CODER"))
        self.assertTrue(hasattr(AgentRole, "RESEARCHER"))
        self.assertTrue(hasattr(AgentRole, "ANALYST"))


if __name__ == "__main__":
    unittest.main()
