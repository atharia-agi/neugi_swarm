"""Integration tests for Governance subsystem."""
import os
import sys
import unittest
import tempfile
import uuid

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestGovernanceImports(unittest.TestCase):
    def test_budget_imports(self):
        from governance import budget
        self.assertTrue(hasattr(budget, "BudgetTracker"))

    def test_approval_imports(self):
        from governance import approval
        self.assertTrue(hasattr(approval, "ApprovalGate"))

    def test_package_exports(self):
        from governance import ApprovalGate, BudgetTracker
        self.assertIsNotNone(BudgetTracker)
        self.assertIsNotNone(ApprovalGate)

    def test_approval_get_stats_empty_db(self):
        from governance.approval import ApprovalGate
        db_path = os.path.join(tempfile.gettempdir(), f"neugi_approval_{uuid.uuid4().hex}.db")
        gate = ApprovalGate(db_path=db_path)
        stats = gate.get_stats()
        self.assertEqual(stats["total_requests"], 0)
        self.assertEqual(stats["approved"], 0)
        self.assertEqual(stats["rejected"], 0)
        self.assertEqual(stats["pending"], 0)
        self.assertEqual(stats["approval_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
