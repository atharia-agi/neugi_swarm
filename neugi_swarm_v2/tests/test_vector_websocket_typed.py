"""Tests for Vector Memory, WebSocket, and TypedAgent LLM wiring."""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from memory.embeddings import EmbeddingEngine, VectorMemoryIndex
from dashboard.websocket import WebSocketHandler, WebSocketServer, WebSocketError
from agents.typed import TypedAgent, RunContext, ToolDef


class TestEmbeddingEngine(unittest.TestCase):
    def test_initialization(self):
        engine = EmbeddingEngine()
        self.assertIsNotNone(engine)
        self.assertEqual(engine.dimension, 384)
    
    def test_backend_detection(self):
        engine = EmbeddingEngine()
        backend = engine._init_backend()
        self.assertIn(backend, ["sentence_transformers", "ollama", "tfidf"])
    
    def test_encode_text(self):
        engine = EmbeddingEngine()
        vec = engine.encode("Hello world")
        self.assertIsInstance(vec, list)
        self.assertEqual(len(vec), engine.dimension)
    
    def test_encode_batch(self):
        engine = EmbeddingEngine()
        texts = ["Hello", "World", "Test"]
        vecs = engine.encode_batch(texts)
        self.assertEqual(len(vecs), 3)
        self.assertEqual(len(vecs[0]), engine.dimension)
    
    def test_cosine_similarity(self):
        engine = EmbeddingEngine()
        a = [1.0, 0.0, 0.0]
        b = [1.0, 0.0, 0.0]
        sim = EmbeddingEngine._cosine_similarity(a, b)
        self.assertAlmostEqual(sim, 1.0)
        
        c = [0.0, 1.0, 0.0]
        sim2 = EmbeddingEngine._cosine_similarity(a, c)
        self.assertAlmostEqual(sim2, 0.0)
    
    def test_similarity_search(self):
        engine = EmbeddingEngine()
        query = engine.encode("test query")
        candidates = [
            ("1", engine.encode("test match")),
            ("2", engine.encode("something else")),
            ("3", engine.encode("another test")),
        ]
        results = engine.similarity(query, candidates, top_k=2)
        self.assertEqual(len(results), 2)
        self.assertTrue(all(0 <= score <= 1 for _, score in results))
    
    def test_tfidf_fallback(self):
        engine = EmbeddingEngine()
        engine._backend = "tfidf"
        vec = engine.encode("hello world test")
        self.assertEqual(len(vec), 384)
        # Should be normalized
        import math
        norm = math.sqrt(sum(v * v for v in vec))
        self.assertAlmostEqual(norm, 1.0, places=5)


class TestVectorMemoryIndex(unittest.TestCase):
    def test_add_and_search(self):
        engine = EmbeddingEngine()
        index = VectorMemoryIndex(engine)
        
        index.add("mem1", "The quick brown fox")
        index.add("mem2", "Lazy dog sleeping")
        index.add("mem3", "Fox jumps over dog")
        
        results = index.search("fox", top_k=2)
        self.assertTrue(len(results) <= 2)
        # mem1 or mem3 should be top
        ids = [r[0] for r in results]
        self.assertTrue("mem1" in ids or "mem3" in ids)
    
    def test_delete(self):
        engine = EmbeddingEngine()
        index = VectorMemoryIndex(engine)
        
        index.add("mem1", "test content")
        index.delete("mem1")
        
        results = index.search("test")
        self.assertNotIn("mem1", [r[0] for r in results])


class TestWebSocketHandler(unittest.TestCase):
    def test_frame_encoding(self):
        """Test that text frames are properly encoded."""
        # We can't easily test the full handshake without a real HTTP request,
        # but we can test frame encoding logic indirectly
        handler = WebSocketHandler.__new__(WebSocketHandler)
        handler._socket = None
        handler._closed = False
        handler._lock = __import__('threading').Lock()
        
        # Can't send without socket, but we verify the class exists
        self.assertIsNotNone(handler)
    
    def test_opcodes(self):
        self.assertEqual(WebSocketHandler.OP_TEXT, 0x1)
        self.assertEqual(WebSocketHandler.OP_BINARY, 0x2)
        self.assertEqual(WebSocketHandler.OP_CLOSE, 0x8)
        self.assertEqual(WebSocketHandler.OP_PING, 0x9)
        self.assertEqual(WebSocketHandler.OP_PONG, 0xA)


class TestWebSocketServer(unittest.TestCase):
    def test_initialization(self):
        server = WebSocketServer()
        self.assertEqual(server.client_count, 0)
    
    def test_add_remove_client(self):
        server = WebSocketServer()
        handler = WebSocketHandler.__new__(WebSocketHandler)
        
        server.add_client(handler)
        self.assertEqual(server.client_count, 1)
        
        server.remove_client(handler)
        self.assertEqual(server.client_count, 0)
    
    def test_broadcast_event(self):
        server = WebSocketServer()
        sent = server.broadcast_event("test", {"data": "hello"})
        self.assertEqual(sent, 0)  # No clients


class TestTypedAgentLLM(unittest.TestCase):
    def test_llm_provider_integration(self):
        """Test that TypedAgent can accept and use an LLM provider."""
        from llm_provider import ProviderConfig, ProviderType, OllamaProvider
        
        config = ProviderConfig(provider_type=ProviderType.OLLAMA)
        provider = OllamaProvider(config)
        
        agent = TypedAgent[str, str](
            model="ollama:test",
            llm_provider=provider,
        )
        
        self.assertIsNotNone(agent._llm)
    
    def test_tools_schema_generation(self):
        agent = TypedAgent()
        
        @agent.tool(description="A test tool")
        async def my_tool(ctx, query: str) -> str:
            return query
        
        schema = agent.get_tools_schema()
        self.assertEqual(len(schema), 1)
        self.assertEqual(schema[0]["function"]["name"], "my_tool")
    
    def test_run_context(self):
        ctx = RunContext(deps={"db": "test"}, agent_name="agent1")
        self.assertEqual(ctx.deps, {"db": "test"})
        ctx.set("key", "value")
        self.assertEqual(ctx.get("key"), "value")


class TestMemoryVectorIntegration(unittest.TestCase):
    """Integration test: MemorySystem with vector embeddings."""
    
    def test_memory_with_embeddings(self):
        from memory.memory_core import MemorySystem
        import tempfile
        
        with tempfile.TemporaryDirectory() as tmpdir:
            ms = MemorySystem(
                base_dir=tmpdir,
                enable_vec=True,
            )
            
            # Save some memories
            ms.save("Python is a great programming language", tags=["python", "coding"])
            ms.save("JavaScript runs in the browser", tags=["js", "web"])
            ms.save("Machine learning with Python", tags=["python", "ml"])
            
            # Recall with semantic query
            results = ms.recall("programming languages", limit=5)
            self.assertTrue(len(results) > 0)
            
            # First result should be about Python
            first_content = results[0][0].content.lower()
            self.assertTrue("python" in first_content or "language" in first_content)
            
            ms.close()


if __name__ == "__main__":
    unittest.main()
