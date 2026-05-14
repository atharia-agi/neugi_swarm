import sys
import os
# Set the path to include the package root
sys.path.insert(0, os.path.abspath('.'))

try:
    from plugins.cybersecurity_expert.knowledge_indexer import build_knowledge_index
    print("SUCCESS: build_knowledge_index imported")
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)

try:
    from plugins.cybersecurity_expert.knowledge_searcher import search_knowledge
    print("SUCCESS: search_knowledge imported")
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)

try:
    from plugins.cybersecurity_expert import CybersecurityExpertPlugin
    print("SUCCESS: CybersecurityExpertPlugin imported")
except Exception as e:
    print(f"FAILED: {e}")
    sys.exit(1)

print("All imports successful.")