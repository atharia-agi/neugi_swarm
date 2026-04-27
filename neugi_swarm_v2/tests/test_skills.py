"""Integration tests for Skills subsystem."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSkillsImports(unittest.TestCase):
    def test_skill_contract_imports(self):
        from skills import skill_contract
        self.assertTrue(hasattr(skill_contract, "SkillContract"))

    def test_skill_loader_imports(self):
        from skills import skill_loader
        self.assertTrue(hasattr(skill_loader, "SkillLoader"))

    def test_skill_manager_imports(self):
        from skills import skill_manager
        self.assertTrue(hasattr(skill_manager, "SkillManager"))

    def test_skill_matcher_imports(self):
        from skills import skill_matcher
        self.assertTrue(hasattr(skill_matcher, "SkillMatcher"))

    def test_skill_prompt_imports(self):
        from skills import skill_prompt
        self.assertTrue(hasattr(skill_prompt, "PromptAssembler"))

    def test_package_exports(self):
        from skills import SkillManager, SkillLoader, SkillMatcher
        self.assertIsNotNone(SkillManager)
        self.assertIsNotNone(SkillLoader)
        self.assertIsNotNone(SkillMatcher)


if __name__ == "__main__":
    unittest.main()
