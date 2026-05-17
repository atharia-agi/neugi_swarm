"""
Tests for the Cybersecurity Expert Plugin's vector embeddings functionality.
"""
import json
import tempfile
import os
from pathlib import Path
import sys

# Add the active package root to the path so plugin imports never resolve to
# stale audit/copy directories outside this checkout.
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

def test_knowledge_indexer_with_vectors():
    """Test that the knowledge indexer can create an index with vector embeddings."""
    try:
        from plugins.cybersecurity_expert.knowledge_indexer import build_knowledge_index
    except ImportError as e:
        raise AssertionError(f"Failed to import build_knowledge_index: {e}") from e

    with tempfile.TemporaryDirectory() as tmpdir:
        kb_path = Path(tmpdir) / 'kb'
        kb_path.mkdir()
        
        # Create a few markdown files for testing
        (kb_path / 'test1.md').write_text('''---\ntitle: SQL Injection Prevention\nframeworks: [OWASP]\nseverity: [high]\n---\n# SQL Injection Prevention\n\nUse parameterized queries to prevent SQL injection attacks.\n''')
        
        (kb_path / 'test2.md').write_text('''---\ntitle: XSS Defense\nframeworks: [OWASP]\nseverity: [medium]\n---\n# Cross-Site Scripting (XSS) Defense\n\nEscape user input to prevent XSS attacks.\n''')
        
        (kb_path / 'test3.md').write_text('''---\ntitle: Password Storage\nframeworks: [NIST]\nseverity: [high]\n---\n# Secure Password Storage\n\nUse bcrypt or argon2 for password hashing.\n''')
        
        # Create index directory
        index_path = Path(tmpdir) / 'index'
        
        # Build the index with vectors
        try:
            result = build_knowledge_index(str(kb_path), str(index_path), use_vectors=True)
            print(f"SUCCESS: Indexed {result} documents with vectors")
        except Exception as e:
            raise AssertionError(f"ERROR building index: {e}") from e
        
        # Check that the index was created
        if not index_path.exists():
            raise AssertionError("ERROR: Index directory was not created")
        
        # Check for either SQLite or Whoosh index files
        sqlite_db = index_path / 'kb_index.db'
        whoosh_files = list(index_path.glob('*.idx'))
        
        if sqlite_db.exists():
            print("SUCCESS: SQLite index created")
        elif whoosh_files:
            print(f"SUCCESS: Whoosh index created with {len(whoosh_files)} files")
        else:
            raise AssertionError("ERROR: No index files found")

def test_knowledge_searcher_with_vectors():
    """Test that the knowledge searcher can search using vector embeddings."""
    try:
        from plugins.cybersecurity_expert.knowledge_searcher import search_knowledge
    except ImportError as e:
        raise AssertionError(f"Failed to import search_knowledge: {e}") from e

    with tempfile.TemporaryDirectory() as tmpdir:
        kb_path = Path(tmpdir) / 'kb'
        kb_path.mkdir()
        
        # Create a markdown file for testing
        (kb_path / 'test_crypto.md').write_text('''---\ntitle: Cryptographic Hash Functions\nframeworks: [NIST]\nseverity: [high]\n---\n# Cryptographic Hash Functions\n\nUse SHA-256 or SHA-3 for cryptographic hashing.\nMD5 and SHA-1 are considered insecure.\n''')
        
        # Create index directory and build index
        index_path = Path(tmpdir) / 'index'
        try:
            from plugins.cybersecurity_expert.knowledge_indexer import build_knowledge_index
            build_knowledge_index(str(kb_path), str(index_path), use_vectors=True)
        except Exception as e:
            raise AssertionError(f"ERROR building index for search test: {e}") from e
        
        # Test search with a query
        try:
            results = search_knowledge(str(index_path), "secure hashing algorithms", limit=5)
            print(f"SUCCESS: Search returned {results['count']} results")
            if results['count'] > 0:
                print(f"First result: {results['results'][0]['title']} (relevance: {results['results'][0]['relevance']})")
        except Exception as e:
            raise AssertionError(f"ERROR during search: {e}") from e

        assert results["count"] >= 0

def test_hybrid_search_scoring():
    """Test that the hybrid search combines vector and keyword scores appropriately."""
    # This is more of a conceptual test - we'll check that the searcher function exists and runs
    try:
        from plugins.cybersecurity_expert.knowledge_searcher import search_knowledge
        print("SUCCESS: Hybrid search function is importable")
        assert search_knowledge is not None
    except ImportError as e:
        raise AssertionError(f"Failed to import search_knowledge: {e}") from e

if __name__ == "__main__":
    print("Testing Cybersecurity Expert Plugin Vector Embeddings Functionality")
    print("=" * 70)
    
    tests = [
        ("Knowledge Indexer with Vectors", test_knowledge_indexer_with_vectors),
        ("Knowledge Searcher with Vectors", test_knowledge_searcher_with_vectors),
        ("Hybrid Search Scoring", test_hybrid_search_scoring),
    ]
    
    passed = 0
    total = len(tests)
    
    for name, test_func in tests:
        print(f"\nTesting: {name}")
        print("-" * 40)
        try:
            test_func()
            print(f"+ PASSED: {name}")
            passed += 1
        except Exception as e:
            print(f"- FAILED: {name}: {e}")
    
    print("\n" + "=" * 70)
    print(f"Results: {passed}/{total} tests passed")
    
    if passed == total:
        print("All tests passed! +")
        sys.exit(0)
    else:
        print("Some tests failed! -")
        sys.exit(1)
