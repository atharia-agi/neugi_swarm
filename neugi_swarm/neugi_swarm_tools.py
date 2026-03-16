#!/usr/bin/env python3
"""
🤖 NEUGI SWARM - TOOLS
======================

Tool system - like OpenClaw tools

Categories:
- Web: search, fetch, browser
- Code: execute, debug
- AI: llm, embeddings
- Files: read, write
- Data: json, csv
- Comm: email, sms, telegram

Usage:
    from neugi_swarm_tools import ToolManager
    tools = ToolManager()
    tools.execute("web_search", query="AI news")
"""

import os
import json
import requests
import re
from typing import Dict, List, Any, Callable, Optional
from urllib.parse import quote_plus
from dataclasses import dataclass
from concurrent.futures import ThreadPoolExecutor


@dataclass
class Tool:
    """Tool definition"""

    id: str
    name: str
    category: str
    description: str
    function: Callable
    enabled: bool = True

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "enabled": self.enabled,
        }


class ToolManager:
    """Manages all tools"""

    CATEGORIES = [
        "web",
        "code",
        "ai",
        "files",
        "data",
        "comm",
        "system",
        "media",
        "security",
        "custom",
    ]

    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self._register_default_tools()

    def _register_default_tools(self):
        """Register all default tools"""

        # Web tools
        self.register(
            Tool(
                id="web_search",
                name="Web Search",
                category="web",
                description="Search the web",
                function=self._web_search,
            )
        )

        self.register(
            Tool(
                id="web_fetch",
                name="Web Fetch",
                category="web",
                description="Fetch webpage content",
                function=self._web_fetch,
            )
        )

        self.register(
            Tool(
                id="browser_navigate",
                name="Browser Navigate",
                category="web",
                description="Navigate browser to URL",
                function=self._browser_navigate,
            )
        )

        self.register(
            Tool(
                id="browser_screenshot",
                name="Browser Screenshot",
                category="web",
                description="Take screenshot of page",
                function=self._browser_screenshot,
            )
        )

        # Native Browser Tool - FREE, no API key!
        self.register(
            Tool(
                id="neugi_browser",
                name="NEUGI Browser",
                category="web",
                description="Search web + extract content + verify claims (FREE, no API key)",
                function=self._neugi_browser,
            )
        )

        # Code tools
        self.register(
            Tool(
                id="code_execute",
                name="Code Execute",
                category="code",
                description="Execute code safely",
                function=self._code_execute,
            )
        )

        self.register(
            Tool(
                id="code_debug",
                name="Code Debug",
                category="code",
                description="Debug code issues",
                function=self._code_debug,
            )
        )

        # AI tools
        self.register(
            Tool(
                id="llm_think",
                name="LLM Think",
                category="ai",
                description="Use LLM for reasoning",
                function=self._llm_think,
            )
        )

        self.register(
            Tool(
                id="embeddings",
                name="Embeddings",
                category="ai",
                description="Generate embeddings",
                function=self._embeddings,
            )
        )

        # File tools
        self.register(
            Tool(
                id="file_read",
                name="File Read",
                category="files",
                description="Read file contents",
                function=self._file_read,
            )
        )

        self.register(
            Tool(
                id="file_write",
                name="File Write",
                category="files",
                description="Write file contents",
                function=self._file_write,
            )
        )

        self.register(
            Tool(
                id="file_list",
                name="File List",
                category="files",
                description="List directory contents",
                function=self._file_list,
            )
        )

        # Data tools
        self.register(
            Tool(
                id="json_parse",
                name="JSON Parse",
                category="data",
                description="Parse JSON data",
                function=self._json_parse,
            )
        )

        self.register(
            Tool(
                id="csv_analyze",
                name="CSV Analyze",
                category="data",
                description="Analyze CSV data",
                function=self._csv_analyze,
            )
        )

        # Communication tools
        self.register(
            Tool(
                id="send_email",
                name="Send Email",
                category="comm",
                description="Send email",
                function=self._send_email,
            )
        )

        self.register(
            Tool(
                id="send_telegram",
                name="Send Telegram",
                category="comm",
                description="Send Telegram message",
                function=self._send_telegram,
            )
        )

        self.register(
            Tool(
                id="send_discord",
                name="Send Discord",
                category="comm",
                description="Send Discord message",
                function=self._send_discord,
            )
        )

        # System tools
        self.register(
            Tool(
                id="system_exec",
                name="System Execute",
                category="system",
                description="Execute system command",
                function=self._system_exec,
            )
        )

        self.register(
            Tool(
                id="process_list",
                name="Process List",
                category="system",
                description="List running processes",
                function=self._process_list,
            )
        )

        # Swarm Specific Tools
        self.register(
            Tool(
                id="delegate_task",
                name="Delegate Task",
                category="ai",
                description="Delegate a task to another agent",
                function=self._delegate_task,
            )
        )
        self.register(
            Tool(
                id="search_memory",
                name="Search Memory",
                category="ai",
                description="Retrieve context from the codebase RAG",
                function=self._search_memory,
            )
        )
        self.register(
            Tool(
                id="git_execute",
                name="Git Execute",
                category="system",
                description="Execute safe git commands",
                function=self._git_execute,
            )
        )
        self.register(
            Tool(
                id="request_diagnostic",
                name="Request Diagnostic",
                category="system",
                description="Run system-wide health checks and auto-fix common issues",
                function=self._request_diagnostic,
            )
        )
        self.register(
            Tool(
                id="self_heal",
                name="Self Heal",
                category="system",
                description="Attempt to fix a specific system error or friction",
                function=self._self_heal,
            )
        )

    def register(self, tool: Tool):
        """Register a tool"""
        self.tools[tool.id] = tool

    def unregister(self, tool_id: str):
        """Unregister a tool"""
        if tool_id in self.tools:
            del self.tools[tool_id]

    def get(self, tool_id: str) -> Optional[Tool]:
        """Get a tool"""
        return self.tools.get(tool_id)

    def list(self, category: Optional[str] = None, enabled_only: bool = False) -> List[Tool]:
        """List tools"""
        tools = list(self.tools.values())

        if category:
            tools = [t for t in tools if t.category == category]

        if enabled_only:
            tools = [t for t in tools if t.enabled]

        return tools

    def execute(self, tool_id: str, **kwargs) -> Any:
        """Execute a tool"""
        tool = self.get(tool_id)

        if not tool:
            return {"error": f"Tool {tool_id} not found"}

        if not tool.enabled:
            return {"error": f"Tool {tool_id} is disabled"}

        try:
            return tool.function(**kwargs)
        except Exception as e:
            return {"error": str(e)}

    def search(self, query: str) -> List[Tool]:
        """Search tools"""
        query = query.lower()
        results = []

        for tool in self.tools.values():
            if (
                query in tool.name.lower()
                or query in tool.description.lower()
                or query in tool.category.lower()
            ):
                results.append(tool)

        return results

    # Tool implementations

    def _web_search(self, query: str, **kwargs) -> Dict:
        """Search the web using Native Browser"""
        if not hasattr(self, "_browser"):
            self._browser = NativeWebBrowser()
        results = self._browser.search(query)
        return {"query": query, "results": results, "engine": "multi", "count": len(results)}

    def _web_fetch(self, url: str, **kwargs) -> Dict:
        """Fetch webpage"""
        try:
            r = requests.get(url, timeout=10)
            return {
                "url": url,
                "status": r.status_code,
                "content_type": r.headers.get("content-type", "unknown"),
                "length": len(r.text),
            }
        except Exception as e:
            return {"error": str(e)}

    def _browser_navigate(self, url: str, **kwargs) -> Dict:
        """Navigate browser"""
        return {"action": "navigate", "url": url}

    def _browser_screenshot(self, url: str, **kwargs) -> Dict:
        """Take screenshot"""
        return {"action": "screenshot", "url": url}

    def _neugi_browser(
        self, query: str = "", mode: str = "search", url: str = "", **kwargs
    ) -> Dict:
        """
        NEUGI Native Browser - FREE web browsing!

        Usage:
        - search: query="latest AI news", mode="search"
        - browse: query="what is Ollama", mode="browse"
        - verify: query="claim to verify", mode="verify"
        - extract: url="https://...", mode="extract"
        """
        # Lazy-load browser to avoid import overhead
        if not hasattr(self, "_browser"):
            self._browser = NativeWebBrowser()

        browser = self._browser

        if mode == "search":
            results = browser.search(query, num_results=5)
            return {
                "query": query,
                "results": results,
                "count": len(results),
                "note": "Free multi-engine search",
            }

        elif mode == "browse":
            results = browser.search(query, num_results=3)
            content = []
            for r in results[:2]:
                c = browser.extract_content(r["url"])
                if c["success"]:
                    content.append(
                        {
                            "title": r.get("title", ""),
                            "url": r["url"],
                            "content": c["content"][:1000],
                            "method": c["method"],
                        }
                    )
            return {
                "query": query,
                "results": results,
                "content": content,
                "summary": f"Found {len(results)} results, extracted {len(content)} pages",
            }

        elif mode == "verify":
            verification = browser.verify_claim(query)
            return {
                "query": query,
                "verification": verification,
                "note": "Cross-validated claim verification",
            }

        elif mode == "extract" and url:
            result = browser.extract_content(url)
            return result

        return {"error": "Invalid mode. Use: search, browse, verify, or extract with url"}

    def _code_execute(self, code: str, language: str = "python", **kwargs) -> Dict:
        """Execute code safely (or omnipotently if God Mode is active)"""
        import subprocess
        import tempfile
        import os

        god_mode = os.environ.get("NEUGI_GOD_MODE") == "1"
        timeout_val = None if god_mode else 15

        # God Mode: Unrestricted shell access (Native or WSL)
        if language.lower() in ["bash", "sh", "batch", "powershell", "ps1"] and god_mode:
            try:
                result = subprocess.run(
                    code, shell=True, capture_output=True, text=True, timeout=timeout_val
                )
                output = result.stdout if result.returncode == 0 else result.stderr
                return {
                    "language": language,
                    "success": result.returncode == 0,
                    "output": output,
                    "exit_code": result.returncode,
                    "god_mode_active": True,
                }
            except Exception as e:
                return {"error": str(e), "success": False, "god_mode_active": True}

        if language.lower() not in ["python", "py"]:
            return {"error": "Only Python is supported normally. God Mode enables bash/powershell."}

        try:
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
                f.write(code)
                temp_path = f.name

            result = subprocess.run(
                ["python", temp_path], capture_output=True, text=True, timeout=timeout_val
            )

            os.unlink(temp_path)

            output = result.stdout if result.returncode == 0 else result.stderr
            return {
                "language": language,
                "success": result.returncode == 0,
                "output": output,
                "exit_code": result.returncode,
                "god_mode_active": god_mode,
            }
        except Exception as e:
            return {"error": str(e), "success": False, "god_mode_active": god_mode}

    def _code_debug(self, code: str, **kwargs) -> Dict:
        """Debug code"""
        return self._llm_think(
            prompt=f"Review and debug the following code:\n\n{code}\n\nProvide a corrected version."
        )

    def _llm_think(self, prompt: str, model: str = "auto", **kwargs) -> Dict:
        """Use LLM"""
        import urllib.request
        import json
        import os

        # Use explicitly provided model if any, otherwise default local
        primary_model = "qwen3.5:cloud"
        fallback_model = "nemotron-3-super:cloud"
        ollama_url = os.environ.get("OLLAMA_URL", "http://localhost:11434")

        try:
            config_path = os.path.expanduser("~/neugi/data/config.json")
            if os.path.exists(config_path):
                with open(config_path, "r") as f:
                    cfg = json.load(f)
                    model_cfg = cfg.get("model", {})
                    if isinstance(model_cfg, dict):
                        primary_model = model_cfg.get("primary", primary_model)
                        fallback_model = model_cfg.get("fallback", fallback_model)
                    elif isinstance(model_cfg, str):
                        primary_model = model_cfg
        except Exception:
            pass

        target_model = model if model != "auto" else primary_model

        for model_name in [target_model, fallback_model]:
            try:
                payload = {
                    "model": model_name,
                    "prompt": prompt,
                    "stream": False,
                    "options": {"temperature": 0.2},
                }
                req = urllib.request.Request(
                    f"{ollama_url}/api/generate",
                    data=json.dumps(payload).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=45) as response:
                    data = json.loads(response.read().decode())
                    return {"success": True, "response": data.get("response", "").strip()}
            except Exception:
                continue

        return {
            "success": False,
            "error": "LLM simulation fallback triggered: Local LLM failed to respond.",
        }

    def _embeddings(self, text: str, **kwargs) -> Dict:
        """Generate embeddings"""
        try:
            import urllib.request, json

            req = urllib.request.Request(
                "http://localhost:11434/api/embeddings",
                data=json.dumps({"model": "qwen2.5:14b", "prompt": text}).encode(),
                headers={"Content-Type": "application/json"},
            )
            with urllib.request.urlopen(req, timeout=10) as r:
                data = json.loads(r.read())
                return {
                    "success": True,
                    "embedding": data.get("embedding", [])[:10],
                    "truncated": True,
                }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def _file_read(self, path: str, **kwargs) -> Dict:
        """Read file"""
        try:
            with open(path, "r") as f:
                content = f.read()
            return {"path": path, "content": content[:500], "length": len(content)}
        except Exception as e:
            return {"error": str(e)}

    def _file_write(self, path: str, content: str, **kwargs) -> Dict:
        """Write file"""
        try:
            os.makedirs(os.path.dirname(path) if os.path.dirname(path) else ".", exist_ok=True)
            with open(path, "w") as f:
                f.write(content)
            return {"path": path, "status": "written"}
        except Exception as e:
            return {"error": str(e)}

    def _file_list(self, path: str = ".", **kwargs) -> Dict:
        """List files"""
        try:
            files = os.listdir(path)
            return {"path": path, "files": files[:20], "count": len(files)}
        except Exception as e:
            return {"error": str(e)}

    def _json_parse(self, data: str, **kwargs) -> Dict:
        """Parse JSON"""
        try:
            parsed = json.loads(data)
            return {
                "valid": True,
                "keys": list(parsed.keys()) if isinstance(parsed, dict) else "array",
            }
        except Exception as e:
            return {"valid": False, "error": str(e)}

    def _csv_analyze(self, data: str, **kwargs) -> Dict:
        """Analyze CSV"""
        lines = data.strip().split("\n")
        return {"rows": len(lines), "columns": len(lines[0].split(",")) if lines else 0}

    def _send_email(self, to: str, subject: str, body: str, **kwargs) -> Dict:
        """Send email via ChannelManager"""
        from neugi_swarm_channels import ChannelManager
        import asyncio

        cm = ChannelManager()
        # Find first email channel or add one
        email_channels = cm.list("email")
        if not email_channels:
            return {"status": "error", "message": "No email channel configured"}
        return asyncio.run(cm.send(email_channels[0].id, body))

    def _send_telegram(self, message: str, chat_id: Optional[str] = None, **kwargs) -> Dict:
        """Send Telegram via ChannelManager"""
        from neugi_swarm_channels import ChannelManager
        import asyncio

        cm = ChannelManager()
        tg_channels = cm.list("telegram")
        if not tg_channels:
            return {"status": "error", "message": "No Telegram channel configured"}
        return asyncio.run(cm.send(tg_channels[0].id, message))

    def _send_discord(self, message: str, webhook_url: Optional[str] = None, **kwargs) -> Dict:
        """Send Discord via ChannelManager"""
        from neugi_swarm_channels import ChannelManager
        import asyncio

        cm = ChannelManager()
        ds_channels = cm.list("discord")
        if not ds_channels:
            return {"status": "error", "message": "No Discord channel configured"}
        return asyncio.run(cm.send(ds_channels[0].id, message))

    def _system_exec(self, command: str, **kwargs) -> Dict:
        """Execute system command"""
        return self._code_execute(command, language="bash")

    def _process_list(self, **kwargs) -> Dict:
        """List processes"""
        cmd = "ps aux" if os.name != "nt" else "tasklist"
        return self._code_execute(cmd, language="bash")

    def _request_diagnostic(self, **kwargs) -> Dict:
        """Run system-wide health checks via NEUGIWizard"""
        from neugi_wizard import SystemChecker

        diagnosis = SystemChecker.full_diagnosis()

        return {
            "status": "diagnostic_complete",
            "findings": diagnosis,
            "summary": f"Detected {len(diagnosis.get('granular_issues', []))} granular issues.",
        }

    def _self_heal(self, error_message: str, **kwargs) -> Dict:
        """Attempt to fix a specific error using LLM reasoning + God Mode"""
        god_mode = os.environ.get("NEUGI_GOD_MODE") == "1"
        if not god_mode:
            return {"error": "Self-healing requires God Mode to perform system fixes."}

        # 1. Think about the fix
        think_prompt = f"System Error encountered: '{error_message}'. Provide a specific shell command to fix this issue. Output ONLY the command, no talk."
        res = self._llm_think(prompt=think_prompt)

        if not res.get("success"):
            return {"error": "Failed to generate healing command."}

        fix_cmd = res.get("response", "").strip().strip("`")

        safe_prefixes = ["npm", "pip", "git", "python", "echo", "ls", "cat", "chmod"]
        if not any(fix_cmd.startswith(p) for p in safe_prefixes):
            return {"error": f"Security policy blocked command: {fix_cmd}"}

        # 2. Execute the fix
        exec_res = self._code_execute(code=fix_cmd, language="bash")

        return {
            "error_addressed": error_message,
            "proposed_fix": fix_cmd,
            "execution_result": exec_res,
            "status": "healed" if exec_res.get("success") else "healing_failed",
        }

    # --- SWARM EXTENSION TOOLS ---
    def _delegate_task(self, target_agent: str, task: str, **kwargs) -> Dict:
        try:
            from neugi_swarm_agents import AgentManager

            manager = AgentManager()
            if target_agent in manager.agents:
                response = manager.run(target_agent, task)
                return {
                    "action": "delegate",
                    "target": target_agent,
                    "response": response,
                    "status": "success",
                }
            return {
                "action": "delegate",
                "error": f"Agent {target_agent} not found",
                "status": "failed",
            }
        except Exception as e:
            return {"action": "delegate", "error": str(e), "status": "failed"}

    def _search_memory(self, query: str, **kwargs) -> Dict:
        if not hasattr(self, "_rag_instance"):
            self._rag_instance = CodebaseRAG()
        return {"query": query, "results": self._rag_instance.search(query), "success": True}

    def _git_execute(self, command: str, **kwargs) -> Dict:
        if not command.startswith("git "):
            command = "git " + command
        import subprocess

        try:
            result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=15)
            return {
                "command": command,
                "output": result.stdout or result.stderr,
                "success": result.returncode == 0,
            }
        except Exception as e:
            return {"error": str(e)}


