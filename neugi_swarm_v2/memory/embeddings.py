"""
NEUGI v2 Embedding Engine
===========================
Lightweight semantic embedding for vector memory.

Strategy:
    1. sentence-transformers all-MiniLM-L6-v2 (primary) — 80MB, pure Python
    2. Ollama nomic-embed-text (fallback) — 137MB, requires Ollama
    3. TF-IDF sparse vectors (last resort) — stdlib only

Usage:
    from memory.embeddings import EmbeddingEngine
    
    engine = EmbeddingEngine()
    vec = engine.encode("Hello world")  # 384-dim float list
    
    # Similarity search
    results = engine.similarity(query_vec, memory_vectors, top_k=5)
"""

from __future__ import annotations

import logging
import math
import os
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """
    Unified embedding engine with multiple backends.
    
    Auto-selects best available backend:
        1. sentence-transformers (all-MiniLM-L6-v2)
        2. Ollama (nomic-embed-text)
        3. TF-IDF (sparse fallback)
    """

    def __init__(
        self,
        model_name: str = "",
        ollama_url: str = "",
        ollama_model: str = "nomic-embed-text",
        dimension: int = 384,
    ):
        self.model_name = model_name or "all-MiniLM-L6-v2"
        self.ollama_url = ollama_url or os.environ.get("OLLAMA_URL", "http://localhost:11434")
        self.ollama_model = ollama_model
        self.dimension = dimension

        self._backend: Optional[str] = None
        self._st_model: Any = None
        self._tfidf: Optional[Any] = None

    def _init_backend(self) -> str:
        """Lazy-initialize the best available backend."""
        if self._backend is not None:
            return self._backend

        # Try sentence-transformers first
        try:
            from sentence_transformers import SentenceTransformer
            logger.info("Loading sentence-transformers model: %s", self.model_name)
            self._st_model = SentenceTransformer(self.model_name)
            self.dimension = self._st_model.get_sentence_embedding_dimension()
            self._backend = "sentence_transformers"
            logger.info("Embedding backend: sentence-transformers (%s, dim=%d)", self.model_name, self.dimension)
            return self._backend
        except ImportError:
            logger.info("sentence-transformers not installed, trying Ollama...")
        except Exception as e:
            logger.warning("sentence-transformers failed: %s", e)

        # Try Ollama
        try:
            import requests
            resp = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if resp.status_code == 200:
                models = resp.json().get("models", [])
                available = [m.get("name", "") for m in models]
                if self.ollama_model in available or any(self.ollama_model in a for a in available):
                    self._backend = "ollama"
                    logger.info("Embedding backend: Ollama (%s)", self.ollama_model)
                    return self._backend
                else:
                    logger.info("Ollama model %s not available (have: %s)", self.ollama_model, available[:5])
            else:
                logger.info("Ollama not reachable at %s", self.ollama_url)
        except Exception as e:
            logger.info("Ollama fallback failed: %s", e)

        # Final fallback: TF-IDF
        self._backend = "tfidf"
        logger.info("Embedding backend: TF-IDF (sparse fallback)")
        return self._backend

    def encode(self, text: str) -> List[float]:
        """
        Encode text into embedding vector.
        
        Args:
            text: Input text
            
        Returns:
            List of floats (dimension depends on backend)
        """
        backend = self._init_backend()

        if backend == "sentence_transformers":
            return self._st_model.encode(text, convert_to_numpy=True).tolist()

        elif backend == "ollama":
            return self._encode_ollama(text)

        else:
            return self._encode_tfidf(text)

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Encode multiple texts efficiently."""
        backend = self._init_backend()

        if backend == "sentence_transformers":
            embeddings = self._st_model.encode(texts, convert_to_numpy=True, batch_size=32)
            return [e.tolist() for e in embeddings]

        elif backend == "ollama":
            return [self._encode_ollama(t) for t in texts]

        else:
            return [self._encode_tfidf(t) for t in texts]

    def _encode_ollama(self, text: str) -> List[float]:
        """Encode via Ollama API."""
        import requests
        try:
            resp = requests.post(
                f"{self.ollama_url}/api/embeddings",
                json={"model": self.ollama_model, "prompt": text},
                timeout=30,
            )
            resp.raise_for_status()
            return resp.json().get("embedding", [])
        except Exception as e:
            logger.error("Ollama embedding failed: %s", e)
            return [0.0] * self.dimension

    def _encode_tfidf(self, text: str) -> List[float]:
        """Simple TF-IDF sparse encoding fallback."""
        # Tokenize
        tokens = text.lower().split()
        # Build vocabulary on first call
        if self._tfidf is None:
            self._tfidf = {"vocab": {}, "docs": 0}
        
        # Simple hash-based encoding (deterministic)
        vec = [0.0] * self.dimension
        for token in tokens:
            idx = hash(token) % self.dimension
            vec[idx] += 1.0
        
        # Normalize
        norm = math.sqrt(sum(v * v for v in vec))
        if norm > 0:
            vec = [v / norm for v in vec]
        
        return vec

    def similarity(
        self,
        query_vec: List[float],
        candidates: List[Tuple[str, List[float]]],
        top_k: int = 10,
    ) -> List[Tuple[str, float]]:
        """
        Compute cosine similarity and return top-k.
        
        Args:
            query_vec: Query embedding
            candidates: List of (id, vector) tuples
            top_k: Number of top results
            
        Returns:
            List of (id, score) sorted by score desc
        """
        scores = []
        for cid, vec in candidates:
            score = self._cosine_similarity(query_vec, vec)
            scores.append((cid, score))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:top_k]

    @staticmethod
    def _cosine_similarity(a: List[float], b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    @property
    def backend_name(self) -> str:
        """Get current backend name."""
        return self._init_backend()

    @property
    def is_available(self) -> bool:
        """Check if any backend is available."""
        try:
            return self._init_backend() is not None
        except Exception:
            return False


class VectorMemoryIndex:
    """
    In-memory vector index with optional sqlite-vec persistence.
    """

    def __init__(
        self,
        embedding: EmbeddingEngine,
        db_conn: Optional[Any] = None,
        table_name: str = "memory_embeddings",
    ):
        self.embedding = embedding
        self._db = db_conn
        self._table = table_name
        self._vectors: Dict[str, List[float]] = {}
        self._use_sqlite_vec = False

        if db_conn is not None:
            self._init_sqlite_vec()

    def _init_sqlite_vec(self) -> None:
        """Try to initialize sqlite-vec table."""
        try:
            import sqlite_vec
            # sqlite-vec auto-registers itself when imported
            self._use_sqlite_vec = True
            logger.info("sqlite-vec loaded successfully")
        except ImportError:
            logger.info("sqlite-vec not available, using in-memory index")

    def add(self, memory_id: str, content: str) -> None:
        """Add a memory to the vector index."""
        vec = self.embedding.encode(content)
        self._vectors[memory_id] = vec

        if self._use_sqlite_vec and self._db:
            try:
                # sqlite-vec insert
                self._db.execute(
                    f"INSERT OR REPLACE INTO {self._table}(memory_id, embedding) VALUES (?, ?)",
                    (memory_id, self._serialize(vec)),
                )
                self._db.commit()
            except Exception as e:
                logger.warning("sqlite-vec insert failed: %s", e)

    def search(self, query: str, top_k: int = 10) -> List[Tuple[str, float]]:
        """Search for similar memories."""
        query_vec = self.embedding.encode(query)

        if self._use_sqlite_vec and self._db:
            try:
                return self._search_sqlite_vec(query_vec, top_k)
            except Exception as e:
                logger.warning("sqlite-vec search failed, using in-memory: %s", e)

        # In-memory search
        candidates = list(self._vectors.items())
        return self.embedding.similarity(query_vec, candidates, top_k)

    def _search_sqlite_vec(self, query_vec: List[float], top_k: int) -> List[Tuple[str, float]]:
        """Search using sqlite-vec KNN."""
        try:
            rows = self._db.execute(
                f"""
                SELECT memory_id, distance
                FROM {self._table}
                WHERE embedding MATCH ?
                ORDER BY distance
                LIMIT ?
                """,
                (self._serialize(query_vec), top_k),
            ).fetchall()
            return [(row[0], 1.0 - row[1]) for row in rows]
        except Exception as e:
            logger.warning("sqlite-vec KNN failed: %s", e)
            raise

    def delete(self, memory_id: str) -> None:
        """Remove a memory from the index."""
        self._vectors.pop(memory_id, None)
        if self._use_sqlite_vec and self._db:
            try:
                self._db.execute(f"DELETE FROM {self._table} WHERE memory_id = ?", (memory_id,))
                self._db.commit()
            except Exception as e:
                logger.warning("sqlite-vec delete failed: %s", e)

    def _serialize(self, vec: List[float]) -> bytes:
        """Serialize vector to sqlite-vec format."""
        import struct
        return struct.pack(f"{len(vec)}f", *vec)


__all__ = [
    "EmbeddingEngine",
    "VectorMemoryIndex",
]
