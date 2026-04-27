"""Integration tests for Governance subsystem."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestGovernanceImports(unittest.TestCase):
    def test_budget_imports(self):
        from governance import budget
        self.assertTrue(hasattr(budget, "BudgetTracker"))

    def test_approval_imports(self):
        from governance import approval
        self.assertTrue(hasattr(approval, "ApprovalGate"))

    def test_audit_imports(self):
        from governance import audit
        self.assertTrue(hasattr(audit, "AuditLogger"))

    def test_policy_imports(self):
        from governance import policy
        self.assertTrue(hasattr(policy, "PolicyEngine"))

    def test_package_exports(self):
        from governance import BudgetTracker, ApprovalGate, AuditLogger, PolicyEngine
        self.assertIsNotNone(BudgetTracker)
        self.assertIsNotNone(ApprovalGate)
        self.assertIsNotNone(AuditLogger)
        self.assertIsNotNone(PolicyEngine)


if __name__ == "__main__":
    unittest.main()
