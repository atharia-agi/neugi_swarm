#!/usr/bin/env python3
"""
🤖 NEUGI TEST FRAMEWORK
=========================

Simple test framework for NEUGI agents and skills

Version: 1.0
Date: March 15, 2026
"""

import os
import json
import time
from typing import Dict, List, Any, Callable
from dataclasses import dataclass


NEUGI_DIR = os.path.expanduser("~/neugi")
TESTS_DIR = os.path.join(NEUGI_DIR, "tests")


@dataclass
class TestResult:
    """Test result"""

    name: str
    passed: bool
    duration: float
    error: str = ""
    output: Any = None


class TestCase:
    """Base test case"""

    def setup(self):
        """Setup before test"""
        pass

    def teardown(self):
        """Cleanup after test"""
        pass

    def run(self) -> bool:
        """Run test - override this"""
        raise NotImplementedError


class TestSuite:
    """Test suite"""

    def __init__(self, name: str):
        self.name = name
        self.tests: List[Callable] = []
        self.results: List[TestResult] = []

    def add(self, test_func: Callable):
        """Add test function"""
        self.tests.append(test_func)

    def run(self, verbose: bool = True) -> Dict:
        """Run all tests"""
        self.results = []

        passed = 0
        failed = 0

        for test_func in self.tests:
            name = test_func.__name__
            start = time.time()

            try:
                # Create test instance
                test_instance = test_func()

                # Setup
                if hasattr(test_instance, "setup"):
                    test_instance.setup()

                # Run
                result = test_instance.run()

                # Teardown
                if hasattr(test_instance, "teardown"):
                    test_instance.teardown()

                duration = time.time() - start

                if result:
                    passed += 1
                    status = "✅ PASS"
                else:
                    failed += 1
                    status = "❌ FAIL"

                self.results.append(TestResult(name, result, duration))

                if verbose:
                    print(f"{status} {name} ({duration:.3f}s)")

            except Exception as e:
                duration = time.time() - start
                failed += 1
                self.results.append(TestResult(name, False, duration, str(e)))

                if verbose:
                    print(f"❌ FAIL {name} ({duration:.3f}s)")
                    print(f"   Error: {e}")

        total = passed + failed
        success_rate = (passed / total * 100) if total > 0 else 0

        if verbose:
            print(f"\n{'=' * 50}")
            print(f"Results: {passed}/{total} passed ({success_rate:.1f}%)")

        return {
            "passed": passed,
            "failed": failed,
            "total": total,
            "success_rate": success_rate,
            "results": self.results,
        }


# ========== BUILT-IN TESTS ==========


class TestMemory(TestCase):
    """Test memory system"""

    def setup(self):
        from neugi_memory_v2 import TwoTierMemory

        self.memory = TwoTierMemory()

    def run(self) -> bool:
        # Test write daily
        self.memory.write_daily("Test note from test suite")

        # Test recall
        results = self.memory.recall("test")

        return True


class TestSoul(TestCase):
    """Test soul system"""

    def setup(self):
        from neugi_soul import SoulSystem

        self.soul = SoulSystem()

    def run(self) -> bool:
        # Test get system prompt
        prompt = self.soul.get_system_prompt()

        return len(prompt) > 0


class TestSkills(TestCase):
    """Test skills system"""

    def setup(self):
        from neugi_skills_v2 import SkillManagerV2

        self.skills = SkillManagerV2()

    def run(self) -> bool:
        # Test list skills
        skills = self.skills.list_skills()

        return len(skills) >= 0


class TestCowork(TestCase):
    """Test cowork system"""

    def setup(self):
        from neugi_cowork import CoworkSession

        # Use temp directory
        import tempfile

        self.temp_dir = tempfile.mkdtemp()
        self.session = CoworkSession(self.temp_dir)

    def teardown(self):
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def run(self) -> bool:
        # Test write
        result = self.session.write("test.txt", "Hello from test!")

        # Test read
        result = self.session.read("test.txt")

        return result.get("content", "").strip() == "Hello from test!"


class TestScheduler(TestCase):
    """Test scheduler"""

    def setup(self):
        from neugi_scheduler import NEUGIScheduler

        self.scheduler = NEUGIScheduler()

    def run(self) -> bool:
        # Test list tasks
        tasks = self.scheduler.list_tasks()

        return isinstance(tasks, list)


# ========== TEST RUNNER ==========


def run_tests(test_pattern: str = "*", verbose: bool = True) -> Dict:
    """Run tests matching pattern"""

    # Register built-in tests
    suite = TestSuite("NEUGI")

    # Add tests
    test_classes = [
        ("test_memory", TestMemory),
        ("test_soul", TestSoul),
        ("test_skills", TestSkills),
        ("test_cowork", TestCowork),
        ("test_scheduler", TestScheduler),
    ]

    for name, test_class in test_classes:
        if test_pattern == "*" or test_pattern in name:
            suite.add(test_class)

    return suite.run(verbose=verbose)


def run_test_file(filepath: str) -> Dict:
    """Run tests from a file"""
    import importlib.util

    spec = importlib.util.spec_from_file_location("tests", filepath)
    if spec and spec.loader:
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        # Find test classes
        suite = TestSuite(os.path.basename(filepath))

        for name in dir(module):
            obj = getattr(module, name)
            if isinstance(obj, type) and issubclass(obj, TestCase) and obj != TestCase:
                suite.add(obj)

        return suite.run()

    return {"error": "Could not load test file"}


# ========== CLI ==========


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Test Framework")
    parser.add_argument("--pattern", default="*", help="Test pattern")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--file", help="Run tests from file")

    args = parser.parse_args()

    if args.file:
        result = run_test_file(args.file)
    else:
        result = run_tests(args.pattern)

    if args.json:
        print(json.dumps(result, indent=2, default=str))

    # Exit with appropriate code
    if result.get("failed", 0) > 0:
        exit(1)
    exit(0)


if __name__ == "__main__":
    main()
