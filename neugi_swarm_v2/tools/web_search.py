"""
Web Search Tool for NEUGI v2
==============================
Multi-tier web search with Jina AI Reader (primary) and DuckDuckGo (fallback).

Features:
    - Search web and get LLM-friendly markdown results
    - Read any URL and convert to clean markdown
    - Image captioning support
    - PDF reading support
    - Caching layer for repeated queries
    - Graceful fallback chain

Usage:
    from tools.web_search import WebSearch
    
    ws = WebSearch()
    results = ws.search("latest AI breakthroughs 2026")
    content = ws.read_url("https://example.com/article")
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class SearchResult:
    """A single web search result."""
    title: str
    url: str
    content: str
    score: float = 0.0
    source: str = "unknown"  # jina, ddgs, etc.


@dataclass
class WebSearchConfig:
    """Configuration for web search."""
    jina_reader_url: str = "https://r.jina.ai/"
    jina_search_url: str = "https://s.jina.ai/"
    timeout_seconds: float = 30.0
    max_results: int = 5
    cache_enabled: bool = True
    cache_ttl_seconds: int = 3600
    fallback_to_ddgs: bool = True
    image_captioning: bool = False


class WebSearchError(Exception):
    """Base exception for web search errors."""
    pass


class WebSearch:
    """Multi-tier web search with caching and fallback."""

    def __init__(self, config: Optional[WebSearchConfig] = None):
        self.config = config or WebSearchConfig()
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._ddgs_available = self._check_ddgs()

    def _check_ddgs(self) -> bool:
        """Check if duckduckgo-search is available."""
        try:
            import duckduckgo_search
            return True
        except ImportError:
            logger.info("duckduckgo-search not installed. Fallback disabled.")
            return False

    def _cache_key(self, operation: str, query: str) -> str:
        """Generate cache key."""
        return hashlib.sha256(f"{operation}:{query}".encode()).hexdigest()[:16]

    def _get_cached(self, key: str) -> Optional[Any]:
        """Get cached result if not expired."""
        if not self.config.cache_enabled or key not in self._cache:
            return None
        entry = self._cache[key]
        if time.time() - entry["timestamp"] > self.config.cache_ttl_seconds:
            del self._cache[key]
            return None
        return entry["data"]

    def _set_cached(self, key: str, data: Any) -> None:
        """Cache result."""
        if self.config.cache_enabled:
            self._cache[key] = {"timestamp": time.time(), "data": data}

    def _fetch(self, url: str, headers: Optional[Dict[str, str]] = None) -> str:
        """Fetch URL with timeout."""
        req = urllib.request.Request(
            url,
            headers=headers or {
                "User-Agent": "NEUGI-Agent/2.0 (https://github.com/atharia-agi/neugi_swarm)"
            }
        )
        try:
            with urllib.request.urlopen(req, timeout=self.config.timeout_seconds) as resp:
                return resp.read().decode("utf-8", errors="replace")
        except Exception as e:
            raise WebSearchError(f"Fetch failed: {e}")

    def read_url(self, url: str) -> str:
        """Read any URL and convert to LLM-friendly markdown.
        
        Uses Jina AI Reader: https://r.jina.ai/https://URL
        """
        cache_key = self._cache_key("read", url)
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        jina_url = f"{self.config.jina_reader_url}{url}"
        headers = {}
        if self.config.image_captioning:
            headers["X-With-Generated-Alt"] = "true"

        try:
            content = self._fetch(jina_url, headers=headers)
            self._set_cached(cache_key, content)
            return content
        except WebSearchError as e:
            logger.warning(f"Jina Reader failed for {url}: {e}")
            # Fallback: basic fetch
            try:
                content = self._fetch(url)
                self._set_cached(cache_key, content)
                return content
            except Exception:
                raise WebSearchError(f"Failed to read URL: {url}")

    def search(self, query: str, max_results: Optional[int] = None) -> List[SearchResult]:
        """Search the web and return LLM-friendly results.
        
        Primary: Jina AI Search (https://s.jina.ai/)
        Fallback: DuckDuckGo Search (ddgs)
        """
        max_results = max_results or self.config.max_results
        cache_key = self._cache_key("search", query)
        cached = self._get_cached(cache_key)
        if cached:
            return cached

        results: List[SearchResult] = []

        # Try Jina AI Search first
        try:
            results = self._search_jina(query, max_results)
            if results:
                self._set_cached(cache_key, results)
                return results
        except Exception as e:
            logger.warning(f"Jina Search failed: {e}")

        # Fallback to DDGS
        if self.config.fallback_to_ddgs and self._ddgs_available:
            try:
                results = self._search_ddgs(query, max_results)
                if results:
                    self._set_cached(cache_key, results)
                    return results
            except Exception as e:
                logger.warning(f"DDGS fallback failed: {e}")

        return results

    def _search_jina(self, query: str, max_results: int) -> List[SearchResult]:
        """Search using Jina AI Search API."""
        encoded_query = urllib.parse.quote(query)
        url = f"{self.config.jina_search_url}{encoded_query}"
        
        response = self._fetch(url)
        
        # Jina returns markdown with results separated by ---
        results = []
        sections = response.split("\n---\n")
        
        for section in sections[:max_results]:
            lines = section.strip().split("\n")
            if not lines:
                continue
            
            # Parse title and URL from first lines
            title = ""
            url_str = ""
            content_lines = []
            
            for line in lines:
                if line.startswith("**URL:** ") or line.startswith("URL: "):
                    url_str = line.replace("**URL:** ", "").replace("URL: ", "").strip()
                elif line.startswith("**Title:** ") or line.startswith("Title: "):
                    title = line.replace("**Title:** ", "").replace("Title: ", "").strip()
                elif line.startswith("## "):
                    title = line.replace("## ", "").strip()
                elif line.startswith("### "):
                    title = line.replace("### ", "").strip()
                else:
                    content_lines.append(line)
            
            if not title and lines:
                title = lines[0].replace("## ", "").replace("### ", "").strip()
            
            content = "\n".join(content_lines).strip()
            
            if content or url_str:
                results.append(SearchResult(
                    title=title or "Untitled",
                    url=url_str or "",
                    content=content,
                    source="jina"
                ))
        
        return results

    def _search_ddgs(self, query: str, max_results: int) -> List[SearchResult]:
        """Search using DuckDuckGo Search."""
        from duckduckgo_search import DDGS
        
        results = []
        with DDGS() as ddgs:
            ddgs_results = ddgs.text(query, max_results=max_results)
            for r in ddgs_results:
                results.append(SearchResult(
                    title=r.get("title", "Untitled"),
                    url=r.get("href", ""),
                    content=r.get("body", ""),
                    source="ddgs"
                ))
        return results

    def search_and_summarize(self, query: str, max_results: int = 3) -> str:
        """Search and return a summarized markdown string."""
        results = self.search(query, max_results=max_results)
        if not results:
            return f"No results found for: {query}"
        
        lines = [f"# Search Results: {query}\n"]
        for i, r in enumerate(results, 1):
            lines.append(f"## {i}. {r.title}")
            lines.append(f"**URL:** {r.url}")
            lines.append(f"**Source:** {r.source}")
            lines.append(f"\n{r.content[:2000]}...\n" if len(r.content) > 2000 else f"\n{r.content}\n")
        
        return "\n".join(lines)

    def read_and_summarize(self, url: str) -> str:
        """Read URL and return content with metadata."""
        content = self.read_url(url)
        return f"# Content from {url}\n\n{content}"

    def clear_cache(self) -> None:
        """Clear search cache."""
        self._cache.clear()

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "entries": len(self._cache),
            "max_ttl": self.config.cache_ttl_seconds,
            "enabled": self.config.cache_enabled
        }
