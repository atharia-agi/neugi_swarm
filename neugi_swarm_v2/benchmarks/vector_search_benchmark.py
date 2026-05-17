"""
Performance benchmarks for the Cybersecurity Expert Plugin's vector search functionality.
"""
import json
import tempfile
import time
import statistics
from pathlib import Path
import sys
import os

# Add the active package root to the path so benchmark imports never resolve
# to stale audit/copy directories outside this checkout.
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

def create_test_knowledge_base(num_docs=100):
    """Create a test knowledge base with specified number of documents."""
    test_docs = []
    
    # Sample cybersecurity topics for generating test data
    topics = [
        "SQL Injection Prevention",
        "Cross-Site Scripting (XSS) Defense", 
        "Secure Password Storage",
        "Network Firewall Configuration",
        "Intrusion Detection Systems",
        "Encryption Algorithms",
        "Secure Socket Layer (SSL/TLS)",
        "Virtual Private Network (VPN)",
        "Two-Factor Authentication",
        "Security Information and Event Management (SIEM)",
        "Vulnerability Assessment",
        "Penetration Testing Methodology",
        "Incident Response Plan",
        "Disaster Recovery Planning",
        "Security Awareness Training",
        "Access Control Models",
        "Authentication Protocols",
        "Authorization Frameworks",
        "Cryptographic Hash Functions",
        "Digital Signatures"
    ]
    
    frameworks = ["OWASP", "NIST", "ISO27001", "GDPR", "HIPAA", "PCI-DSS"]
    severities = ["low", "medium", "high", "critical"]
    
    for i in range(num_docs):
        topic = topics[i % len(topics)]
        framework = frameworks[i % len(frameworks)]
        severity = severities[i % len(severities)]
        
        doc_content = f'''---\ntitle: {topic}\nframeworks: [{framework}]\nseverity: [{severity}]\n---\n# {topic}\n\nThis document discusses {topic.lower()} in detail. It covers best practices, implementation guidelines, and common pitfalls to avoid. Proper implementation of {topic.lower()} is essential for maintaining a strong security posture.\n\nKey points:\n1. Regular updates and patches\n2. Monitoring and logging\n3. User training and awareness\n4. Compliance with relevant standards\n5. Continuous improvement processes\n'''
        
        test_docs.append((f"test_{i:03d}.md", doc_content))
    
    return test_docs

def benchmark_indexing_performance():
    """Benchmark the performance of knowledge base indexing with vectors."""
    print("Benchmarking indexing performance...")
    
    try:
        from plugins.cybersecurity_expert.knowledge_indexer import build_knowledge_index
    except ImportError as e:
        print(f"Failed to import build_knowledge_index: {e}")
        return None
    
    # Test with different document counts
    doc_counts = [10, 50, 100, 200]
    results = {}
    
    for count in doc_counts:
        with tempfile.TemporaryDirectory() as tmpdir:
            kb_path = Path(tmpdir) / 'kb'
            kb_path.mkdir()
            
            # Create test documents
            test_docs = create_test_knowledge_base(count)
            for filename, content in test_docs:
                (kb_path / filename).write_text(content)
            
            # Create index directory
            index_path = Path(tmpdir) / 'index'
            
            # Measure indexing time
            start_time = time.time()
            try:
                result = build_knowledge_index(str(kb_path), str(index_path), use_vectors=True)
                end_time = time.time()
                
                indexing_time = end_time - start_time
                docs_per_second = result / indexing_time if indexing_time > 0 else 0
                
                results[count] = {
                    'documents': result,
                    'time_seconds': indexing_time,
                    'docs_per_second': docs_per_second
                }
                
                print(f"  {count:3d} docs: {indexing_time:.3f}s ({docs_per_second:.1f} docs/sec)")
                
            except Exception as e:
                print(f"  ERROR indexing {count} docs: {e}")
                results[count] = {'error': str(e)}
    
    return results

def benchmark_search_performance():
    """Benchmark the performance of knowledge base search with vectors."""
    print("Benchmarking search performance...")
    
    try:
        from plugins.cybersecurity_expert.knowledge_searcher import search_knowledge
        from plugins.cybersecurity_expert.knowledge_indexer import build_knowledge_index
    except ImportError as e:
        print(f"Failed to import required modules: {e}")
        return None
    
    # Create a test knowledge base
    with tempfile.TemporaryDirectory() as tmpdir:
        kb_path = Path(tmpdir) / 'kb'
        kb_path.mkdir()
        
        # Create test documents
        test_docs = create_test_knowledge_base(50)  # 50 documents for search testing
        for filename, content in test_docs:
            (kb_path / filename).write_text(content)
        
        # Create index directory and build index
        index_path = Path(tmpdir) / 'index'
        try:
            build_knowledge_index(str(kb_path), str(index_path), use_vectors=True)
        except Exception as e:
            print(f"ERROR building index for search benchmark: {e}")
            return None
        
        # Test queries
        test_queries = [
            "SQL injection prevention",
            "How to defend against XSS attacks",
            "Best practices for password storage",
            "Network security firewall configuration",
            "Encryption algorithms and protocols",
            "What is two-factor authentication",
            "Security monitoring and SIEM systems",
            "Vulnerability assessment methodologies",
            "Incident response procedures",
            "Access control and authentication mechanisms"
        ]
        
        # Measure search times
        search_times = []
        for query in test_queries:
            start_time = time.time()
            try:
                results = search_knowledge(str(index_path), query, limit=10)
                end_time = time.time()
                
                search_time = end_time - start_time
                search_times.append(search_time)
                
                print(f"  '{query[:30]:30s}': {search_time:.4f}s ({results['count']} results)")
                
            except Exception as e:
                print(f"  ERROR searching for '{query}': {e}")
                search_times.append(float('inf'))
        
        # Calculate statistics
        valid_times = [t for t in search_times if t != float('inf')]
        if valid_times:
            return {
                'queries': len(test_queries),
                'successful_queries': len(valid_times),
                'mean_time': statistics.mean(valid_times),
                'median_time': statistics.median(valid_times),
                'stdev_time': statistics.stdev(valid_times) if len(valid_times) > 1 else 0,
                'min_time': min(valid_times),
                'max_time': max(valid_times)
            }
        else:
            return None

