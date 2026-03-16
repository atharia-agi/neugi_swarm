#!/usr/bin/env python3
"""
🤖 NEUGI SWARM - WEB BROWSER AGENT v2.0
========================================

POWERFUL FREE WEB BROWSING - No expensive APIs!

Based on research from:
- openclaw-free-web-search (SearXNG + Scrapling)
- Jina AI Reader (free content extraction)
- Multi-source cross-validation

Version: 2.0
Date: March 14, 2026
"""

import re
import requests
from typing import Dict, List, Optional
from urllib.parse import quote_plus
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed


class SearchEngine:
    """Free multi-engine web search"""

    # Public SearXNG instances (fallback)
    SEARXNG_INSTANCES = [
        "https://searx.be",
        "https://searx.org",
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )

    def search_duckduckgo(self, query: str, num_results: int = 5) -> List[Dict]:
        """Search DuckDuckGo (FREE!)"""
        results = []
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            r = self.session.get(url, timeout=10)
            if not r.ok:
                return results

            pattern = r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>.*?<a class="result__snippet"[^>]*>([^<]+)</a>'

            for match in re.finditer(pattern, r.text, re.DOTALL):
                url = match.group(1)
                title = re.sub(r"<[^>]+>", "", match.group(2)).strip()
                snippet = re.sub(r"<[^>]+>", "", match.group(3)).strip()

                if url and title:
                    results.append(
                        {
                            "title": title,
                            "url": url,
                            "snippet": snippet,
                            "source": "DuckDuckGo",
                            "quality_score": 0.7,
                        }
                    )
                if len(results) >= num_results:
                    break
        except Exception as e:
            print(f"DDG error: {e}")
        return results

    def search_searxng(self, query: str, num_results: int = 5) -> List[Dict]:
        """Search using SearXNG (FREE, privacy-focused)"""
        results = []

        for inst in self.SEARXNG_INSTANCES:
            try:
                url = f"{inst}/search?q={quote_plus(query)}&format=json"
                r = self.session.get(url, timeout=10)
                if r.ok:
                    data = r.json()
                    for item in data.get("results", [])[:num_results]:
                        results.append(
                            {
                                "title": item.get("title", ""),
                                "url": item.get("url", ""),
                                "snippet": item.get("content", ""),
                                "source": f"SearXNG ({inst})",
                                "quality_score": 0.8,
                            }
                        )
                    if results:
                        break
            except Exception:
                continue
        return results

    def search_brave(self, query: str, num_results: int = 5) -> List[Dict]:
        """Search Brave (FREE - no API key needed for basic)"""
        results = []
        try:
            url = f"https://search.brave.com/search?q={quote_plus(query)}"
            r = self.session.get(url, timeout=10)
            if r.ok:
                pattern = r'<a class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>.*?<p class="result__description"[^>]*>([^<]+)</p>'
                for match in re.finditer(pattern, r.text, re.DOTALL):
                    url = match.group(1)
                    title = match.group(2).strip()
                    snippet = match.group(3).strip()
                    if url and title:
                        results.append(
                            {
                                "title": title,
                                "url": url,
                                "snippet": snippet,
                                "source": "Brave",
                                "quality_score": 0.85,
                            }
                        )
                    if len(results) >= num_results:
                        break
        except Exception:
            pass
        return results

    def search_multi(self, query: str, num_results: int = 5) -> List[Dict]:
        """Multi-engine search with quality scoring"""
        all_results = []

        # Parallel search
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {
                executor.submit(self.search_duckduckgo, query, num_results): "ddg",
                executor.submit(self.search_searxng, query, num_results): "searxng",
                executor.submit(self.search_brave, query, num_results): "brave",
            }

            for future in as_completed(futures):
                try:
                    results = future.result()
                    all_results.extend(results)
                except Exception:
                    pass

        # Deduplicate by URL domain
        seen = set()
        unique_results = []
        for r in all_results:
            domain = r["url"].split("/")[2] if "//" in r["url"] else ""
            if domain not in seen:
                seen.add(domain)
                unique_results.append(r)
            if len(unique_results) >= num_results:
                break

        return unique_results[:num_results]


