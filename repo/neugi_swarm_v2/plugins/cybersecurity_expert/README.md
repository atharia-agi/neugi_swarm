# Cybersecurity Expert Plugin for NEUGI Swarm

Enterprise-grade autonomous security assessment integrated as a native NEUGI plugin.

## Features

- **LLM-agnostic**: Works with any NEUGI provider (OpenAI, Claude, local models)
- **Knowledge-driven**: 37+ markdown files indexed (OWASP, MITRE, NIST, CVEs, etc.) with **semantic vector search** capabilities
- **Tool-integrated**: Uses NEUGI's ToolExecutor for nmap, nuclei, sqlmap, etc.
- **Compliance-aware**: Built-in ISO 27001, GDPR, NIST framework mapping
- **Safety-first**: Scope validation, rate limiting, authorization checks
- **Event-integrated**: Publishes events to NEUGI's event bus for monitoring
- **Advanced Search**: Hybrid search combining traditional keyword matching with vector embeddings for conceptual search

## Installation

```bash
# Already in plugins/ directory
neugi plugin install ./plugins/cybersecurity_expert
```

## Configuration

Add to `~/.neugi/config.json`:

```json
{
  "cybersecurity": {
    "kb_path": "K:\\Workspace\\Cybersecurity_Expert",
    "index_path": "~/.neugi/data/kb_index",
    "use_vectors": true
  }
}
```

### Configuration Options

- `kb_path`: Path to the directory containing cybersecurity knowledge base markdown files
- `index_path`: Path where the search index will be stored
- `use_vectors`: Whether to use vector embeddings for semantic search (requires sentence-transformers)

## Tools Provided

| Tool | Description |
|------|-------------|
| `security_scan` | Run nmap, nuclei, sqlmap on targets |
| `knowledge_search` | Search OWASP, MITRE, NIST knowledge base (supports semantic search) |
| `compliance_check` | Check against ISO 27001, GDPR, NIST |
| `scope_validate` | Validate targets are in authorized scope |

## Usage

```python
from neugi_swarm_v2 import NeugiSwarmV2
swarm = NeugiSwarmV2()
# Tools are auto-registered via plugin system
result = swarm.chat("Scan example.com for open ports and vulnerabilities")
```

## Knowledge Base Search

The knowledge search tool now supports both traditional keyword matching and semantic vector search:

```python
from neugi_swarm_v2.plugins.cybersecurity_expert.knowledge_searcher import search_knowledge
results = search_knowledge("~/.neugi/data/kb_index", "SQL injection prevention", category="frameworks")
```

### Search Features

- **Hybrid Search**: Combines traditional TF-IDF/KBM25 scoring with vector cosine similarity
- **Configurable Weighting**: 70% vector similarity, 30% traditional search score (can be adjusted)
- **Category Filtering**: Filter results by knowledge base categories (frameworks, tools, vulns, etc.)
- **Relevance Scoring**: Results ranked by combined relevance score

## Events Published

- `tool_execution_success` - tool completed
- `tool_execution_failure` - tool failed
- `memory_warning` - memory pressure detected

## Vector Embeddings

The plugin uses sentence-transformers (specifically 'all-MiniLM-L6-v2') to generate vector embeddings for knowledge base documents, enabling:

- Conceptual search beyond exact keyword matching
- Better retrieval of semantically related security concepts
- Improved handling of synonyms and related terms
- More accurate results for complex security queries

If sentence-transformers is not available, the plugin gracefully falls back to traditional keyword-only search.

## Requirements

- NEUGI Swarm v2.1.2 or higher
- Docker (for security tool sandboxing)
- sentence-transformers (optional, for vector search)
- whoosh (optional, for faster keyword search - falls back to SQLite if not available)

## Example Queries

Try these natural language queries with the cybersecurity expert:

1. "How do I prevent SQL injection in web applications?"
2. "What are the OWASP Top 10 vulnerabilities for 2023?"
3. "Explain the difference between IDS and IPS"
4. "Show me NIST guidelines for password storage"
5. "What tools can I use to test for XSS vulnerabilities?"
6. "Give me a checklist for GDPR compliance"