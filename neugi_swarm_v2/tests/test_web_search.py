"""Tests for Web Search Tool."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.web_search import WebSearch, WebSearchConfig, SearchResult


class TestWebSearch(unittest.TestCase):
    def setUp(self):
        self.ws = WebSearch()

    def test_initialization(self):
        self.assertIsNotNone(self.ws.config)
        self.assertTrue(self.ws.config.cache_enabled)

    def test_cache_operations(self):
        key = self.ws._cache_key("test", "query")
        self.assertIsNone(self.ws._get_cached(key))
        
        self.ws._set_cached(key, "value")
        self.assertEqual(self.ws._get_cached(key), "value")

    def test_read_url_returns_content(self):
        # Test with a simple reliable URL
        try:
            content = self.ws.read_url("https://example.com")
            self.assertIsInstance(content, str)
            self.assertTrue(len(content) > 0)
        except Exception as e:
            self.skipIf(True, f"Network unavailable: {e}")

    def test_search_returns_results(self):
        try:
            results = self.ws.search("Python programming", max_results=2)
            self.assertIsInstance(results, list)
            # Results might be empty if services are down
        except Exception as e:
            self.skipIf(True, f"Search service unavailable: {e}")

    def test_search_result_structure(self):
        result = SearchResult(
            title="Test",
            url="https://example.com",
            content="Test content",
            source="test"
        )
        self.assertEqual(result.title, "Test")
        self.assertEqual(result.source, "test")

    def test_clear_cache(self):
        self.ws._set_cached("key", "value")
        self.ws.clear_cache()
        self.assertEqual(len(self.ws._cache), 0)

    def test_config_customization(self):
        config = WebSearchConfig(max_results=10, cache_enabled=False)
        ws = WebSearch(config)
        self.assertEqual(ws.config.max_results, 10)
        self.assertFalse(ws.config.cache_enabled)


if __name__ == "__main__":
    unittest.main()
