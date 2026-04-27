"""Integration tests for Memory subsystem."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestMemoryImports(unittest.TestCase):
    def test_memory_core_imports(self):
        from memory import memory_core
        self.assertTrue(hasattr(memory_core, "MemoryTier"))

    def test_scopes_imports(self):
        from memory import scopes
        self.assertTrue(hasattr(scopes, "ScopePath"))

    def test_scoring_imports(self):
        from memory import scoring
        self.assertTrue(hasattr(scoring, "ScoringEngine"))

    def test_dreaming_imports(self):
        from memory import dreaming
        self.assertIsNotNone(dreaming)


if __name__ == "__main__":
    unittest.main()
