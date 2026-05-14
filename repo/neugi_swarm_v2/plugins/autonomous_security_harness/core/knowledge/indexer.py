"""
Knowledge Base Indexer for Autonomous Security Harness Plugin.
"""
import json, os, re, sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = __import__("logging").getLogger(__name__)

try:
    from whoosh import index
    from whoosh.fields import Schema, TEXT, ID, KEYWORD, STORED
    from whoosh.analysis import StemmingAnalyzer
    HAS_WHOOSH = True
except ImportError:
    HAS_WHOOSH = False

try:
    from sentence_transformers import SentenceTransformer
    import numpy as np
    HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    HAS_SENTENCE_TRANSFORMERS = False


class KnowledgeIndexer:
    def __init__(self, kb_path: str, index_path: str, use_vectors: bool = True):
        self.kb_path = Path(kb_path).resolve()
        self.index_path = Path(index_path).resolve()
        self.use_vectors = use_vectors and HAS_SENTENCE_TRANSFORMERS
        self.index_path.mkdir(parents=True, exist_ok=True)

        if self.use_vectors:
            try:
                self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("Initialized sentence transformer for vector embeddings")
            except Exception as e:
                logger.warning(f"Failed to initialize sentence transformer: {e}")
                self.use_vectors = False
                self.embedder = None
        else:
            self.embedder = None

        if HAS_WHOOSH:
            self.schema = Schema(
                path=ID(stored=True, unique=True),
                title=TEXT(stored=True, analyzer=StemmingAnalyzer()),
                content=TEXT(analyzer=StemmingAnalyzer()),
                headings=KEYWORD(stored=True, commas=True),
                tags=KEYWORD(stored=True, commas=True),
                framework=KEYWORD(stored=True, commas=True),
                severity=KEYWORD(stored=True, commas=True),
                metadata=STORED,
                vector=STORED if self.use_vectors else None  # Store vector as binary
            )
        else:
            self.schema = None  # We'll handle SQLite separately

    def build_index(self) -> int:
        """Build the knowledge index from markdown files."""
        if not self.kb_path.exists():
            logger.warning(f"Knowledge base not found: {self.kb_path}")
            return 0

        md_files = []
        for p in ["**/*.md", "**/*.MD"]:
            md_files.extend(self.kb_path.glob(p))
        md_files = [f for f in md_files if not any(
            part.startswith(".") or part in ("node_modules", "__pycache__") for part in f.parts
        )]
        logger.info(f"Found {len(md_files)} markdown files")

        if HAS_WHOOSH:
            return self._whoosh_index(md_files)
        else:
            return self._sqlite_index(md_files)

    def _whoosh_index(self, md_files) -> int:
        ix = index.open_dir(str(self.index_path)) if index.exists_in(str(self.index_path)) else index.create_in(str(self.index_path), self.schema)
        writer = ix.writer()
        success = 0
        for fp in md_files:
            try:
                content = fp.read_text("utf-8", errors="replace")
            except Exception:
                continue
            fm, clean = {}, content
            if content.startswith("---"):
                end = content.find("---", 3)
                if end != -1:
                    try:
                        fm = __import__("yaml").safe_load(content[3:end]) or {}
                    except Exception:
                        pass
                    clean = content[end + 3:].strip()
            headings = re.findall(r"^#{1,6}\s+(.+)$", clean, re.MULTILINE)
            title = fm.get("title") or (headings[0] if headings else fp.stem)
            tags = self._infer_tags(fp, fm, headings)
            
            # Generate vector embedding if embedder is available
            vector_bytes = None
            if self.embedder and clean.strip():
                try:
                    embedding = self.embedder.encode([clean.strip()])[0]
                    vector_bytes = embedding.astype(np.float32).tobytes()
                except Exception as e:
                    logger.debug(f"Failed to generate embedding for {fp.name}: {e}")
            
            try:
                writer.add_document(
                    path=str(fp.relative_to(self.kb_path)), title=title, content=clean,
                    headings=",".join(headings[:10]), tags=",".join(tags[:20]),
                    framework=",".join(fm.get("frameworks", [])),
                    severity=",".join(fm.get("severity", [])),
                    metadata=json.dumps(fm),
                    vector=vector_bytes)
                success += 1
            except Exception:
                continue
        writer.commit()
        logger.info(f"Whoosh: indexed {success}/{len(md_files)}")
        return success

    def _sqlite_index(self, md_files) -> int:
        db = self.index_path / "kb_index.db"
        conn = sqlite3.connect(str(db))
        conn.execute("""CREATE TABLE IF NOT EXISTS knowledge (
            path TEXT PRIMARY KEY, title TEXT, content TEXT, headings TEXT,
            tags TEXT, framework TEXT, severity TEXT, tools TEXT, metadata TEXT,
            vector BLOB)""")
        conn.execute("CREATE VIRTUAL TABLE IF NOT EXISTS kb_fts USING fts5(path, title, content, headings)")
        success = 0
        for fp in md_files:
            try:
                content = fp.read_text("utf-8", errors="replace")
            except Exception:
                continue
            fm, clean = {}, content
            if content.startswith("---"):
                end = content.find("---", 3)
                if end != -1:
                    try:
                        fm = __import__("yaml").safe_load(content[3:end]) or {}
                    except Exception:
                        pass
                    clean = content[end + 3:].strip()
            headings = re.findall(r"^#{1,6}\s+(.+)$", clean, re.MULTILINE)
            title = fm.get("title") or (headings[0] if headings else fp.stem)
            tags = ",".join(self._infer_tags(fp, fm, headings))
            rel = str(fp.relative_to(self.kb_path))
            
            # Generate vector embedding if embedder is available
            vector_bytes = None
            if self.embedder and clean.strip():
                try:
                    embedding = self.embedder.encode([clean.strip()])[0]
                    vector_bytes = embedding.astype(np.float32).tobytes()
                except Exception as e:
                    logger.debug(f"Failed to generate embedding for {fp.name}: {e}")
            
            try:
                conn.execute("INSERT OR REPLACE INTO knowledge VALUES (?,?,?,?,?,?,?,?,?,?)",
                             (rel, title, clean[:50000], ",".join(headings[:10]), tags,
                              json.dumps(fm.get("frameworks", [])),
                              json.dumps(fm.get("severity", "")),
                              json.dumps(fm.get("tools", [])),
                              json.dumps(fm),
                              vector_bytes))
                conn.execute("INSERT OR REPLACE INTO kb_fts VALUES (?,?,?,?)",
                             (rel, title, clean[:50000], "\n".join(headings[:10])))
                success += 1
            except Exception:
                continue
        conn.commit()
        conn.close()
        logger.info(f"SQLite: indexed {success}/{len(md_files)}")
        return success

    def _infer_tags(self, fp, fm, headings):
        tags = set()
        name = fp.stem.lower()
        kw_map = {
            "owasp": "owasp", "mitre": "mitre", "nist": "nist", "cve": "cve",
            "cwe": "cwe", "pentest": "pentest", "compliance": "compliance",
            "threat": "threat-intel", "ai": "ai-security", "llm": "ai-security",
        }
        for kw, tag in kw_map.items():
            if kw in name:
                tags.add(tag)
        if "category" in fm:
            tags.add(str(fm["category"]).lower())
        for h in headings:
            hl = h.lower()
            if any(k in hl for k in ["vulnerability", "exploit", "attack"]):
                tags.add("vulnerability")
            if any(k in hl for k in ["compliance", "audit", "governance"]):
                tags.add("compliance")
            if any(k in hl for k in ["threat", "ioc", "ttp"]):
                tags.add("threat-intel")
        return list(tags)


