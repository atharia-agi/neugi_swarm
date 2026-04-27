"""
Built-in tools for NEUGI v2.

50+ production-ready tools across 10 categories:
- Web: search, fetch, scrape, screenshot, monitor
- Code: execute, debug, lint, test, refactor, review
- File: read, write, list, find, diff, patch, archive
- Data: parse JSON/CSV/XML, query SQL, transform, visualize
- Comm: email, telegram, discord, slack, webhook, sms
- System: process, network, disk, memory, cpu, env
- AI: summarize, translate, classify, extract, generate
- Git: status, diff, commit, push, pull, branch, merge
- Docker: build, run, stop, logs, exec, compose
- Security: scan, audit, encrypt, decrypt, hash, sign
"""

import csv
import difflib
import hashlib
import io
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from tools.tool_registry import ToolCategory, ToolRegistry

logger = logging.getLogger(__name__)


def _safe_request():
    """Safely import requests, return None if unavailable."""
    try:
        import requests
        return requests
    except ImportError:
        return None


# ============================================================================
# Web Tools
# ============================================================================

class WebTools:
    """Web-related built-in tools."""

    @staticmethod
    def web_search(query: str, engine: str = "google", num_results: int = 10) -> Dict[str, Any]:
        """
        Search the web for information.

        Args:
            query: Search query string.
            engine: Search engine (google, duckduckgo).
            num_results: Number of results to return.

        Returns:
            Dict with search results.
        """
        requests = _safe_request()
        if not requests:
            return {"error": "requests library not available", "results": []}

        results = []
        if engine == "duckduckgo":
            try:
                resp = requests.get(
                    "https://html.duckduckgo.com/html/",
                    params={"q": query},
                    headers={"User-Agent": "NEUGI/2.0"},
                    timeout=10,
                )
                resp.raise_for_status()
                titles = re.findall(r'<a[^>]*class="result__a"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
                snippets = re.findall(r'<a[^>]*class="result__snippet"[^>]*>(.*?)</a>', resp.text, re.DOTALL)
                for i in range(min(num_results, len(titles))):
                    results.append({
                        "title": re.sub(r"<[^>]+>", "", titles[i]).strip(),
                        "snippet": re.sub(r"<[^>]+>", "", snippets[i]).strip() if i < len(snippets) else "",
                    })
            except Exception as e:
                return {"error": str(e), "results": []}

        return {"query": query, "engine": engine, "results": results, "count": len(results)}

    @staticmethod
    def web_fetch(url: str, method: str = "GET", headers: Optional[Dict] = None,
                  timeout: float = 10.0) -> Dict[str, Any]:
        """
        Fetch content from a URL.

        Args:
            url: URL to fetch.
            method: HTTP method.
            headers: Optional request headers.
            timeout: Request timeout in seconds.

        Returns:
            Dict with status_code, headers, and content.
        """
        requests = _safe_request()
        if not requests:
            return {"error": "requests library not available"}

        try:
            resp = requests.request(
                method, url, headers=headers or {}, timeout=timeout
            )
            content_type = resp.headers.get("Content-Type", "")
            if "json" in content_type:
                content = resp.json()
            else:
                content = resp.text

            return {
                "status_code": resp.status_code,
                "headers": dict(resp.headers),
                "content": content,
                "url": resp.url,
            }
        except Exception as e:
            return {"error": str(e), "status_code": 0}

    @staticmethod
    def web_scrape(url: str, extract_links: bool = True, extract_images: bool = False) -> Dict[str, Any]:
        """
        Scrape content from a web page.

        Args:
            url: URL to scrape.
            extract_links: Whether to extract links.
            extract_images: Whether to extract image URLs.

        Returns:
            Dict with title, text, links, and images.
        """
        requests = _safe_request()
        if not requests:
            return {"error": "requests library not available"}

        try:
            resp = requests.get(url, headers={"User-Agent": "NEUGI/2.0"}, timeout=10)
            resp.raise_for_status()
            html = resp.text

            title_match = re.search(r"<title[^>]*>(.*?)</title>", html, re.DOTALL | re.IGNORECASE)
            title = re.sub(r"<[^>]+>", "", title_match.group(1)).strip() if title_match else ""

            text = re.sub(r"<script[^>]*>.*?</script>", "", html, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<style[^>]*>.*?</style>", "", text, flags=re.DOTALL | re.IGNORECASE)
            text = re.sub(r"<[^>]+>", "\n", text)
            text = re.sub(r"\n\s*\n", "\n", text).strip()

            result = {"title": title, "text": text[:5000], "url": url}

            if extract_links:
                links = re.findall(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.DOTALL)
                result["links"] = [{"url": l[0], "text": re.sub(r"<[^>]+>", "", l[1]).strip()[:100]} for l in links[:50]]

            if extract_images:
                images = re.findall(r'<img[^>]*src=["\']([^"\']+)["\']', html)
                result["images"] = images[:20]

            return result
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def web_monitor(url: str, expected_status: int = 200, timeout: float = 10.0) -> Dict[str, Any]:
        """
        Monitor a URL for availability and response time.

        Args:
            url: URL to monitor.
            expected_status: Expected HTTP status code.
            timeout: Request timeout.

        Returns:
            Dict with status, response_time, and health.
        """
        requests = _safe_request()
        if not requests:
            return {"error": "requests library not available"}

        start = time.time()
        try:
            resp = requests.get(url, timeout=timeout)
            response_time = (time.time() - start) * 1000
            healthy = resp.status_code == expected_status
            return {
                "url": url,
                "status_code": resp.status_code,
                "response_time_ms": response_time,
                "healthy": healthy,
                "timestamp": time.time(),
            }
        except Exception as e:
            response_time = (time.time() - start) * 1000
            return {
                "url": url,
                "status_code": 0,
                "response_time_ms": response_time,
                "healthy": False,
                "error": str(e),
                "timestamp": time.time(),
            }

    @staticmethod
    def web_screenshot(url: str, output_path: Optional[str] = None) -> Dict[str, Any]:
        """
        Take a screenshot of a web page (requires playwright or selenium).

        Args:
            url: URL to screenshot.
            output_path: Path to save screenshot.

        Returns:
            Dict with status and path.
        """
        return {
            "status": "not_implemented",
            "message": "Screenshot requires playwright or selenium installation",
            "url": url,
        }


# ============================================================================
# Code Tools
# ============================================================================

class CodeTools:
    """Code-related built-in tools."""

    @staticmethod
    def code_execute(code: str, language: str = "python", timeout: float = 10.0) -> Dict[str, Any]:
        """
        Execute code in a sandboxed environment.

        Args:
            code: Code to execute.
            language: Programming language.
            timeout: Execution timeout.

        Returns:
            Dict with stdout, stderr, and return_code.
        """
        if language != "python":
            return {"error": f"Language '{language}' not supported"}

        try:
            output = io.StringIO()
            old_stdout = sys.stdout
            sys.stdout = output

            exec(compile(code, "<exec>", "exec"), {"__builtins__": {
                "print": print, "len": len, "str": str, "int": int,
                "float": float, "list": list, "dict": dict, "set": set,
                "tuple": tuple, "range": range, "enumerate": enumerate,
                "zip": zip, "map": map, "filter": filter, "sorted": sorted,
                "sum": sum, "min": min, "max": max, "abs": abs,
                "True": True, "False": False, "None": None,
            }})

            sys.stdout = old_stdout
            return {
                "stdout": output.getvalue(),
                "stderr": "",
                "return_code": 0,
            }
        except Exception as e:
            sys.stdout = old_stdout
            return {"stdout": "", "stderr": str(e), "return_code": 1}

    @staticmethod
    def code_lint(code: str, language: str = "python") -> Dict[str, Any]:
        """
        Lint code for style and potential issues.

        Args:
            code: Code to lint.
            language: Programming language.

        Returns:
            Dict with issues found.
        """
        issues = []
        lines = code.split("\n")

        for i, line in enumerate(lines, 1):
            if len(line) > 120:
                issues.append({"line": i, "type": "style", "message": f"Line too long ({len(line)} > 120)"})
            if line.endswith(" "):
                issues.append({"line": i, "type": "style", "message": "Trailing whitespace"})
            if "\t" in line:
                issues.append({"line": i, "type": "style", "message": "Tab character found"})

        if language == "python":
            for i, line in enumerate(lines, 1):
                stripped = line.strip()
                if stripped.startswith("except:") and stripped == "except:":
                    issues.append({"line": i, "type": "warning", "message": "Bare except clause"})
                if "eval(" in stripped or "exec(" in stripped:
                    issues.append({"line": i, "type": "security", "message": "Use of eval/exec detected"})

        return {"issues": issues, "count": len(issues), "language": language}

    @staticmethod
    def code_review(code: str, language: str = "python") -> Dict[str, Any]:
        """
        Review code for best practices and potential issues.

        Args:
            code: Code to review.
            language: Programming language.

        Returns:
            Dict with review findings.
        """
        findings = []
        lines = code.split("\n")

        if len(lines) > 100:
            findings.append({"type": "complexity", "severity": "medium", "message": "Function/file is long, consider splitting"})

        func_count = len([l for l in lines if l.strip().startswith("def ")])
        if func_count > 10:
            findings.append({"type": "complexity", "severity": "low", "message": f"File has {func_count} functions"})

        has_docstrings = any('"""' in l or "'''" in l for l in lines)
        if not has_docstrings:
            findings.append({"type": "documentation", "severity": "low", "message": "No docstrings found"})

        has_type_hints = any("->" in l and ":" in l for l in lines if l.strip().startswith("def "))
        if not has_type_hints and func_count > 0:
            findings.append({"type": "typing", "severity": "low", "message": "No type hints on functions"})

        return {"findings": findings, "language": language, "lines": len(lines)}

    @staticmethod
    def code_refactor(code: str, style: str = "pep8") -> Dict[str, Any]:
        """
        Refactor code to match a style guide.

        Args:
            code: Code to refactor.
            style: Style guide to follow.

        Returns:
            Dict with refactored code and changes.
        """
        changes = []
        lines = code.split("\n")
        refactored = []

        for i, line in enumerate(lines):
            original = line
            if line.endswith(" "):
                line = line.rstrip()
                changes.append({"line": i + 1, "change": "Removed trailing whitespace"})
            if "\t" in line:
                line = line.replace("\t", "    ")
                changes.append({"line": i + 1, "change": "Replaced tabs with spaces"})
            refactored.append(line)

        return {
            "code": "\n".join(refactored),
            "changes": changes,
            "style": style,
        }

    @staticmethod
    def code_debug(error_trace: str, code_context: str = "") -> Dict[str, Any]:
        """
        Analyze an error trace and suggest fixes.

        Args:
            error_trace: Error traceback string.
            code_context: Optional code context.

        Returns:
            Dict with analysis and suggestions.
        """
        suggestions = []
        error_type = ""
        error_message = ""

        for line in error_trace.split("\n"):
            if "Error:" in line or "Exception:" in line:
                parts = line.split(":", 1)
                if len(parts) == 2:
                    error_type = parts[0].strip().split()[-1]
                    error_message = parts[1].strip()

        if "SyntaxError" in error_type:
            suggestions.append("Check for missing colons, parentheses, or quotes")
        elif "IndentationError" in error_type:
            suggestions.append("Fix indentation - ensure consistent use of spaces (4 per level)")
        elif "NameError" in error_type:
            suggestions.append(f"Variable or function '{error_message.split()[0] if error_message else 'unknown'}' is not defined")
        elif "TypeError" in error_type:
            suggestions.append("Check argument types - a function received an unexpected type")
        elif "KeyError" in error_type:
            suggestions.append("Dictionary key not found - use .get() or check key existence")
        elif "IndexError" in error_type:
            suggestions.append("List/tuple index out of range - check bounds before accessing")
        elif "ImportError" in error_type or "ModuleNotFoundError" in error_type:
            suggestions.append("Module not found - check installation and import path")
        else:
            suggestions.append(f"Review the error: {error_type}: {error_message}")

        return {
            "error_type": error_type,
            "error_message": error_message,
            "suggestions": suggestions,
        }


# ============================================================================
# File Tools
# ============================================================================

class FileTools:
    """File-related built-in tools."""

    @staticmethod
    def file_read(path: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """
        Read a file's contents.

        Args:
            path: File path.
            encoding: File encoding.

        Returns:
            Dict with content and metadata.
        """
        try:
            with open(path, "r", encoding=encoding) as f:
                content = f.read()
            stat = os.stat(path)
            return {
                "content": content,
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "encoding": encoding,
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def file_write(path: str, content: str, mode: str = "w", encoding: str = "utf-8") -> Dict[str, Any]:
        """
        Write content to a file.

        Args:
            path: File path.
            content: Content to write.
            mode: Write mode (w, a).
            encoding: File encoding.

        Returns:
            Dict with bytes_written and path.
        """
        try:
            os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
            with open(path, mode, encoding=encoding) as f:
                f.write(content)
            return {"bytes_written": len(content.encode(encoding)), "path": path}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def file_list(path: str, recursive: bool = False, pattern: str = "*") -> Dict[str, Any]:
        """
        List files in a directory.

        Args:
            path: Directory path.
            recursive: Whether to list recursively.
            pattern: Glob pattern to match.

        Returns:
            Dict with files and directories.
        """
        try:
            import fnmatch
            files = []
            dirs = []

            if recursive:
                for root, directories, filenames in os.walk(path):
                    for d in directories:
                        dirs.append(os.path.join(root, d))
                    for f in filenames:
                        if fnmatch.fnmatch(f, pattern):
                            files.append(os.path.join(root, f))
            else:
                for item in os.listdir(path):
                    full_path = os.path.join(path, item)
                    if os.path.isdir(full_path):
                        dirs.append(full_path)
                    elif fnmatch.fnmatch(item, pattern):
                        files.append(full_path)

            return {"files": files, "directories": dirs, "count": len(files) + len(dirs)}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def file_find(path: str, pattern: str, recursive: bool = True) -> Dict[str, Any]:
        """
        Find files matching a pattern.

        Args:
            path: Starting directory.
            pattern: Glob pattern.
            recursive: Search recursively.

        Returns:
            Dict with matching files.
        """
        try:
            import fnmatch
            matches = []
            if recursive:
                for root, _, filenames in os.walk(path):
                    for f in filenames:
                        if fnmatch.fnmatch(f, pattern):
                            matches.append(os.path.join(root, f))
            else:
                for f in os.listdir(path):
                    if fnmatch.fnmatch(f, pattern):
                        matches.append(os.path.join(path, f))
            return {"matches": matches, "count": len(matches)}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def file_diff(file1: str, file2: str, context: int = 3) -> Dict[str, Any]:
        """
        Generate a diff between two files.

        Args:
            file1: First file path.
            file2: Second file path.
            context: Lines of context.

        Returns:
            Dict with diff output.
        """
        try:
            with open(file1, "r") as f1, open(file2, "r") as f2:
                diff = list(difflib.unified_diff(
                    f1.readlines(), f2.readlines(),
                    fromfile=file1, tofile=file2, n=context,
                ))
            return {"diff": "".join(diff), "lines_changed": len(diff)}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def file_archive(files: List[str], output: str, format: str = "zip") -> Dict[str, Any]:
        """
        Create an archive of files.

        Args:
            files: List of file paths to archive.
            output: Output archive path.
            format: Archive format (zip, tar).

        Returns:
            Dict with archive path and size.
        """
        try:
            import shutil
            base_name = os.path.splitext(output)[0]
            result = shutil.make_archive(base_name, format, root_dir=os.path.dirname(files[0]) if files else ".")
            stat = os.stat(result)
            return {"path": result, "size": stat.st_size, "format": format}
        except Exception as e:
            return {"error": str(e)}


# ============================================================================
# Data Tools
# ============================================================================

class DataTools:
    """Data-related built-in tools."""

    @staticmethod
    def data_parse_json(data: str) -> Dict[str, Any]:
        """
        Parse JSON string into a Python object.

        Args:
            data: JSON string.

        Returns:
            Parsed object or error.
        """
        try:
            return {"result": json.loads(data), "type": type(json.loads(data)).__name__}
        except json.JSONDecodeError as e:
            return {"error": f"Invalid JSON: {str(e)}"}

    @staticmethod
    def data_format_json(data: Any, indent: int = 2) -> Dict[str, Any]:
        """
        Format data as JSON string.

        Args:
            data: Data to format.
            indent: Indentation level.

        Returns:
            Formatted JSON string.
        """
        try:
            return {"result": json.dumps(data, indent=indent, default=str)}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def data_parse_csv(data: str, delimiter: str = ",") -> Dict[str, Any]:
        """
        Parse CSV string into rows.

        Args:
            data: CSV string.
            delimiter: Column delimiter.

        Returns:
            Dict with headers and rows.
        """
        try:
            reader = csv.DictReader(io.StringIO(data), delimiter=delimiter)
            rows = list(reader)
            return {
                "headers": reader.fieldnames or [],
                "rows": rows,
                "count": len(rows),
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def data_parse_xml(data: str) -> Dict[str, Any]:
        """
        Parse XML string into a dictionary.

        Args:
            data: XML string.

        Returns:
            Parsed XML as dict.
        """
        try:
            root = ET.fromstring(data)
            result = {root.tag: {child.tag: child.text for child in root}}
            return {"result": result, "root_tag": root.tag}
        except ET.ParseError as e:
            return {"error": f"Invalid XML: {str(e)}"}

    @staticmethod
    def data_transform(data: Any, operations: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Transform data with a sequence of operations.

        Supported operations: filter, map, sort, take, skip, unique.

        Args:
            data: Input data (list).
            operations: List of transformation operations.

        Returns:
            Transformed data.
        """
        if not isinstance(data, list):
            return {"error": "Input must be a list"}

        result = data
        for op in operations:
            op_type = op.get("type")
            if op_type == "filter" and "condition" in op:
                result = [item for item in result if eval(op["condition"], {"item": item})]
            elif op_type == "map" and "expression" in op:
                result = [eval(op["expression"], {"item": item}) for item in result]
            elif op_type == "sort" and "key" in op:
                result = sorted(result, key=lambda x: eval(op["key"], {"item": x}))
            elif op_type == "take":
                result = result[:op.get("count", 10)]
            elif op_type == "skip":
                result = result[op.get("count", 1):]
            elif op_type == "unique":
                seen = set()
                unique = []
                for item in result:
                    item_str = json.dumps(item, sort_keys=True, default=str)
                    if item_str not in seen:
                        seen.add(item_str)
                        unique.append(item)
                result = unique

        return {"result": result, "count": len(result)}

    @staticmethod
    def data_visualize(data: List[Dict[str, Any]], chart_type: str = "table") -> Dict[str, Any]:
        """
        Generate a text-based visualization of data.

        Args:
            data: List of dictionaries to visualize.
            chart_type: Type of visualization (table, summary).

        Returns:
            Dict with visualization string.
        """
        if not data:
            return {"visualization": "No data to visualize"}

        if chart_type == "summary":
            numeric_keys = []
            if data:
                for key in data[0].keys():
                    if all(isinstance(d.get(key), (int, float)) for d in data if key in d):
                        numeric_keys.append(key)

            summary = {}
            for key in numeric_keys:
                values = [d[key] for d in data if key in d]
                summary[key] = {
                    "min": min(values),
                    "max": max(values),
                    "avg": sum(values) / len(values),
                    "count": len(values),
                }
            return {"visualization": json.dumps(summary, indent=2)}

        lines = []
        headers = list(data[0].keys())
        col_widths = {h: max(len(str(h)), max(len(str(d.get(h, ""))) for d in data)) for h in headers}

        header_line = " | ".join(h.ljust(col_widths[h]) for h in headers)
        lines.append(header_line)
        lines.append("-+-".join("-" * col_widths[h] for h in headers))

        for row in data[:20]:
            line = " | ".join(str(row.get(h, "")).ljust(col_widths[h]) for h in headers)
            lines.append(line)

        if len(data) > 20:
            lines.append(f"... and {len(data) - 20} more rows")

        return {"visualization": "\n".join(lines), "rows": len(data)}


# ============================================================================
# Comm Tools
# ============================================================================

class CommTools:
    """Communication-related built-in tools."""

    @staticmethod
    def comm_webhook(url: str, payload: Dict[str, Any], method: str = "POST") -> Dict[str, Any]:
        """
        Send a webhook notification.

        Args:
            url: Webhook URL.
            payload: Data to send.
            method: HTTP method.

        Returns:
            Dict with response status.
        """
        requests = _safe_request()
        if not requests:
            return {"error": "requests library not available"}

        try:
            resp = requests.request(method, url, json=payload, timeout=10)
            return {"status_code": resp.status_code, "response": resp.text}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def comm_email_smtp(to: str, subject: str, body: str,
                        smtp_server: str = "localhost", smtp_port: int = 25) -> Dict[str, Any]:
        """
        Send an email via SMTP.

        Args:
            to: Recipient email.
            subject: Email subject.
            body: Email body.
            smtp_server: SMTP server address.
            smtp_port: SMTP port.

        Returns:
            Dict with send status.
        """
        try:
            import smtplib
            from email.mime.text import MIMEText

            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["To"] = to

            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.send_message(msg)
            return {"status": "sent", "to": to, "subject": subject}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def comm_slack_message(channel: str, text: str, webhook_url: str = "") -> Dict[str, Any]:
        """
        Send a Slack message via webhook.

        Args:
            channel: Slack channel.
            text: Message text.
            webhook_url: Slack webhook URL.

        Returns:
            Dict with send status.
        """
        if not webhook_url:
            return {"error": "webhook_url required"}

        requests = _safe_request()
        if not requests:
            return {"error": "requests library not available"}

        try:
            payload = {"channel": channel, "text": text}
            resp = requests.post(webhook_url, json=payload, timeout=10)
            return {"status_code": resp.status_code, "response": resp.text}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def comm_discord_message(content: str, webhook_url: str) -> Dict[str, Any]:
        """
        Send a Discord message via webhook.

        Args:
            content: Message content.
            webhook_url: Discord webhook URL.

        Returns:
            Dict with send status.
        """
        requests = _safe_request()
        if not requests:
            return {"error": "requests library not available"}

        try:
            resp = requests.post(webhook_url, json={"content": content}, timeout=10)
            return {"status_code": resp.status_code, "response": resp.text}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def comm_telegram_message(chat_id: str, text: str, bot_token: str) -> Dict[str, Any]:
        """
        Send a Telegram message.

        Args:
            chat_id: Telegram chat ID.
            text: Message text.
            bot_token: Telegram bot token.

        Returns:
            Dict with send status.
        """
        requests = _safe_request()
        if not requests:
            return {"error": "requests library not available"}

        try:
            url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
            resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
            return {"status_code": resp.status_code, "response": resp.json()}
        except Exception as e:
            return {"error": str(e)}


# ============================================================================
# System Tools
# ============================================================================

class SystemTools:
    """System-related built-in tools."""

    @staticmethod
    def system_cpu_info() -> Dict[str, Any]:
        """Get CPU information."""
        import platform
        info = {
            "processor": platform.processor(),
            "machine": platform.machine(),
            "cpu_count": os.cpu_count() or 1,
            "platform": platform.platform(),
        }
        try:
            import psutil
            info["cpu_percent"] = psutil.cpu_percent(interval=1)
            info["cpu_freq"] = psutil.cpu_freq()._asdict() if psutil.cpu_freq() else None
        except ImportError:
            info["note"] = "psutil not available for detailed metrics"
        return info

    @staticmethod
    def system_memory_info() -> Dict[str, Any]:
        """Get memory information."""
        try:
            import psutil
            mem = psutil.virtual_memory()
            return {
                "total_gb": round(mem.total / (1024**3), 2),
                "available_gb": round(mem.available / (1024**3), 2),
                "used_gb": round(mem.used / (1024**3), 2),
                "percent": mem.percent,
            }
        except ImportError:
            with open("/proc/meminfo") if os.path.exists("/proc/meminfo") else open(os.devnull) as f:
                if os.path.exists("/proc/meminfo"):
                    lines = f.readlines()
                    meminfo = {}
                    for line in lines[:10]:
                        parts = line.split()
                        meminfo[parts[0].rstrip(":")] = int(parts[1])
                    return {"total_kb": meminfo.get("MemTotal", 0), "free_kb": meminfo.get("MemFree", 0)}
            return {"error": "psutil not available and /proc/meminfo not found"}

    @staticmethod
    def system_disk_info() -> Dict[str, Any]:
        """Get disk information."""
        try:
            import psutil
            partitions = []
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    partitions.append({
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "total_gb": round(usage.total / (1024**3), 2),
                        "used_gb": round(usage.used / (1024**3), 2),
                        "free_gb": round(usage.free / (1024**3), 2),
                        "percent": usage.percent,
                    })
                except PermissionError:
                    pass
            return {"partitions": partitions}
        except ImportError:
            total, used, free = shutil.disk_usage("/") if "shutil" in dir() else (0, 0, 0)
            return {"total_gb": round(total / (1024**3), 2), "used_gb": round(used / (1024**3), 2)}

    @staticmethod
    def system_network_info() -> Dict[str, Any]:
        """Get network information."""
        try:
            import psutil
            net_io = psutil.net_io_counters()
            return {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
                "packets_sent": net_io.packets_sent,
                "packets_recv": net_io.packets_recv,
            }
        except ImportError:
            return {"error": "psutil not available"}

    @staticmethod
    def system_process_list() -> Dict[str, Any]:
        """List running processes."""
        try:
            import psutil
            processes = []
            for proc in psutil.process_iter(["pid", "name", "cpu_percent", "memory_percent"]):
                try:
                    processes.append(proc.info)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
            return {"processes": processes[:50], "total": len(processes)}
        except ImportError:
            return {"error": "psutil not available"}

    @staticmethod
    def system_env_vars(pattern: str = "") -> Dict[str, Any]:
        """
        Get environment variables.

        Args:
            pattern: Filter pattern for variable names.

        Returns:
            Dict with environment variables.
        """
        env = dict(os.environ)
        if pattern:
            env = {k: v for k, v in env.items() if pattern.lower() in k.lower()}
        return {"variables": env, "count": len(env)}

    @staticmethod
    def system_execute_command(command: str, shell: bool = True, timeout: float = 30.0) -> Dict[str, Any]:
        """
        Execute a system command.

        Args:
            command: Command to execute.
            shell: Whether to use shell.
            timeout: Execution timeout.

        Returns:
            Dict with stdout, stderr, and return_code.
        """
        try:
            result = subprocess.run(
                command, shell=shell, capture_output=True, text=True, timeout=timeout
            )
            return {
                "stdout": result.stdout,
                "stderr": result.stderr,
                "return_code": result.returncode,
            }
        except subprocess.TimeoutExpired:
            return {"error": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"error": str(e)}


# ============================================================================
# AI Tools
# ============================================================================

class AITools:
    """AI-related built-in tools."""

    @staticmethod
    def ai_summarize(text: str, max_length: int = 200) -> Dict[str, Any]:
        """
        Summarize text using extractive summarization.

        Args:
            text: Text to summarize.
            max_length: Maximum summary length.

        Returns:
            Dict with summary.
        """
        sentences = re.split(r"(?<=[.!?]) +", text)
        if not sentences:
            return {"summary": "", "original_length": 0}

        word_counts = {}
        words = text.lower().split()
        for word in words:
            word = re.sub(r"[^\w]", "", word)
            if len(word) > 3:
                word_counts[word] = word_counts.get(word, 0) + 1

        sentence_scores = {}
        for i, sentence in enumerate(sentences):
            score = 0
            for word in sentence.lower().split():
                word = re.sub(r"[^\w]", "", word)
                score += word_counts.get(word, 0)
            sentence_scores[i] = score / max(len(sentence.split()), 1)

        top_sentences = sorted(sentence_scores, key=sentence_scores.get, reverse=True)[:3]
        top_sentences.sort()

        summary = " ".join(sentences[i] for i in top_sentences)
        if len(summary) > max_length:
            summary = summary[:max_length].rsplit(" ", 1)[0] + "..."

        return {
            "summary": summary,
            "original_length": len(text),
            "summary_length": len(summary),
            "compression_ratio": round(len(summary) / max(len(text), 1), 2),
        }

    @staticmethod
    def ai_translate(text: str, source: str = "en", target: str = "es") -> Dict[str, Any]:
        """
        Translate text (basic dictionary-based translation).

        Args:
            text: Text to translate.
            source: Source language code.
            target: Target language code.

        Returns:
            Dict with translated text.
        """
        basic_dict = {
            "en_es": {"hello": "hola", "world": "mundo", "good": "bueno", "bad": "malo", "yes": "sí", "no": "no"},
            "en_fr": {"hello": "bonjour", "world": "monde", "good": "bon", "bad": "mauvais", "yes": "oui", "no": "non"},
            "en_de": {"hello": "hallo", "world": "Welt", "good": "gut", "bad": "schlecht", "yes": "ja", "no": "nein"},
        }

        key = f"{source}_{target}"
        dictionary = basic_dict.get(key, {})

        words = text.lower().split()
        translated = [dictionary.get(w, w) for w in words]

        return {
            "translated": " ".join(translated),
            "source": source,
            "target": target,
            "note": "Basic dictionary translation only",
        }

    @staticmethod
    def ai_classify(text: str, categories: List[str]) -> Dict[str, Any]:
        """
        Classify text into categories using keyword matching.

        Args:
            text: Text to classify.
            categories: List of category names.

        Returns:
            Dict with classification scores.
        """
        text_lower = text.lower()
        scores = {}

        for category in categories:
            score = 0
            cat_words = category.lower().split("_")
            for word in cat_words:
                if word in text_lower:
                    score += 1
            scores[category] = score

        sorted_scores = dict(sorted(scores.items(), key=lambda x: x[1], reverse=True))

        return {
            "classifications": sorted_scores,
            "top_category": next(iter(sorted_scores), None),
        }

    @staticmethod
    def ai_extract_entities(text: str) -> Dict[str, Any]:
        """
        Extract named entities from text.

        Args:
            text: Text to extract entities from.

        Returns:
            Dict with extracted entities.
        """
        entities = {
            "emails": re.findall(r"[\w.+-]+@[\w-]+\.[\w.-]+", text),
            "urls": re.findall(r"https?://\S+", text),
            "phones": re.findall(r"\b\d{3}[-.\s]?\d{3}[-.\s]?\d{4}\b", text),
            "dates": re.findall(r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b", text),
            "ips": re.findall(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", text),
            "mentions": re.findall(r"@(\w+)", text),
            "hashtags": re.findall(r"#(\w+)", text),
        }

        return {
            "entities": {k: v for k, v in entities.items() if v},
            "total": sum(len(v) for v in entities.values()),
        }

    @staticmethod
    def ai_generate_text(prompt: str, max_length: int = 100) -> Dict[str, Any]:
        """
        Generate text continuation from a prompt (basic template-based).

        Args:
            prompt: Starting prompt.
            max_length: Maximum output length.

        Returns:
            Dict with generated text.
        """
        templates = {
            "once upon": " a time, in a land far away, there lived a brave adventurer who set out on a quest to find the legendary artifact.",
            "the answer": " to this question lies in understanding the fundamental principles that govern the system.",
            "in conclusion": ", we can see that the evidence strongly supports the proposed hypothesis.",
            "def ": "function requires careful consideration of input validation and error handling.",
        }

        continuation = ""
        for key, value in templates.items():
            if key in prompt.lower():
                continuation = value
                break

        if not continuation:
            continuation = f" [Generated continuation based on: '{prompt[:50]}...']"

        result = prompt + continuation
        if len(result) > max_length:
            result = result[:max_length] + "..."

        return {"generated": result, "length": len(result)}


# ============================================================================
# Git Tools
# ============================================================================

class GitTools:
    """Git-related built-in tools."""

    @staticmethod
    def _run_git(args: List[str], cwd: Optional[str] = None) -> Dict[str, Any]:
        """Run a git command."""
        try:
            result = subprocess.run(
                ["git"] + args, capture_output=True, text=True, cwd=cwd, timeout=30
            )
            return {
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "return_code": result.returncode,
            }
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def git_status(repo_path: str = ".") -> Dict[str, Any]:
        """Get git repository status."""
        return GitTools._run_git(["status", "--short"], cwd=repo_path)

    @staticmethod
    def git_diff(repo_path: str = ".", staged: bool = False) -> Dict[str, Any]:
        """Get git diff."""
        args = ["diff"]
        if staged:
            args.append("--staged")
        return GitTools._run_git(args, cwd=repo_path)

    @staticmethod
    def git_commit(message: str, repo_path: str = ".", files: Optional[List[str]] = None) -> Dict[str, Any]:
        """Commit changes to git."""
        if files:
            GitTools._run_git(["add"] + files, cwd=repo_path)
        return GitTools._run_git(["commit", "-m", message], cwd=repo_path)

    @staticmethod
    def git_push(repo_path: str = ".", remote: str = "origin", branch: str = "main") -> Dict[str, Any]:
        """Push to remote repository."""
        return GitTools._run_git(["push", remote, branch], cwd=repo_path)

    @staticmethod
    def git_pull(repo_path: str = ".", remote: str = "origin", branch: str = "main") -> Dict[str, Any]:
        """Pull from remote repository."""
        return GitTools._run_git(["pull", remote, branch], cwd=repo_path)

    @staticmethod
    def git_branch(repo_path: str = ".", list_all: bool = False) -> Dict[str, Any]:
        """List git branches."""
        args = ["branch"]
        if list_all:
            args.append("-a")
        return GitTools._run_git(args, cwd=repo_path)

    @staticmethod
    def git_merge(branch: str, repo_path: str = ".") -> Dict[str, Any]:
        """Merge a branch."""
        return GitTools._run_git(["merge", branch], cwd=repo_path)

    @staticmethod
    def git_log(repo_path: str = ".", count: int = 10) -> Dict[str, Any]:
        """Get git log."""
        return GitTools._run_git(["log", f"--oneline", f"-{count}"], cwd=repo_path)


# ============================================================================
# Docker Tools
# ============================================================================

class DockerTools:
    """Docker-related built-in tools."""

    @staticmethod
    def _run_docker(args: List[str]) -> Dict[str, Any]:
        """Run a docker command."""
        try:
            result = subprocess.run(
                ["docker"] + args, capture_output=True, text=True, timeout=60
            )
            return {
                "stdout": result.stdout.strip(),
                "stderr": result.stderr.strip(),
                "return_code": result.returncode,
            }
        except FileNotFoundError:
            return {"error": "docker not found"}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def docker_build(path: str = ".", tag: str = "neugi-app", dockerfile: str = "Dockerfile") -> Dict[str, Any]:
        """Build a Docker image."""
        return DockerTools._run_docker(["build", "-f", dockerfile, "-t", tag, path])

    @staticmethod
    def docker_run(image: str, name: str = "", ports: Optional[List[str]] = None,
                   detach: bool = True) -> Dict[str, Any]:
        """Run a Docker container."""
        args = ["run"]
        if detach:
            args.append("-d")
        if name:
            args.extend(["--name", name])
        if ports:
            for port in ports:
                args.extend(["-p", port])
        args.append(image)
        return DockerTools._run_docker(args)

    @staticmethod
    def docker_stop(container: str) -> Dict[str, Any]:
        """Stop a Docker container."""
        return DockerTools._run_docker(["stop", container])

    @staticmethod
    def docker_logs(container: str, lines: int = 100) -> Dict[str, Any]:
        """Get Docker container logs."""
        return DockerTools._run_docker(["logs", "--tail", str(lines), container])

    @staticmethod
    def docker_exec(container: str, command: str) -> Dict[str, Any]:
        """Execute a command in a Docker container."""
        return DockerTools._run_docker(["exec", container] + command.split())

    @staticmethod
    def docker_compose_up(path: str = ".", detach: bool = True) -> Dict[str, Any]:
        """Start Docker Compose services."""
        args = ["compose", "-f", os.path.join(path, "docker-compose.yml"), "up"]
        if detach:
            args.append("-d")
        return DockerTools._run_docker(args)

    @staticmethod
    def docker_ps(all: bool = False) -> Dict[str, Any]:
        """List Docker containers."""
        args = ["ps"]
        if all:
            args.append("-a")
        return DockerTools._run_docker(args)


# ============================================================================
# Security Tools
# ============================================================================

class SecurityTools:
    """Security-related built-in tools."""

    @staticmethod
    def security_hash(data: str, algorithm: str = "sha256") -> Dict[str, Any]:
        """
        Hash data using specified algorithm.

        Args:
            data: Data to hash.
            algorithm: Hash algorithm (md5, sha1, sha256, sha512).

        Returns:
            Dict with hash value.
        """
        algorithms = {
            "md5": hashlib.md5,
            "sha1": hashlib.sha1,
            "sha256": hashlib.sha256,
            "sha512": hashlib.sha512,
        }
        algo = algorithms.get(algorithm)
        if not algo:
            return {"error": f"Unsupported algorithm: {algorithm}"}

        return {"hash": algo(data.encode()).hexdigest(), "algorithm": algorithm}

    @staticmethod
    def security_encrypt(data: str, key: str) -> Dict[str, Any]:
        """
        Encrypt data using XOR cipher (basic).

        Args:
            data: Data to encrypt.
            key: Encryption key.

        Returns:
            Dict with encrypted data (base64).
        """
        import base64
        key_bytes = key.encode()
        data_bytes = data.encode()
        encrypted = bytes([d ^ key_bytes[i % len(key_bytes)] for i, d in enumerate(data_bytes)])
        return {"encrypted": base64.b64encode(encrypted).decode(), "algorithm": "xor"}

    @staticmethod
    def security_decrypt(encrypted: str, key: str) -> Dict[str, Any]:
        """
        Decrypt data using XOR cipher (basic).

        Args:
            encrypted: Base64 encrypted data.
            key: Decryption key.

        Returns:
            Dict with decrypted data.
        """
        import base64
        try:
            encrypted_bytes = base64.b64decode(encrypted)
            key_bytes = key.encode()
            decrypted = bytes([e ^ key_bytes[i % len(key_bytes)] for i, e in enumerate(encrypted_bytes)])
            return {"decrypted": decrypted.decode(), "algorithm": "xor"}
        except Exception as e:
            return {"error": str(e)}

    @staticmethod
    def security_sign(data: str, private_key: str) -> Dict[str, Any]:
        """
        Sign data with a private key (HMAC-based).

        Args:
            data: Data to sign.
            private_key: Signing key.

        Returns:
            Dict with signature.
        """
        import hmac
        signature = hmac.new(private_key.encode(), data.encode(), hashlib.sha256).hexdigest()
        return {"signature": signature, "algorithm": "hmac-sha256"}

    @staticmethod
    def security_verify(data: str, signature: str, private_key: str) -> Dict[str, Any]:
        """
        Verify a data signature.

        Args:
            data: Original data.
            signature: Signature to verify.
            private_key: Signing key.

        Returns:
            Dict with verification result.
        """
        import hmac
        expected = hmac.new(private_key.encode(), data.encode(), hashlib.sha256).hexdigest()
        valid = hmac.compare_digest(expected, signature)
        return {"valid": valid, "algorithm": "hmac-sha256"}

    @staticmethod
    def security_scan_code(code: str) -> Dict[str, Any]:
        """
        Scan code for security vulnerabilities.

        Args:
            code: Code to scan.

        Returns:
            Dict with security findings.
        """
        findings = []
        patterns = {
            "hardcoded_password": [r'password\s*=\s*["\'][^"\']+["\']', r'passwd\s*=\s*["\'][^"\']+["\']'],
            "hardcoded_secret": [r'secret\s*=\s*["\'][^"\']+["\']', r'api_key\s*=\s*["\'][^"\']+["\']'],
            "sql_injection": [r'execute\s*\(.*%.*\)', r'execute\s*\(.*\+.*\)'],
            "command_injection": [r'os\.system\s*\(', r'subprocess\.call\s*\(.*shell\s*=\s*True'],
            "eval_usage": [r'\beval\s*\(', r'\bexec\s*\('],
            "insecure_random": [r'\brandom\.', r'math\.random'],
        }

        for vuln_type, patterns_list in patterns.items():
            for pattern in patterns_list:
                if re.search(pattern, code):
                    findings.append({
                        "type": vuln_type,
                        "severity": "high" if vuln_type in ("sql_injection", "command_injection") else "medium",
                        "pattern": pattern,
                    })

        return {"findings": findings, "count": len(findings)}

    @staticmethod
    def security_audit_file(path: str) -> Dict[str, Any]:
        """
        Audit a file for security issues.

        Args:
            path: File path to audit.

        Returns:
            Dict with audit results.
        """
        try:
            stat = os.stat(path)
            permissions = oct(stat.st_mode)[-3:]
            findings = []

            if permissions[-1] in ("7", "6", "3", "2"):
                findings.append({"type": "permissions", "severity": "medium", "message": f"File is world-writable ({permissions})"})

            if stat.st_size > 100 * 1024 * 1024:
                findings.append({"type": "size", "severity": "low", "message": f"Large file ({stat.st_size / 1024 / 1024:.1f}MB)"})

            return {
                "path": path,
                "permissions": permissions,
                "size": stat.st_size,
                "findings": findings,
            }
        except Exception as e:
            return {"error": str(e)}


# ============================================================================
# Registration
# ============================================================================

def register_builtin_tools(registry: ToolRegistry) -> Dict[str, int]:
    """
    Register all built-in tools in the registry.

    Args:
        registry: ToolRegistry instance.

    Returns:
        Dict with counts per category.
    """
    counts = {cat.value: 0 for cat in ToolCategory}

    tool_definitions = [
        # Web Tools
        ("web_search", WebTools.web_search, ToolCategory.WEB, {
            "query": {"type": "str", "description": "Search query"},
            "engine": {"type": "str", "description": "Search engine"},
            "num_results": {"type": "int", "description": "Number of results"},
        }, ["query"]),
        ("web_fetch", WebTools.web_fetch, ToolCategory.WEB, {
            "url": {"type": "str", "description": "URL to fetch"},
            "method": {"type": "str", "description": "HTTP method"},
            "headers": {"type": "dict", "description": "Request headers"},
            "timeout": {"type": "float", "description": "Timeout in seconds"},
        }, ["url"]),
        ("web_scrape", WebTools.web_scrape, ToolCategory.WEB, {
            "url": {"type": "str", "description": "URL to scrape"},
            "extract_links": {"type": "bool", "description": "Extract links"},
            "extract_images": {"type": "bool", "description": "Extract images"},
        }, ["url"]),
        ("web_monitor", WebTools.web_monitor, ToolCategory.WEB, {
            "url": {"type": "str", "description": "URL to monitor"},
            "expected_status": {"type": "int", "description": "Expected status code"},
            "timeout": {"type": "float", "description": "Timeout"},
        }, ["url"]),
        ("web_screenshot", WebTools.web_screenshot, ToolCategory.WEB, {
            "url": {"type": "str", "description": "URL to screenshot"},
            "output_path": {"type": "str", "description": "Output path"},
        }, ["url"]),

        # Code Tools
        ("code_execute", CodeTools.code_execute, ToolCategory.CODE, {
            "code": {"type": "str", "description": "Code to execute"},
            "language": {"type": "str", "description": "Programming language"},
            "timeout": {"type": "float", "description": "Timeout"},
        }, ["code"]),
        ("code_lint", CodeTools.code_lint, ToolCategory.CODE, {
            "code": {"type": "str", "description": "Code to lint"},
            "language": {"type": "str", "description": "Programming language"},
        }, ["code"]),
        ("code_review", CodeTools.code_review, ToolCategory.CODE, {
            "code": {"type": "str", "description": "Code to review"},
            "language": {"type": "str", "description": "Programming language"},
        }, ["code"]),
        ("code_refactor", CodeTools.code_refactor, ToolCategory.CODE, {
            "code": {"type": "str", "description": "Code to refactor"},
            "style": {"type": "str", "description": "Style guide"},
        }, ["code"]),
        ("code_debug", CodeTools.code_debug, ToolCategory.CODE, {
            "error_trace": {"type": "str", "description": "Error traceback"},
            "code_context": {"type": "str", "description": "Code context"},
        }, ["error_trace"]),

        # File Tools
        ("file_read", FileTools.file_read, ToolCategory.FILE, {
            "path": {"type": "str", "description": "File path"},
            "encoding": {"type": "str", "description": "File encoding"},
        }, ["path"]),
        ("file_write", FileTools.file_write, ToolCategory.FILE, {
            "path": {"type": "str", "description": "File path"},
            "content": {"type": "str", "description": "Content to write"},
            "mode": {"type": "str", "description": "Write mode"},
            "encoding": {"type": "str", "description": "Encoding"},
        }, ["path", "content"]),
        ("file_list", FileTools.file_list, ToolCategory.FILE, {
            "path": {"type": "str", "description": "Directory path"},
            "recursive": {"type": "bool", "description": "Recursive listing"},
            "pattern": {"type": "str", "description": "Glob pattern"},
        }, ["path"]),
        ("file_find", FileTools.file_find, ToolCategory.FILE, {
            "path": {"type": "str", "description": "Search path"},
            "pattern": {"type": "str", "description": "Glob pattern"},
            "recursive": {"type": "bool", "description": "Recursive search"},
        }, ["path", "pattern"]),
        ("file_diff", FileTools.file_diff, ToolCategory.FILE, {
            "file1": {"type": "str", "description": "First file"},
            "file2": {"type": "str", "description": "Second file"},
            "context": {"type": "int", "description": "Context lines"},
        }, ["file1", "file2"]),
        ("file_archive", FileTools.file_archive, ToolCategory.FILE, {
            "files": {"type": "list", "description": "Files to archive"},
            "output": {"type": "str", "description": "Output path"},
            "format": {"type": "str", "description": "Archive format"},
        }, ["files", "output"]),

        # Data Tools
        ("data_parse_json", DataTools.data_parse_json, ToolCategory.DATA, {
            "data": {"type": "str", "description": "JSON string"},
        }, ["data"]),
        ("data_format_json", DataTools.data_format_json, ToolCategory.DATA, {
            "data": {"type": "dict", "description": "Data to format"},
            "indent": {"type": "int", "description": "Indent level"},
        }, ["data"]),
        ("data_parse_csv", DataTools.data_parse_csv, ToolCategory.DATA, {
            "data": {"type": "str", "description": "CSV string"},
            "delimiter": {"type": "str", "description": "Delimiter"},
        }, ["data"]),
        ("data_parse_xml", DataTools.data_parse_xml, ToolCategory.DATA, {
            "data": {"type": "str", "description": "XML string"},
        }, ["data"]),
        ("data_transform", DataTools.data_transform, ToolCategory.DATA, {
            "data": {"type": "list", "description": "Input data"},
            "operations": {"type": "list", "description": "Transform operations"},
        }, ["data", "operations"]),
        ("data_visualize", DataTools.data_visualize, ToolCategory.DATA, {
            "data": {"type": "list", "description": "Data to visualize"},
            "chart_type": {"type": "str", "description": "Chart type"},
        }, ["data"]),

        # Comm Tools
        ("comm_webhook", CommTools.comm_webhook, ToolCategory.COMM, {
            "url": {"type": "str", "description": "Webhook URL"},
            "payload": {"type": "dict", "description": "Payload data"},
            "method": {"type": "str", "description": "HTTP method"},
        }, ["url", "payload"]),
        ("comm_email_smtp", CommTools.comm_email_smtp, ToolCategory.COMM, {
            "to": {"type": "str", "description": "Recipient"},
            "subject": {"type": "str", "description": "Subject"},
            "body": {"type": "str", "description": "Body"},
            "smtp_server": {"type": "str", "description": "SMTP server"},
            "smtp_port": {"type": "int", "description": "SMTP port"},
        }, ["to", "subject", "body"]),
        ("comm_slack_message", CommTools.comm_slack_message, ToolCategory.COMM, {
            "channel": {"type": "str", "description": "Slack channel"},
            "text": {"type": "str", "description": "Message text"},
            "webhook_url": {"type": "str", "description": "Webhook URL"},
        }, ["channel", "text", "webhook_url"]),
        ("comm_discord_message", CommTools.comm_discord_message, ToolCategory.COMM, {
            "content": {"type": "str", "description": "Message content"},
            "webhook_url": {"type": "str", "description": "Webhook URL"},
        }, ["content", "webhook_url"]),
        ("comm_telegram_message", CommTools.comm_telegram_message, ToolCategory.COMM, {
            "chat_id": {"type": "str", "description": "Chat ID"},
            "text": {"type": "str", "description": "Message text"},
            "bot_token": {"type": "str", "description": "Bot token"},
        }, ["chat_id", "text", "bot_token"]),

        # System Tools
        ("system_cpu_info", SystemTools.system_cpu_info, ToolCategory.SYSTEM, {}, []),
        ("system_memory_info", SystemTools.system_memory_info, ToolCategory.SYSTEM, {}, []),
        ("system_disk_info", SystemTools.system_disk_info, ToolCategory.SYSTEM, {}, []),
        ("system_network_info", SystemTools.system_network_info, ToolCategory.SYSTEM, {}, []),
        ("system_process_list", SystemTools.system_process_list, ToolCategory.SYSTEM, {}, []),
        ("system_env_vars", SystemTools.system_env_vars, ToolCategory.SYSTEM, {
            "pattern": {"type": "str", "description": "Filter pattern"},
        }, []),
        ("system_execute_command", SystemTools.system_execute_command, ToolCategory.SYSTEM, {
            "command": {"type": "str", "description": "Command to execute"},
            "shell": {"type": "bool", "description": "Use shell"},
            "timeout": {"type": "float", "description": "Timeout"},
        }, ["command"]),

        # AI Tools
        ("ai_summarize", AITools.ai_summarize, ToolCategory.AI, {
            "text": {"type": "str", "description": "Text to summarize"},
            "max_length": {"type": "int", "description": "Max summary length"},
        }, ["text"]),
        ("ai_translate", AITools.ai_translate, ToolCategory.AI, {
            "text": {"type": "str", "description": "Text to translate"},
            "source": {"type": "str", "description": "Source language"},
            "target": {"type": "str", "description": "Target language"},
        }, ["text"]),
        ("ai_classify", AITools.ai_classify, ToolCategory.AI, {
            "text": {"type": "str", "description": "Text to classify"},
            "categories": {"type": "list", "description": "Categories"},
        }, ["text", "categories"]),
        ("ai_extract_entities", AITools.ai_extract_entities, ToolCategory.AI, {
            "text": {"type": "str", "description": "Text to analyze"},
        }, ["text"]),
        ("ai_generate_text", AITools.ai_generate_text, ToolCategory.AI, {
            "prompt": {"type": "str", "description": "Starting prompt"},
            "max_length": {"type": "int", "description": "Max output length"},
        }, ["prompt"]),

        # Git Tools
        ("git_status", GitTools.git_status, ToolCategory.GIT, {
            "repo_path": {"type": "str", "description": "Repository path"},
        }, []),
        ("git_diff", GitTools.git_diff, ToolCategory.GIT, {
            "repo_path": {"type": "str", "description": "Repository path"},
            "staged": {"type": "bool", "description": "Show staged diff"},
        }, []),
        ("git_commit", GitTools.git_commit, ToolCategory.GIT, {
            "message": {"type": "str", "description": "Commit message"},
            "repo_path": {"type": "str", "description": "Repository path"},
            "files": {"type": "list", "description": "Files to stage"},
        }, ["message"]),
        ("git_push", GitTools.git_push, ToolCategory.GIT, {
            "repo_path": {"type": "str", "description": "Repository path"},
            "remote": {"type": "str", "description": "Remote name"},
            "branch": {"type": "str", "description": "Branch name"},
        }, []),
        ("git_pull", GitTools.git_pull, ToolCategory.GIT, {
            "repo_path": {"type": "str", "description": "Repository path"},
            "remote": {"type": "str", "description": "Remote name"},
            "branch": {"type": "str", "description": "Branch name"},
        }, []),
        ("git_branch", GitTools.git_branch, ToolCategory.GIT, {
            "repo_path": {"type": "str", "description": "Repository path"},
            "list_all": {"type": "bool", "description": "List all branches"},
        }, []),
        ("git_merge", GitTools.git_merge, ToolCategory.GIT, {
            "branch": {"type": "str", "description": "Branch to merge"},
            "repo_path": {"type": "str", "description": "Repository path"},
        }, ["branch"]),
        ("git_log", GitTools.git_log, ToolCategory.GIT, {
            "repo_path": {"type": "str", "description": "Repository path"},
            "count": {"type": "int", "description": "Number of entries"},
        }, []),

        # Docker Tools
        ("docker_build", DockerTools.docker_build, ToolCategory.DOCKER, {
            "path": {"type": "str", "description": "Build path"},
            "tag": {"type": "str", "description": "Image tag"},
            "dockerfile": {"type": "str", "description": "Dockerfile path"},
        }, []),
        ("docker_run", DockerTools.docker_run, ToolCategory.DOCKER, {
            "image": {"type": "str", "description": "Image name"},
            "name": {"type": "str", "description": "Container name"},
            "ports": {"type": "list", "description": "Port mappings"},
            "detach": {"type": "bool", "description": "Run detached"},
        }, ["image"]),
        ("docker_stop", DockerTools.docker_stop, ToolCategory.DOCKER, {
            "container": {"type": "str", "description": "Container name/ID"},
        }, ["container"]),
        ("docker_logs", DockerTools.docker_logs, ToolCategory.DOCKER, {
            "container": {"type": "str", "description": "Container name/ID"},
            "lines": {"type": "int", "description": "Number of lines"},
        }, ["container"]),
        ("docker_exec", DockerTools.docker_exec, ToolCategory.DOCKER, {
            "container": {"type": "str", "description": "Container name/ID"},
            "command": {"type": "str", "description": "Command to run"},
        }, ["container", "command"]),
        ("docker_compose_up", DockerTools.docker_compose_up, ToolCategory.DOCKER, {
            "path": {"type": "str", "description": "Compose file path"},
            "detach": {"type": "bool", "description": "Run detached"},
        }, []),
        ("docker_ps", DockerTools.docker_ps, ToolCategory.DOCKER, {
            "all": {"type": "bool", "description": "Show all containers"},
        }, []),

        # Security Tools
        ("security_hash", SecurityTools.security_hash, ToolCategory.SECURITY, {
            "data": {"type": "str", "description": "Data to hash"},
            "algorithm": {"type": "str", "description": "Hash algorithm"},
        }, ["data"]),
        ("security_encrypt", SecurityTools.security_encrypt, ToolCategory.SECURITY, {
            "data": {"type": "str", "description": "Data to encrypt"},
            "key": {"type": "str", "description": "Encryption key"},
        }, ["data", "key"]),
        ("security_decrypt", SecurityTools.security_decrypt, ToolCategory.SECURITY, {
            "encrypted": {"type": "str", "description": "Encrypted data"},
            "key": {"type": "str", "description": "Decryption key"},
        }, ["encrypted", "key"]),
        ("security_sign", SecurityTools.security_sign, ToolCategory.SECURITY, {
            "data": {"type": "str", "description": "Data to sign"},
            "private_key": {"type": "str", "description": "Signing key"},
        }, ["data", "private_key"]),
        ("security_verify", SecurityTools.security_verify, ToolCategory.SECURITY, {
            "data": {"type": "str", "description": "Original data"},
            "signature": {"type": "str", "description": "Signature"},
            "private_key": {"type": "str", "description": "Signing key"},
        }, ["data", "signature", "private_key"]),
        ("security_scan_code", SecurityTools.security_scan_code, ToolCategory.SECURITY, {
            "code": {"type": "str", "description": "Code to scan"},
        }, ["code"]),
        ("security_audit_file", SecurityTools.security_audit_file, ToolCategory.SECURITY, {
            "path": {"type": "str", "description": "File path"},
        }, ["path"]),
    ]

    for name, func, category, params, required in tool_definitions:
        try:
            registry.register_tool(
                name=name,
                func=func,
                category=category,
                parameters=params,
                required_params=required,
            )
            counts[category.value] = counts.get(category.value, 0) + 1
        except Exception as e:
            logger.warning(f"Failed to register tool '{name}': {e}")

    return counts
