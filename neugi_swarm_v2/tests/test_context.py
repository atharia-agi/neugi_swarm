"""Integration tests for Context subsystem."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestContextImports(unittest.TestCase):
    def test_context_injector_imports(self):
        from context import context_injector
        self.assertIsNotNone(context_injector)

    def test_prompt_assembler_imports(self):
        from context import prompt_assembler
        self.assertTrue(hasattr(prompt_assembler, "PromptAssembler"))

    def test_token_budget_imports(self):
        from context import token_budget
        self.assertTrue(hasattr(token_budget, "TokenBudget"))

    def test_cache_stability_imports(self):
        from context import cache_stability
        self.assertTrue(hasattr(cache_stability, "CacheStability"))


if __name__ == "__main__":
    unittest.main()