def benchmark_hybrid_vs_keyword_only():
    """Benchmark hybrid search vs keyword-only search to show performance impact."""
    print("Benchmarking hybrid vs keyword-only search...")
    
    try:
        from plugins.cybersecurity_expert.knowledge_searcher import search_knowledge
        from plugins.cybersecurity_expert.knowledge_indexer import build_knowledge_index
    except ImportError as e:
        print(f"Failed to import required modules: {e}")
        return None
    
    # Create a test knowledge base
    with tempfile.TemporaryDirectory() as tmpdir:
        kb_path = Path(tmpdir) / 'kb'
        kb_path.mkdir()
        
        # Create test documents
        test_docs = create_test_knowledge_base(30)
        for filename, content in test_docs:
            (kb_path / filename).write_text(content)
        
        # Create index directory
        index_path = Path(tmpdir) / 'index'
        
        # Build index with vectors
        try:
            build_knowledge_index(str(kb_path), str(index_path), use_vectors=True)
        except Exception as e:
            print(f"ERROR building index: {e}")
            return None
        
        # Test queries
        test_queries = [
            "SQL injection prevention techniques",
            "Cross site scripting defense methods",
            "Secure password hashing algorithms",
            "Network intrusion detection systems"
        ]
        
        hybrid_times = []
        keyword_times = []
        
        for query in test_queries:
            # Hybrid search (with vectors)
            start_time = time.time()
            try:
                results = search_knowledge(str(index_path), query, limit=10, use_vectors=True)
                end_time = time.time()
                hybrid_times.append(end_time - start_time)
            except Exception as e:
                print(f"  Hybrid search error for '{query}': {e}")
                hybrid_times.append(float('inf'))
            
            # Keyword-only search (without vectors)
            start_time = time.time()
            try:
                results = search_knowledge(str(index_path), query, limit=10, use_vectors=False)
                end_time = time.time()
                keyword_times.append(end_time - start_time)
            except Exception as e:
                print(f"  Keyword search error for '{query}': {e}")
                keyword_times.append(float('inf'))
        
        # Calculate averages
        valid_hybrid = [t for t in hybrid_times if t != float('inf')]
        valid_keyword = [t for t in keyword_times if t != float('inf')]
        
        if valid_hybrid and valid_keyword:
            return {
                'queries': len(test_queries),
                'hybrid_mean': statistics.mean(valid_hybrid),
                'keyword_mean': statistics.mean(valid_keyword),
                'overhead_percent': ((statistics.mean(valid_hybrid) - statistics.mean(valid_keyword)) / statistics.mean(valid_keyword)) * 100 if statistics.mean(valid_keyword) > 0 else 0
            }
        else:
            return None

def run_benchmarks():
    """Run all benchmarks and display results."""
    print("Cybersecurity Expert Plugin - Vector Search Performance Benchmarks")
    print("=" * 70)
    
    # Indexing performance
    print("\n1. Indexing Performance (with vector embeddings)")
    print("-" * 50)
    indexing_results = benchmark_indexing_performance()
    
    # Search performance
    print("\n2. Search Performance (with vector embeddings)")
    print("-" * 50)
    search_results = benchmark_search_performance()
    
    # Hybrid vs keyword-only comparison
    print("\n3. Hybrid Search vs Keyword-Only Search Overhead")
    print("-" * 50)
    comparison_results = benchmark_hybrid_vs_keyword_only()
    
    # Summary
    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY")
    print("=" * 70)
    
    if indexing_results:
        print("\nIndexing Performance:")
        for count, result in indexing_results.items():
            if 'error' not in result:
                print(f"  {count:3d} documents: {result['time_seconds']:.3f}s "
                      f"({result['docs_per_second']:.1f} docs/sec)")
            else:
                print(f"  {count:3d} documents: ERROR - {result['error']}")
    
    if search_results:
        print("\nSearch Performance:")
        print(f"  Queries tested: {search_results['queries']}")
        print(f"  Successful: {search_results['successful_queries']}/{search_results['queries']}")
        print(f"  Mean time: {search_results['mean_time']*1000:.2f} ms")
        print(f"  Median time: {search_results['median_time']*1000:.2f} ms")
        print(f"  Std deviation: {search_results['stdev_time']*1000:.2f} ms")
        print(f"  Range: {search_results['min_time']*1000:.2f} - {search_results['max_time']*1000:.2f} ms")
    
    if comparison_results:
        print("\nHybrid vs Keyword-Only Search:")
        print(f"  Queries tested: {comparison_results['queries']}")
        print(f"  Hybrid search mean: {comparison_results['hybrid_mean']*1000:.2f} ms")
        print(f"  Keyword-only mean: {comparison_results['keyword_mean']*1000:.2f} ms")
        print(f"  Overhead: {comparison_results['overhead_percent']:.1f}%")
    
    print("\nBenchmark completed.")
    
    return {
        'indexing': indexing_results,
        'search': search_results,
        'comparison': comparison_results
    }

if __name__ == "__main__":
    run_benchmarks()