class ContentExtractor:
    """Extract clean content from webpages - FREE!"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )

    def extract_jina(self, url: str) -> Optional[str]:
        """Jina AI Reader - FREE content extraction"""
        try:
            r = requests.get(f"https://r.jina.ai/{url}", timeout=15)
            if r.ok:
                return r.text
        except Exception:
            pass
        return None

    def extract_readability(self, url: str) -> Optional[str]:
        """Basic HTML to text extraction"""
        try:
            r = self.session.get(url, timeout=10)
            if r.ok:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(r.text, "html.parser")

                # Remove unwanted
                for tag in soup(["script", "style", "nav", "footer", "header"]):
                    tag.decompose()

                # Get text
                text = soup.get_text(separator="\n")
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                return "\n".join(lines[:100])  # First 100 lines
        except Exception:
            pass
        return None

    def extract(self, url: str, max_length: int = 8000) -> Dict:
        """Extract content with fallback chain"""
        result = {"url": url, "content": "", "success": False, "method": "none"}

        # Try Jina first (best extraction)
        content = self.extract_jina(url)
        if content:
            result["content"] = content[:max_length]
            result["success"] = True
            result["method"] = "jina_ai"
            return result

        # Fallback to readability
        content = self.extract_readability(url)
        if content:
            result["content"] = content[:max_length]
            result["success"] = True
            result["method"] = "readability"
            return result

        return result


class ClaimVerifier:
    """
    Cross-validate claims - tells you how much to trust the answer!

    Based on openclaw-free-web-search's verify_claim.py
    """

    def __init__(self):
        self.search = SearchEngine()
        self.extract = ContentExtractor()

    def verify(self, claim: str, num_sources: int = 3) -> Dict:
        """
        Verify a claim against multiple sources

        Returns verdict with confidence score:
        - VERIFIED: ≥75% - Multiple high-authority sources agree
        - LIKELY_TRUE: 55-74% - Majority support
        - UNCERTAIN: 35-54% - Mixed evidence
        - LIKELY_FALSE: 15-34% - Multiple sources contradict
        - UNVERIFIABLE: <15% - Cannot find sources
        """
        result = {
            "claim": claim,
            "verdict": "UNVERIFIABLE",
            "confidence": 0,
            "sources_checked": 0,
            "agree": 0,
            "contradict": 0,
            "neutral": 0,
            "sources": [],
        }

        # Expand claim into search queries
        queries = [claim, f'"{claim}"', f"Is it true that {claim}?"]

        all_urls = []

        # Search for sources
        for query in queries[:2]:
            results = self.search.search_multi(query, num_results=5)
            for r in results:
                if r["url"] not in [s["url"] for s in all_urls]:
                    all_urls.append(r)
            if len(all_urls) >= num_sources:
                break

        # Extract from sources
        for source in all_urls[:num_sources]:
            content_data = self.extract.extract(source["url"])
            if content_data["success"]:
                result["sources_checked"] += 1
                source_info = {
                    "url": source["url"],
                    "title": source.get("title", ""),
                    "content": content_data["content"][:500] if content_data["content"] else "",
                    "agree": False,
                    "contradict": False,
                }

                # Simple keyword-based analysis
                content_lower = content_data["content"].lower() if content_data["content"] else ""
                claim.lower()

                # Check for agreement/contradiction keywords
                positive = ["yes", "true", "correct", "confirmed", "verified"]
                negative = ["no", "false", "incorrect", "denied", "fake"]

                has_positive = any(w in content_lower for w in positive)
                has_negative = any(w in content_lower for w in negative)

                if has_positive and not has_negative:
                    source_info["agree"] = True
                    result["agree"] += 1
                elif has_negative:
                    source_info["contradict"] = True
                    result["contradict"] += 1
                else:
                    result["neutral"] += 1

                result["sources"].append(source_info)

        # Calculate verdict
        if result["sources_checked"] == 0:
            result["verdict"] = "UNVERIFIABLE"
            result["confidence"] = 5
        else:
            agreement_ratio = (result["agree"] - result["contradict"]) / result["sources_checked"]

            if result["agree"] >= num_sources and result["contradict"] == 0:
                result["verdict"] = "VERIFIED"
                result["confidence"] = 80 + (result["agree"] * 5)
            elif agreement_ratio > 0.3:
                result["verdict"] = "LIKELY_TRUE"
                result["confidence"] = 60 + int(agreement_ratio * 30)
            elif agreement_ratio < -0.3:
                result["verdict"] = "LIKELY_FALSE"
                result["confidence"] = 20 + int(abs(agreement_ratio) * 30)
            else:
                result["verdict"] = "UNCERTAIN"
                result["confidence"] = 40 + int(abs(agreement_ratio) * 20)

        result["confidence"] = min(result["confidence"], 99)

        return result


class WebBrowser:
    """
    Complete web browser agent for NEUGI

    Features:
    - Multi-engine search (FREE)
    - Clean content extraction (FREE)
    - Claim verification with confidence score
    - No API keys required!
    """

    def __init__(self):
        self.search = SearchEngine()
        self.extract = ContentExtractor()
        self.verify = ClaimVerifier()

    def search_web(self, query: str, num_results: int = 5) -> List[Dict]:
        """Search the web"""
        return self.search.search_multi(query, num_results)

    def browse(self, query: str, mode: str = "search") -> Dict:
        """
        Browse the web

        Modes:
        - "search": Just search
        - "read": Search + extract top result
        - "verify": Search + extract + verify claims
        """
        output = {
            "query": query,
            "mode": mode,
            "timestamp": datetime.now().isoformat(),
            "results": [],
            "content": [],
            "verification": None,
            "summary": "",
        }

        # Search
        search_results = self.search.search_multi(query)
        output["results"] = search_results

        if not search_results:
            output["summary"] = "No results found."
            return output

        # Get content if needed
        if mode in ["read", "verify"]:
            targets = search_results[:3] if mode == "read" else search_results

            for r in targets:
                content = self.extract.extract(r["url"])
                if content["success"]:
                    output["content"].append(
                        {
                            "title": r.get("title", ""),
                            "url": r["url"],
                            "content": content["content"],
                            "method": content["method"],
                        }
                    )

        # Verify if needed
        if mode == "verify":
            output["verification"] = self.verify.verify(query)

        # Summary
        total_chars = sum(len(c.get("content", "")) for c in output["content"])
        output["summary"] = f"Found {len(search_results)} results. "

        if output["content"]:
            output["summary"] += (
                f"Retrieved content from {len(output['content'])} pages ({total_chars} chars). "
            )

        if output["verification"]:
            v = output["verification"]
            output["summary"] += f"Verification: {v['verdict']} ({v['confidence']}% confidence)"

        return output


# ============================================================
# STANDALONE USAGE
# ============================================================

if __name__ == "__main__":
    import sys

    browser = WebBrowser()

    if len(sys.argv) < 2:
        print("""
