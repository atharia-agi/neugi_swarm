"""Knowledge base search for Cybersecurity Expert Plugin."""
import json
from pathlib import Path
from typing import Any, Dict, Optional, List, Tuple
import math

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    HAS_NUMPY = False

logger = __import__("logging").getLogger(__name__)

def _cosine_similarity(vec1: bytes, vec2: bytes) -> float:
    """Calculate cosine similarity between two binary vectors."""
    try:
        # Convert bytes back to numpy arrays
        a = np.frombuffer(vec1, dtype=np.float32)
        b = np.frombuffer(vec2, dtype=np.float32)
        # Calculate cosine similarity
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)
    except Exception:
        return 0.0

def search_knowledge(index_path: str, query: str, category: Optional[str] = None, limit: int = 10, use_vectors: bool = True) -> Dict[str, Any]:
    idx = Path(index_path)
    
    # Initialize sentence transformer if requested and available
    embedder = None
    if use_vectors:
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
            embedder = SentenceTransformer('all-MiniLM-L6-v2')
        except ImportError:
            logger.debug("Sentence transformers not available for vector search")
            embedder = None
        except Exception as e:
            logger.debug("Failed to initialize sentence transformer: %s", e)
            embedder = None
    
    # Try Whoosh first (with vector re-ranking if available)
    try:
        from whoosh import index as wi
        from whoosh.qparser import MultifieldParser, OrGroup
        if wi.exists_in(str(idx)):
            ix = wi.open_dir(str(idx))
            parser = MultifieldParser(["title","content","headings","tags","framework"], schema=ix.schema, group=OrGroup)
            with ix.searcher() as s:
                hits = s.search(parser.parse(query), limit=limit*5)  # Get more hits for re-ranking
                results = []
                
                # Generate query embedding if vector search is enabled
                query_embedding = None
                if embedder and query.strip():
                    try:
                        query_embedding = embedder.encode([query.strip()])[0].astype(np.float32)
                    except Exception as e:
                        logger.debug("Failed to generate query embedding: %s", e)
                
                for hit in hits:
                    d = hit.fields()
                    if category and category not in d.get("tags","") and category not in d.get("framework",""): continue
                    
                    # Calculate base relevance from Whoosh score
                    base_relevance = round(hit.score, 3)
                    
                    # Enhance with vector similarity if available
                    final_relevance = base_relevance
                    if embedder and query_embedding is not None and d.get("vector"):
                        try:
                            vector_bytes = d.get("vector")
                            if vector_bytes:
                                # Convert stored bytes back to array
                                stored_embedding = np.frombuffer(vector_bytes, dtype=np.float32)
                                # Calculate cosine similarity
                                similarity = np.dot(query_embedding, stored_embedding) / (
                                    np.linalg.norm(query_embedding) * np.linalg.norm(stored_embedding)
                                )
                                # Combine scores (70% vector similarity, 30% whoosh score)
                                final_relevance = round(0.7 * float(similarity) + 0.3 * base_relevance, 3)
                        except Exception as e:
                            logger.debug("Vector similarity calculation failed: %s", e)
                            final_relevance = base_relevance
                    
                    try: 
                        meta = json.loads(d.get("metadata","{}"))
                    except: 
                        meta = {}
                    
                    results.append({
                        "id": d["path"],
                        "title": d["title"],
                        "snippet": hit.highlights("content", top=3),
                        "relevance": final_relevance,
                        "tags": d.get("tags", "").split(","),
                        "metadata": meta
                    })
                    
                    if len(results) >= limit:
                        break
                
                # Sort by relevance (descending)
                results.sort(key=lambda x: x["relevance"], reverse=True)
                return {"query": query, "results": results[:limit], "count": len(results[:limit])}
    except Exception as e:
        logger.debug("Whoosh search failed: %s", e)
    
    # Fallback to SQLite search
    import sqlite3
    db = idx / "kb_index.db"
    if db.exists():
        try:
            # Generate query embedding for SQLite vector search
            query_embedding = None
            if embedder and query.strip():
                try:
                    query_embedding = embedder.encode([query.strip()])[0].astype(np.float32)
                except Exception as e:
                    logger.debug("Failed to generate query embedding for SQLite: %s", e)
            
            c = sqlite3.connect(str(db))
            c.row_factory = sqlite3.Row
            like = f"%{query}%"
            
            # Get more results for potential re-ranking
            rows = c.execute(
                "SELECT path, title, substr(content,1,500) snip, tags, framework, metadata, vector "
                "FROM knowledge WHERE title LIKE ? OR content LIKE ? OR headings LIKE ? ORDER BY "
                "(CASE WHEN title LIKE ? THEN 1 WHEN content LIKE ? THEN 2 ELSE 3 END), "
                "length(title) LIMIT ?",
                (like, like, like, like, like, limit*3)
            ).fetchall()
            c.close()
            
            results = []
            for r in rows:
                if category and category not in r["tags"] and category not in r["framework"]:
                    continue
                
                # Base relevance (we'll adjust for vector similarity if available)
                base_relevance = 0.5
                final_relevance = base_relevance
                
                # Enhance with vector similarity if available
                if embedder and query_embedding is not None and r["vector"]:
                    try:
                        # Convert stored bytes back to array
                        stored_embedding = np.frombuffer(r["vector"], dtype=np.float32)
                        # Calculate cosine similarity
                        similarity = np.dot(query_embedding, stored_embedding) / (
                            np.linalg.norm(query_embedding) * np.linalg.norm(stored_embedding)
                        )
                        # Use vector similarity as primary score
                        final_relevance = round(float(similarity), 3)
                    except Exception as e:
                        logger.debug("Vector similarity calculation failed for SQLite: %s", e)
                        final_relevance = base_relevance
                
                try:
                    meta = json.loads(r["metadata"])
                except:
                    meta = {}
                
                results.append({
                    "id": r["path"],
                    "title": r["title"],
                    "snippet": r["snip"],
                    "relevance": final_relevance,
                    "tags": r["tags"].split(",") if r["tags"] else [],
                    "metadata": meta
                })
            
            # Sort by relevance (descending)
            results.sort(key=lambda x: x["relevance"], reverse=True)
            return {"query": query, "results": results[:limit], "count": len(results[:limit])}
        except Exception as e:
            logger.debug("SQLite search failed: %s", e)
    
    return {"query": query, "results": [], "count": 0, "error": "No index found"}