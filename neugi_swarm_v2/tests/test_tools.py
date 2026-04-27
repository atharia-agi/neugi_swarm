"""Integration tests for Tools subsystem."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestToolsImports(unittest.TestCase):
    def test_tool_registry_imports(self):
        from tools import tool_registry
        self.assertTrue(hasattr(tool_registry, "ToolRegistry"))

    def test_tool_executor_imports(self):
        from tools import tool_executor
        self.assertIsNotNone(tool_executor)

    def test_tool_composer_imports(self):
        from tools import tool_composer
        self.assertIsNotNone(tool_composer)

    def test_tool_generator_imports(self):
        from tools import tool_generator
        self.assertIsNotNone(tool_generator)

    def test_builtins_imports(self):
        from tools import builtins
        self.assertIsNotNone(builtins)

    def test_tool_categories_exist(self):
        from tools.tool_registry import ToolCategory
        self.assertTrue(hasattr(ToolCategory, "WEB"))
        self.assertTrue(hasattr(ToolCategory, "CODE"))
        self.assertTrue(hasattr(ToolCategory, "FILE"))
        self.assertTrue(hasattr(ToolCategory, "SECURITY"))


if __name__ == "__main__":
    unittest.main()
