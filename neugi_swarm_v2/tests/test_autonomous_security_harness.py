"""
Tests for the Autonomous Security Harness Plugin.
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

def test_plugin_import():
    """Test that the plugin can be imported and instantiated."""
    try:
        from plugins.autonomous_security_harness import AutonomousSecurityHarnessPlugin
        print("SUCCESS: AutonomousSecurityHarnessPlugin imported")
    except Exception as e:
        print(f"FAILED to import AutonomousSecurityHarnessPlugin: {e}")
        return False

    try:
        plugin = AutonomousSecurityHarnessPlugin()
        print("SUCCESS: AutonomousSecurityHarnessPlugin instantiated")
    except Exception as e:
        print(f"FAILED to instantiate AutonomousSecurityHarnessPlugin: {e}")
        return False

    return True

def test_knowledge_indexer_searcher():
    """Test the knowledge indexer and searcher components."""
    try:
        from plugins.autonomous_security_harness.core.knowledge.indexer import KnowledgeIndexer, KnowledgeSearcher
    except Exception as e:
        print(f"FAILED to import knowledge indexer/searcher: {e}")
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        kb_path = Path(tmpdir) / 'kb'
        kb_path.mkdir()
        index_path = Path(tmpdir) / 'index'

        # Create a test markdown file
        (kb_path / 'test.md').write_text('''---\ntitle: Test\nframeworks: [OWASP]\nseverity: [high]\n---\n# Test\n\nThis is a test.''')

        try:
            indexer = KnowledgeIndexer(str(kb_path), str(index_path), use_vectors=False)  # Use False to avoid needing sentence-transformers in test
            count = indexer.build_index()
            print(f"SUCCESS: Indexed {count} documents")
        except Exception as e:
            print(f"FAILED to build index: {e}")
            return False

        try:
            searcher = KnowledgeSearcher(str(index_path), use_vectors=False)
            results = searcher.search_knowledge("test", limit=5)
            print(f"SUCCESS: Search returned {results['count']} results")
        except Exception as e:
            print(f"FAILED to search: {e}")
            return False

    return True

def test_scope_validator():
    """Test the scope validator."""
    try:
        from plugins.autonomous_security_harness.core.security.scope_validator import ScopeValidator
    except Exception as e:
        print(f"FAILED to import ScopeValidator: {e}")
        return False

    # Test with a simple scope
    scope = {
        'allowed_targets': ['example.com', '192.168.1.0/24'],
        'allow_private_ips': False,
        'allowed_ports': [80, 443, 8080]
    }
    validator = ScopeValidator(scope)

    # Test allowed targets
    assert validator.validate_target('example.com', 'nmap') == True
    assert validator.validate_target('192.168.1.10', 'nmap') == True  # In CIDR
    assert validator.validate_target('10.0.0.1', 'nmap') == False   # Private IP not allowed
    assert validator.validate_target('google.com', 'nmap') == False  # Not in allowed list

    # Test port validation (if we had a method for it)
    # We don't have a public method for port validation in the current ScopeValidator, but we can add one if needed.
    # For now, we'll just test the validate_target method with a tool that doesn't care about ports.
    print("SUCCESS: Scope validator tests passed")
    return True

def test_audit_logger():
    """Test the audit logger."""
    try:
        from plugins.autonomous_security_harness.core.security.audit_logger import ImmutableAuditLogger
    except Exception as e:
        print(f"FAILED to import ImmutableAuditLogger: {e}")
        return False

    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / 'audit.jsonl'
        logger = ImmutableAuditLogger(str(log_path))

        # Log an entry
        logger.log({'action': 'test', 'data': 'value'})

        # Verify the chain
        assert logger.verify_chain() == True

        # Try to tamper with the log file
        with open(log_path, 'r') as f:
            lines = f.readlines()
        # Modify the first line (not the hash, but the content)
        if len(lines) > 0:
            # We'll just append a character to break the hash
            lines[0] = lines[0].strip() + 'x' + '\n'
            with open(log_path, 'w') as f:
                f.writelines(lines)

        # Now verification should fail
        assert logger.verify_chain() == False

        print("SUCCESS: Audit logger tests passed")
        return True

if __name__ == "__main__":
    print("Testing Autonomous Security Harness Plugin")
    print("=" * 50)

    tests = [
        ("Plugin Import", test_plugin_import),
        ("Knowledge Indexer/Searcher", test_knowledge_indexer_searcher),
        ("Scope Validator", test_scope_validator),
        ("Audit Logger", test_audit_logger),
    ]

    passed = 0
    total = len(tests)

    for name, test_func in tests:
        print(f"\nTesting: {name}")
        print("-" * 30)
        if test_func():
            print(f"+ PASSED: {name}")
            passed += 1
        else:
            print(f"- FAILED: {name}")

    print("\n" + "=" * 50)
    print(f"Results: {passed}/{total} tests passed")

    if passed == total:
        print("All tests passed! +")
        sys.exit(0)
    else:
        print("Some tests failed! -")
        sys.exit(1)