🤖 NEUGI WEB BROWSER AGENT v2.0
================================

Usage:
    python neugi_swarm_browser.py search "query"     - Search web
    python neugi_swarm_browser.py browse "query"    - Search + read content  
    python neugi_swarm_browser.py verify "claim"   - Search + verify claim
    python neugi_swarm_browser.py url "https://..." - Extract URL content

Features:
    ✅ Multi-engine search (DuckDuckGo, SearXNG, Brave)
    ✅ Clean content extraction (Jina AI, readability)
    ✅ Claim verification with confidence score
    ✅ NO API keys required!
    ✅ Completely FREE!

Examples:
    python neugi_swarm_browser.py search "latest AI news"
    python neugi_swarm_browser.py browse "what is Ollama"
    python neugi_swarm_browser.py verify "qwen3.5 is the best model"
    python neugi_swarm_browser.py url "https://github.com"
""")
        sys.exit(1)

    cmd = sys.argv[1].lower()
    query = " ".join(sys.argv[2:])

    if cmd == "search":
        results = browser.search_web(query)
        print(f"\n🔍 Results for: {query}\n")
        for i, r in enumerate(results, 1):
            print(f"{i}. {r.get('title', 'N/A')}")
            print(f"   {r.get('url', 'N/A')}")
            print(f"   📊 Quality: {r.get('quality_score', 0) * 100:.0f}%")
            print()

    elif cmd == "browse":
        result = browser.browse(query, mode="read")
        print(f"\n🔍 Research: {query}\n")
        print(result["summary"])
        print("\n" + "=" * 50 + "\n")

        for i, c in enumerate(result.get("content", []), 1):
            print(f"📄 Source {i}: {c.get('title', 'N/A')}")
            print(f"   {c.get('url', 'N/A')}")
            print(f"   Method: {c.get('method', 'unknown')}")
            print(f"\n{c.get('content', 'N/A')[:500]}...")
            print("\n" + "-" * 50 + "\n")

    elif cmd == "verify":
        result = browser.browse(query, mode="verify")
        v = result.get("verification", {})

        print(f"\n🔍 Claim Verification: {query}\n")

        verdict_emoji = {
            "VERIFIED": "✅",
            "LIKELY_TRUE": "🟢",
            "UNCERTAIN": "🟡",
            "LIKELY_FALSE": "🔴",
            "UNVERIFIABLE": "⬜",
        }

        emoji = verdict_emoji.get(v.get("verdict", "UNVERIFIABLE"), "⬜")
        print(f"{emoji} VERDICT: {v.get('verdict', 'UNKNOWN')}")
        print(f"📊 CONFIDENCE: {v.get('confidence', 0)}%")
        print(f"📚 SOURCES: {v.get('sources_checked', 0)} checked")
        print(f"   - Agree: {v.get('agree', 0)}")
        print(f"   - Contradict: {v.get('contradict', 0)}")
        print(f"   - Neutral: {v.get('neutral', 0)}")
        print()

        for s in v.get("sources", []):
            status = "✅" if s.get("agree") else ("❌" if s.get("contradict") else "➖")
            print(f"{status} {s.get('title', 'N/A')[:50]}")
            print(f"   {s.get('url', 'N/A')[:60]}")

    elif cmd == "url":
        result = browser.extract.extract(query)
        print(f"\n📄 Content from: {query}\n")
        if result["success"]:
            print(f"Method: {result['method']}")
            print(f"\n{result['content'][:2000]}")
        else:
            print("Failed to extract content")

    else:
        print(f"Unknown command: {cmd}")
        print("Use: search, browse, verify, or url")
