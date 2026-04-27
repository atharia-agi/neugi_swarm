"""Integration tests for Session subsystem."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TestSessionImports(unittest.TestCase):
    def test_session_manager_imports(self):
        from session import session_manager
        self.assertIsNotNone(session_manager)

    def test_compaction_imports(self):
        from session import compaction
        self.assertIsNotNone(compaction)

    def test_steering_imports(self):
        from session import steering
        self.assertIsNotNone(steering)

    def test_transcript_imports(self):
        from session import transcript
        self.assertIsNotNone(transcript)


if __name__ == "__main__":
    unittest.main()