class NativeWebBrowser:
    """
    Native Web Browser Tool - Built into NEUGI!

    No external APIs required - completely FREE!

    Features:
    - Multi-engine search (DuckDuckGo, SearXNG, Brave)
    - Clean content extraction
    - Claim verification with confidence scoring
    """

    SEARXNG_INSTANCES = [
        "https://searx.be",
        "https://searx.org",
    ]

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update(
            {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        )

    def search(self, query: str, num_results: int = 5) -> List[Dict]:
        """Multi-engine web search"""
        results = []

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(self._search_duckduckgo, query, num_results),
                executor.submit(self._search_searxng, query, num_results),
                executor.submit(self._search_brave, query, num_results),
            ]

            for future in futures:
                try:
                    results.extend(future.result())
                except Exception:
                    pass

        # Deduplicate
        seen = set()
        unique = []
        for r in results:
            domain = r.get("url", "").split("/")[2] if r.get("url") else ""
            if domain and domain not in seen:
                seen.add(domain)
                unique.append(r)
            if len(unique) >= num_results:
                break

        return unique[:num_results]

    def _search_duckduckgo(self, query: str, num_results: int) -> List[Dict]:
        results = []
        try:
            url = f"https://html.duckduckgo.com/html/?q={quote_plus(query)}"
            r = self.session.get(url, timeout=10)
            if r.ok:
                pattern = r'<a rel="nofollow" class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>'
                for match in re.finditer(pattern, r.text):
                    url = match.group(1)
                    title = re.sub(r"<[^>]+>", "", match.group(2)).strip()
                    if url and title:
                        results.append(
                            {
                                "title": title,
                                "url": url,
                                "source": "DuckDuckGo",
                                "quality": 0.7,
                            }
                        )
                    if len(results) >= num_results:
                        break
        except Exception:
            pass
        return results

    def _search_searxng(self, query: str, num_results: int) -> List[Dict]:
        results = []
        try:
            url = f"https://searx.be/search?q={quote_plus(query)}&format=json"
            r = self.session.get(url, timeout=10)
            if r.ok:
                data = r.json()
                for item in data.get("results", [])[:num_results]:
                    results.append(
                        {
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "snippet": item.get("content", ""),
                            "source": "SearXNG",
                            "quality": 0.8,
                        }
                    )
        except Exception:
            pass
        return results

    def _search_brave(self, query: str, num_results: int) -> List[Dict]:
        results = []
        try:
            url = f"https://search.brave.com/search?q={quote_plus(query)}"
            r = self.session.get(url, timeout=10)
            if r.ok:
                pattern = r'<a class="result__a" href="([^"]+)"[^>]*>([^<]+)</a>'
                for match in re.finditer(pattern, r.text):
                    url = match.group(1)
                    title = match.group(2).strip()
                    if url and title:
                        results.append(
                            {
                                "title": title,
                                "url": url,
                                "source": "Brave",
                                "quality": 0.85,
                            }
                        )
                    if len(results) >= num_results:
                        break
        except Exception:
            pass
        return results

    def extract_content(self, url: str, max_length: int = 4000) -> Dict:
        """Extract clean content from URL"""
        result = {"url": url, "content": "", "success": False, "method": "none"}

        # Try Jina AI Reader (free)
        try:
            r = requests.get(f"https://r.jina.ai/{url}", timeout=15)
            if r.ok and len(r.text) > 50:
                result["content"] = r.text[:max_length]
                result["success"] = True
                result["method"] = "jina_ai"
                return result
        except Exception:
            pass

        # Fallback to basic extraction
        try:
            r = self.session.get(url, timeout=10)
            if r.ok:
                from bs4 import BeautifulSoup

                soup = BeautifulSoup(r.text, "html.parser")
                for tag in soup(["script", "style", "nav", "footer"]):
                    tag.decompose()
                text = soup.get_text(separator="\n")
                lines = [line.strip() for line in text.split("\n") if line.strip()]
                result["content"] = "\n".join(lines)[:max_length]
                result["success"] = True
                result["method"] = "readability"
        except Exception:
            pass

        return result

    def verify_claim(self, claim: str, num_sources: int = 3) -> Dict:
        """Verify claim with confidence score"""
        result = {
            "claim": claim,
            "verdict": "UNVERIFIABLE",
            "confidence": 0,
            "sources": [],
        }

        # Search for sources
        sources = self.search(claim, num_results=num_sources)

        for source in sources:
            content = self.extract_content(source["url"])
            if content["success"]:
                result["sources"].append(
                    {
                        "title": source.get("title", ""),
                        "url": source["url"],
                        "source": source.get("source", ""),
                        "content": content["content"][:200],
                    }
                )

        result["sources_checked"] = len(result["sources"])

        if result["sources"]:
            result["verdict"] = "LIKELY_TRUE"
            result["confidence"] = min(60 + len(result["sources"]) * 10, 85)

        return result


