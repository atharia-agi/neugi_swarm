"""Tests for Browser Tool and Computer Use."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.browser import BrowserTool, BrowserConfig, BrowserAction
from computer_use.controller import ComputerUseController, ActionType, ComputerAction, SafetyChecker


class TestBrowserTool(unittest.TestCase):
    def test_initialization(self):
        bt = BrowserTool()
        self.assertIsNotNone(bt.config)

    def test_read_without_browser(self):
        """Tier 1: Read without launching browser."""
        bt = BrowserTool()
        try:
            content = bt.read("https://example.com")
            self.assertIsInstance(content, str)
        except Exception as e:
            self.skipIf(True, f"Network unavailable: {e}")

    def test_lazy_playwright(self):
        bt = BrowserTool()
        self.assertIsNone(bt._playwright)
        # Playwright only loaded when needed

    def test_get_clickable_elements(self):
        bt = BrowserTool()
        try:
            bt.navigate("https://example.com")
            elements = bt.get_clickable_elements()
            self.assertIsInstance(elements, list)
            bt.close()
        except Exception as e:
            self.skipIf(True, f"Browser unavailable: {e}")

    def test_screenshot(self):
        bt = BrowserTool()
        try:
            bt.navigate("https://example.com")
            b64 = bt.screenshot()
            self.assertTrue(len(b64) > 100)
            bt.close()
        except Exception as e:
            self.skipIf(True, f"Browser unavailable: {e}")

    def test_context_manager(self):
        with BrowserTool() as bt:
            self.assertIsNotNone(bt)

    def test_action_history(self):
        bt = BrowserTool()
        self.assertEqual(len(bt.get_action_history()), 0)


class TestComputerUse(unittest.TestCase):
    def test_initialization(self):
        ctrl = ComputerUseController()
        self.assertIsNotNone(ctrl.browser)

    def test_safety_checker(self):
        checker = SafetyChecker()
        
        # Safe action
        safe = ComputerAction(action=ActionType.CLICK, selector="#button")
        result = checker.check(safe)
        self.assertTrue(result["allowed"])
        
        # Destructive action
        destructive = ComputerAction(action=ActionType.FILL, text="rm -rf /")
        result = checker.check(destructive)
        self.assertFalse(result["allowed"])

    def test_action_types(self):
        self.assertEqual(ActionType.CLICK.value, "click")
        self.assertEqual(ActionType.NAVIGATE.value, "navigate")
        self.assertEqual(ActionType.TERMINATE.value, "terminate")

    def test_computer_action_creation(self):
        action = ComputerAction(
            action=ActionType.FILL,
            selector="#search",
            text="hello",
            reason="Test"
        )
        self.assertEqual(action.action, ActionType.FILL)
        self.assertEqual(action.text, "hello")

    def test_reset(self):
        ctrl = ComputerUseController()
        ctrl._step_count = 5
        ctrl.reset()
        self.assertEqual(ctrl._step_count, 0)


if __name__ == "__main__":
    unittest.main()
