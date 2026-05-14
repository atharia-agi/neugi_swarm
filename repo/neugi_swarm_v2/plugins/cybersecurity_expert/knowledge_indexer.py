"""Knowledge Base Indexer for Cybersecurity Expert Plugin."""

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


def build_knowledge_index(kb_root: str, index_dir: str, use_vectors: bool = True) -> int:
    kb_path = Path(kb_root).resolve()
    idx_path = Path(index_dir)
    idx_path.mkdir(parents=True, exist_ok=True)

    if not kb_path.exists():
        logger.warning("Knowledge base not found: %s", kb_path)
        return 0

    md_files = []
    for p in ["**/*.md", "**/*.MD"]:
        md_files.extend(kb_path.glob(p))
    md_files = [f for f in md_files if not any(
        part.startswith(".") or part in ("node_modules", "__pycache__") for part in f.parts
    )]
    logger.info("Found %d markdown files", len(md_files))

    # Initialize sentence transformer if requested and available
    embedder = None
    if use_vectors and HAS_SENTENCE_TRANSFORMERS:
        try:
            embedder = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Initialized sentence transformer for vector embeddings")
        except Exception as e:
            logger.warning("Failed to initialize sentence transformer: %s", e)
            embedder = None

    if HAS_WHOOSH:
        return _whoosh_index(md_files, kb_path, idx_path, embedder)
    return _sqlite_index(md_files, kb_path, idx_path, embedder)


def _whoosh_index(md_files, kb_path, idx_path, embedder=None):
    schema = Schema(
        path=ID(stored=True, unique=True),
        title=TEXT(stored=True, analyzer=StemmingAnalyzer()),
        content=TEXT(analyzer=StemmingAnalyzer()),
        headings=KEYWORD(stored=True, commas=True),
        tags=KEYWORD(stored=True, commas=True),
        framework=KEYWORD(stored=True, commas=True),
        severity=KEYWORD(stored=True, commas=True),
        metadata=STORED,
        # Vector field for embeddings (stored as binary)
        vector=STORED
    )
    ix = index.open_dir(str(idx_path)) if index.exists_in(str(idx_path)) else index.create_in(str(idx_path), schema)
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
        tags = _infer_tags(fp, fm, headings)
        
        # Generate vector embedding if embedder is available
        vector_bytes = None
        if embedder and clean.strip():
            try:
                embedding = embedder.encode([clean.strip()])[0]
                # Convert to bytes for storage
                vector_bytes = embedding.astype(np.float32).tobytes()
            except Exception as e:
                logger.debug("Failed to generate embedding for %s: %s", fp.name, e)
        
        try:
            writer.add_document(
                path=str(fp.relative_to(kb_path)), title=title, content=clean,
                headings=",".join(headings[:10]), tags=",".join(tags[:20]),
                framework=",".join(fm.get("frameworks", [])),
                severity=",".join(fm.get("severity", [])),
                metadata=json.dumps(fm),
                vector=vector_bytes)
            success += 1
        except Exception:
            continue
    writer.commit()
    logger.info("Whoosh: indexed %d/%d", success, len(md_files))
    return success


def _sqlite_index(md_files, kb_path, idx_path, embedder=None):
    db = idx_path / "kb_index.db"
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
        tags = ",".join(_infer_tags(fp, fm, headings))
        rel = str(fp.relative_to(kb_path))
        
        # Generate vector embedding if embedder is available
        vector_bytes = None
        if embedder and clean.strip():
            try:
                embedding = embedder.encode([clean.strip()])[0]
                # Convert to bytes for storage
                vector_bytes = embedding.astype(np.float32).tobytes()
            except Exception as e:
                logger.debug("Failed to generate embedding for %s: %s", fp.name, e)
        
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
    logger.info("SQLite: indexed %d/%d", success, len(md_files))
    return success


def _infer_tags(fp, fm, headings):
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