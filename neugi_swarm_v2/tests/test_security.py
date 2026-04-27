"""Integration tests for Security subsystem."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSecurityImports(unittest.TestCase):
    def test_sandbox_imports(self):
        from security import sandbox
        self.assertTrue(hasattr(sandbox, "ExecutionSandbox"))

    def test_command_validator_imports(self):
        from security import command_validator
        self.assertTrue(hasattr(command_validator, "CommandValidator"))

    def test_exploit_prevention_imports(self):
        from security import exploit_prevention
        self.assertTrue(hasattr(exploit_prevention, "ExploitPreventionEngine"))

    def test_secret_manager_imports(self):
        from security import secret_manager
        self.assertTrue(hasattr(secret_manager, "SecretManager"))

    def test_shield_reasoning_imports(self):
        from security import shield_reasoning
        self.assertTrue(hasattr(shield_reasoning, "ShieldReasoner"))

    def test_package_exports(self):
        from security import ExecutionSandbox, CommandValidator, SecretManager
        self.assertIsNotNone(ExecutionSandbox)
        self.assertIsNotNone(CommandValidator)
        self.assertIsNotNone(SecretManager)


if __name__ == "__main__":
    unittest.main()