class KnowledgeSearcher:
    def __init__(self, index_path: str, use_vectors: bool = True):
        self.index_path = Path(index_path).resolve()
        self.use_vectors = use_vectors and HAS_SENTENCE_TRANSFORMERS
        if self.use_vectors:
            try:
                self.embedder = SentenceTransformer('all-MiniLM-L6-v2')
            except Exception as e:
                logger.warning(f"Failed to initialize sentence transformer for search: {e}")
                self.use_vectors = False
                self.embedder = None
        else:
            self.embedder = None

        if HAS_WHOOSH and self.index_path.exists():
            try:
                self.ix = index.open_dir(str(self.index_path))
                self.HAS_INDEX = True
            except Exception as e:
                logger.warning(f"Failed to open Whoosh index: {e}")
                self.HAS_INDEX = False
        else:
            self.HAS_INDEX = False

        if not self.HAS_INDEX:
            self.db_path = self.index_path / "kb_index.db"
            if not self.db_path.exists():
                logger.warning(f"No knowledge base index found at {self.index_path}")
            else:
                logger.info(f"Using SQLite index at {self.db_path}")

    def _cosine_similarity(self, vec1: bytes, vec2: bytes) -> float:
        """Calculate cosine similarity between two binary vectors."""
        try:
            a = np.frombuffer(vec1, dtype=np.float32)
            b = np.frombuffer(vec2, dtype=np.float32)
            dot_product = np.dot(a, b)
            norm_a = np.linalg.norm(a)
            norm_b = np.linalg.norm(b)
            if norm_a == 0 or norm_b == 0:
                return 0.0
            return dot_product / (norm_a * norm_b)
        except Exception:
            return 0.0

    def search_knowledge(self, query: str, category: Optional[str] = None, limit: int = 10) -> Dict[str, Any]:
        """Search the knowledge base."""
        if self.HAS_INDEX:
            return self._whoosh_search(query, category, limit)
        else:
            return self._sqlite_search(query, category, limit)

    def _whoosh_search(self, query: str, category: Optional[str], limit: int) -> Dict[str, Any]:
        try:
            from whoosh.qparser import MultifieldParser, OrGroup
            parser = MultifieldParser(["title","content","headings","tags","framework"], schema=self.ix.schema, group=OrGroup)
            with self.ix.searcher() as s:
                hits = s.search(parser.parse(query), limit=limit*5)  # Get more hits for re-ranking
                results = []
                
                # Generate query embedding if vector search is enabled
                query_embedding = None
                if self.use_vectors and self.embedder and query.strip():
                    try:
                        query_embedding = self.embedder.encode([query.strip()])[0].astype(np.float32)
                    except Exception as e:
                        logger.debug(f"Failed to generate query embedding: {e}")
                
                for hit in hits:
                    d = hit.fields()
                    if category and category not in d.get("tags","") and category not in d.get("framework",""):
                        continue
                    
                    base_relevance = round(hit.score, 3)
                    final_relevance = base_relevance
                    
                    if self.use_vectors and self.embedder and query_embedding is not None and d.get("vector"):
                        try:
                            vector_bytes = d.get("vector")
                            if vector_bytes:
                                stored_embedding = np.frombuffer(vector_bytes, dtype=np.float32)
                                similarity = np.dot(query_embedding, stored_embedding) / (
                                    np.linalg.norm(query_embedding) * np.linalg.norm(stored_embedding)
                                )
                                final_relevance = round(0.7 * float(similarity) + 0.3 * base_relevance, 3)
                        except Exception as e:
                            logger.debug(f"Vector similarity calculation failed: {e}")
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
                
                results.sort(key=lambda x: x["relevance"], reverse=True)
                return {"query": query, "results": results[:limit], "count": len(results[:limit])}
        except Exception as e:
            logger.error(f"Whoosh search failed: {e}")
            return {"query": query, "results": [], "count": 0, "error": "Whoosh search error"}

    def _sqlite_search(self, query: str, category: Optional[str], limit: int) -> Dict[str, Any]:
        import sqlite3
        if not self.db_path.exists():
            return {"query": query, "results": [], "count": 0, "error": "No index found"}
        
        try:
            # Generate query embedding for SQLite vector search
            query_embedding = None
            if self.use_vectors and self.embedder and query.strip():
                try:
                    query_embedding = self.embedder.encode([query.strip()])[0].astype(np.float32)
                except Exception as e:
                    logger.debug(f"Failed to generate query embedding for SQLite: {e}")
            
            c = sqlite3.connect(str(self.db_path))
            c.row_factory = sqlite3.Row
            like = f"%{query}%"
            
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
                
                base_relevance = 0.5
                final_relevance = base_relevance
                
                if self.use_vectors and self.embedder and query_embedding is not None and r["vector"]:
                    try:
                        stored_embedding = np.frombuffer(r["vector"], dtype=np.float32)
                        similarity = np.dot(query_embedding, stored_embedding) / (
                            np.linalg.norm(query_embedding) * np.linalg.norm(stored_embedding)
                        )
                        final_relevance = round(float(similarity), 3)
                    except Exception as e:
                        logger.debug(f"Vector similarity calculation failed for SQLite: {e}")
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
            
            results.sort(key=lambda x: x["relevance"], reverse=True)
            return {"query": query, "results": results[:limit], "count": len(results[:limit])}
        except Exception as e:
            logger.error(f"SQLite search failed: {e}")
            return {"query": query, "results": [], "count": 0, "error": "SQLite search error"}