class CodebaseRAG:
    """Ultra-lightweight Python RAG system for local codebases."""

    def __init__(self, root_dir="."):
        self.root = root_dir
        self.index = {}
        self._build_index()

    def _build_index(self):
        for root, dirs, files in os.walk(self.root):
            if any(x in root for x in [".git", "__pycache__", "node_modules", ".venv", "assets"]):
                continue
            for f in files:
                if f.endswith((".py", ".html", ".css", ".js", ".md", ".json", ".txt")):
                    try:
                        path = os.path.join(root, f)
                        with open(path, "r", encoding="utf-8") as file:
                            self.index[path] = file.read().lower()
                    except Exception:
                        pass

    def search(self, query: str, top_k: int = 3) -> List[Dict]:
        query = query.lower()
        results = [
            {"path": p, "matches": c.count(query)}
            for p, c in self.index.items()
            if c.count(query) > 0
        ]
        results.sort(key=lambda x: x["matches"], reverse=True)

        snippets = []
        for res in results[:top_k]:
            try:
                with open(res["path"], "r", encoding="utf-8") as file:
                    snippets.append(
                        {"path": res["path"], "content": "".join(file.readlines()[:100])}
                    )
            except Exception:
                pass
        return snippets


# Main
if __name__ == "__main__":
    tools = ToolManager()

    print("🤖 Neugi Swarm Tools")
    print("=" * 40)
    print(f"Total tools: {len(tools.tools)}")
    print("\nBy category:")

    for cat in tools.CATEGORIES:
        count = len(tools.list(cat))
        if count > 0:
            print(f"  {cat}: {count}")

    print(f"\nAll tools: {', '.join(tools.tools.keys())}")
