"""
MCP Server Performance Benchmark
=================================
Benchmarks MCP server throughput, latency, and concurrency.

Usage:
    python -m neugi_swarm_v2.benchmarks.mcp_benchmark

Requires:
    - MCP server running on stdio or http://127.0.0.1:17902
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import sys
import time
import statistics
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from neugi_swarm_v2.mcp.messages import RequestMessage
from neugi_swarm_v2.mcp.server import MCPServer


async def benchmark_stdio(
    server: MCPServer,
    tool_name: str = "echo",
    iterations: int = 100,
    concurrency: int = 1,
) -> dict:
    """Benchmark MCP server via stdio transport."""
    results = []

    async def single_call():
        req = RequestMessage(
            method="tools/call",
            params={"name": tool_name, "arguments": {"message": "benchmark_test"}},
            id="bench",
        )
        start = time.perf_counter()
        resp = await server.handle_request(req)
        elapsed = time.perf_counter() - start
        return elapsed, resp

    for i in range(iterations):
        if concurrency == 1:
            elapsed, resp = await single_call()
            results.append(elapsed)
        else:
            tasks = [single_call() for _ in range(concurrency)]
            batch_start = time.perf_counter()
            batch_responses = await asyncio.gather(*tasks)
            batch_elapsed = time.perf_counter() - batch_start
            for elapsed, _ in batch_responses:
                results.append(elapsed)
            if i > 0 and i % 10 == 0:
                print(f"  Progress: {i}/{iterations} batches ({concurrency} concurrent)")

    return {
        "tool": tool_name,
        "iterations": iterations,
        "concurrency": concurrency,
        "min_ms": min(results) * 1000,
        "max_ms": max(results) * 1000,
        "avg_ms": statistics.mean(results) * 1000,
        "median_ms": statistics.median(results) * 1000,
        "p95_ms": sorted(results)[int(len(results) * 0.95)] * 1000,
        "p99_ms": sorted(results)[int(len(results) * 0.99)] * 1000,
        "throughput": len(results) / sum(results),
        "total_time_s": sum(results),
    }


async def benchmark_http(
    url: str = "http://127.0.0.1:17902",
    tool_name: str = "echo",
    iterations: int = 50,
    concurrency: int = 5,
) -> dict:
    """Benchmark MCP server via HTTP transport."""
    import httpx

    results = []

    async def single_http_call(client: httpx.AsyncClient):
        payload = {
            "jsonrpc": "2.0",
            "id": "bench",
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": {"message": "benchmark_test"},
            },
        }
        start = time.perf_counter()
        try:
            resp = await client.post(url, json=payload, timeout=10)
            resp.raise_for_status()
            elapsed = time.perf_counter() - start
            return elapsed, resp.json()
        except Exception as e:
            return None, str(e)

    async with httpx.AsyncClient() as client:
        for i in range(iterations):
            if concurrency == 1:
                result = await single_http_call(client)
                if result[0] is not None:
                    results.append(result[0])
            else:
                tasks = [single_http_call(client) for _ in range(concurrency)]
                batch_results = await asyncio.gather(*tasks)
                for r in batch_results:
                    if r[0] is not None:
                        results.append(r[0])
            if i > 0 and i % 10 == 0:
                print(f"  Progress: {i}/{iterations} batches ({concurrency} concurrent)")

    if not results:
        return {"error": "All HTTP requests failed"}

    return {
        "tool": tool_name,
        "iterations": iterations,
        "concurrency": concurrency,
        "endpoint": url,
        "min_ms": min(results) * 1000,
        "max_ms": max(results) * 1000,
        "avg_ms": statistics.mean(results) * 1000,
        "median_ms": statistics.median(results) * 1000,
        "p95_ms": sorted(results)[int(len(results) * 0.95)] * 1000,
        "p99_ms": sorted(results)[int(len(results) * 0.99)] * 1000,
        "throughput": len(results) / sum(results) if sum(results) > 0 else 0,
        "total_time_s": sum(results),
    }


async def benchmark_all_mcp_tools(server: MCPServer) -> dict:
    """Benchmark all default MCP tools."""
    tools_list = ["echo", "get_time", "system_info", "health_check", "list_tools"]
    results = {}
    for tool in tools_list:
        print(f"  Benchmarking tool: {tool}")
        if tool == "echo":
            result = await benchmark_stdio(server, tool, iterations=100, concurrency=1)
        else:
            result = await benchmark_stdio(server, tool, iterations=50, concurrency=1)
        results[tool] = result
    return results


async def benchmark_concurrency_scaling(server: MCPServer) -> dict:
    """Benchmark how throughput scales with concurrency."""
    concurrency_levels = [1, 5, 10, 20, 50]
    results = {}
    for conc in concurrency_levels:
        print(f"  Benchmarking concurrency: {conc}")
        result = await benchmark_stdio(server, "echo", iterations=20, concurrency=conc)
        results[f"concurrency_{conc}"] = result
    return results


def print_results(results: dict, title: str = "Benchmark Results"):
    """Pretty-print benchmark results."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")

    if isinstance(results, dict):
        for key, value in results.items():
            if isinstance(value, dict):
                print(f"\n  [{key}]")
                for k, v in value.items():
                    if isinstance(v, float):
                        print(f"    {k}: {v:.3f}")
                    else:
                        print(f"    {k}: {v}")
            else:
                print(f"  {key}: {value}")


async def main():
    """Main benchmark entry point."""
    print("=" * 60)
    print("  NEUGI MCP Server Performance Benchmark")
    print("=" * 60)

    # Create server instance
    print("\n[1/4] Initializing MCP server...")
    server = MCPServer()
    print(f"  Server: {server.name} v{server.version}")
    print(f"  Tools: {server.tools.count()}")
    print(f"  Resources: {server.resources.count()}")
    print(f"  Prompts: {server.prompts.count()}")

    # Benchmark single tool
    print("\n[2/4] Benchmarking echo tool...")
    echo_results = await benchmark_stdio(server, "echo", iterations=200, concurrency=1)
    print_results(echo_results, "echo tool (200 iterations)")

    # Benchmark all tools
    print("\n[3/4] Benchmarking all MCP tools...")
    all_results = await benchmark_all_mcp_tools(server)
    print_results(all_results, "All Tools Comparison")

    # Benchmark concurrency
    print("\n[4/4] Benchmarking concurrency scaling...")
    conc_results = await benchmark_concurrency_scaling(server)
    print_results(conc_results, "Concurrency Scaling")

    # Summary
    print(f"\n{'='*60}")
    print("  SUMMARY")
    print(f"{'='*60}")
    print(f"  Server:      {server.name} v{server.version}")
    echo = echo_results
    print(f"  Echo avg:    {echo['avg_ms']:.2f}ms")
    print(f"  Echo median: {echo['median_ms']:.2f}ms")
    print(f"  Echo p95:    {echo['p95_ms']:.2f}ms")
    print(f"  Echo p99:    {echo['p99_ms']:.2f}ms")
    print(f"  Throughput:  {echo['throughput']:.0f} req/s")
    print(f"{'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
