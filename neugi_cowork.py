#!/usr/bin/env python3
"""
🤖 NEUGI COWORK
================

BrowserOS-style filesystem sandbox for NEUGI agents:
- Sandboxed file access to selected workspace
- 7 filesystem tools (read, write, edit, bash, find, grep, ls)
- Path traversal protection

Version: 1.0
Date: March 15, 2026
"""

import os
import re
import subprocess
import glob as glob_module
from typing import Dict, List, Optional, Any
from pathlib import Path


class CoworkSession:
    """
    NEUGI Cowork - Filesystem Sandbox

    Based on BrowserOS Cowork:
    - Agent sandboxed to selected folder
    - 7 filesystem tools
    - Path traversal protection
    """

    def __init__(self, workspace_dir: str):
        """
        Initialize cowork session

        Args:
            workspace_dir: Directory to sandbox agent to
        """
        self.workspace = os.path.abspath(os.path.expanduser(workspace_dir))
        self._verify_workspace()

    def _verify_workspace(self):
        """Verify workspace exists and is accessible"""
        if not os.path.exists(self.workspace):
            raise ValueError(f"Workspace does not exist: {self.workspace}")

        if not os.path.isdir(self.workspace):
            raise ValueError(f"Workspace is not a directory: {self.workspace}")

    def _resolve_path(self, path: str) -> str:
        """
        Resolve path within workspace

        Blocks path traversal attempts
        """
        # Expand user home
        path = os.path.expanduser(path)

        # Join with workspace
        full_path = os.path.join(self.workspace, path)

        # Get absolute path
        abs_path = os.path.abspath(full_path)

        # Verify it's within workspace
        if not abs_path.startswith(self.workspace):
            raise SecurityError(f"Path traversal detected: {path}")

        return abs_path

    def _verify_read(self, path: str) -> str:
        """Verify path is readable"""
        resolved = self._resolve_path(path)

        if not os.path.exists(resolved):
            raise FileNotFoundError(f"File not found: {path}")

        if not os.access(resolved, os.R_OK):
            raise PermissionError(f"Cannot read: {path}")

        return resolved

    def _verify_write(self, path: str) -> str:
        """Verify path is writable"""
        resolved = self._resolve_path(path)

        # Check parent directory exists or can be created
        parent = os.path.dirname(resolved)
        if not os.path.exists(parent):
            try:
                os.makedirs(parent, exist_ok=True)
            except Exception as e:
                raise PermissionError(f"Cannot create directory: {e}")

        return resolved

    # ========== FILESYSTEM TOOLS ==========

    def read(self, path: str, offset: int = 0, limit: int = 100) -> Dict[str, Any]:
        """
        Read a file with pagination

        Args:
            path: File path relative to workspace
            offset: Starting line (0-indexed)
            limit: Max lines to read

        Returns:
            {"content": str, "total_lines": int, "showing": str}
        """
        try:
            resolved = self._verify_read(path)

            with open(resolved, "r", encoding="utf-8") as f:
                lines = f.readlines()

            total = len(lines)
            start = max(0, offset)
            end = min(total, start + limit)

            content = "".join(lines[start:end])

            return {
                "content": content,
                "total_lines": total,
                "showing": f"{start + 1}-{end}",
                "path": path,
            }

        except SecurityError:
            raise
        except FileNotFoundError:
            raise
        except Exception as e:
            return {"error": str(e)}

    def write(self, path: str, content: str) -> Dict[str, Any]:
        """
        Create or overwrite a file

        Args:
            path: File path relative to workspace
            content: File content

        Returns:
            {"status": "success", "path": str}
        """
        try:
            resolved = self._verify_write(path)

            with open(resolved, "w", encoding="utf-8") as f:
                f.write(content)

            return {"status": "success", "path": path}

        except SecurityError:
            raise
        except Exception as e:
            return {"error": str(e)}

    def edit(self, path: str, old_string: str, new_string: str) -> Dict[str, Any]:
        """
        Edit file by string replacement

        Args:
            path: File path
            old_string: Text to find
            new_string: Replacement text

        Returns:
            {"status": "edited", "path": str}
        """
        try:
            resolved = self._verify_read(path)

            with open(resolved, "r", encoding="utf-8") as f:
                content = f.read()

            if old_string not in content:
                return {"error": "String not found in file"}

            # Try exact match first
            new_content = content.replace(old_string, new_string)

            # Check if change happened
            if new_content == content:
                return {"error": "No changes made"}

            with open(resolved, "w", encoding="utf-8") as f:
                f.write(new_content)

            return {"status": "edited", "path": path}

        except SecurityError:
            raise
        except Exception as e:
            return {"error": str(e)}

    def bash(self, command: str, timeout: int = 120) -> Dict[str, Any]:
        """
        Execute shell command in workspace

        Args:
            command: Shell command to execute
            timeout: Timeout in seconds

        Returns:
            {"stdout": str, "stderr": str, "returncode": int}
        """
        try:
            # Security: disallow certain commands
            dangerous = ["rm -rf /", "dd if=", ":(){:|:&};:", "mkfs", "fdisk"]
            for d in dangerous:
                if d in command:
                    return {"error": f"Dangerous command blocked: {d}"}

            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=self.workspace,
            )

            # Truncate output if too long
            stdout = result.stdout[-5000:] if result.stdout else ""
            stderr = result.stderr[-2000:] if result.stderr else ""

            return {"stdout": stdout, "stderr": stderr, "returncode": result.returncode}

        except subprocess.TimeoutExpired:
            return {"error": f"Command timed out after {timeout}s"}
        except Exception as e:
            return {"error": str(e)}

    def find(self, pattern: str, path: str = ".") -> Dict[str, Any]:
        """
        Find files matching glob pattern

        Args:
            pattern: Glob pattern (e.g., "*.py", "**/*.js")
            path: Directory to search

        Returns:
            {"matches": [str]}
        """
        try:
            resolved = self._resolve_path(path)

            # Build full pattern
            full_pattern = os.path.join(resolved, pattern)

            # Find matches
            matches = glob_module.glob(full_pattern, recursive=True)

            # Filter out build directories
            skip_dirs = {
                ".git",
                "__pycache__",
                "node_modules",
                ".venv",
                "dist",
                "build",
                ".next",
                "coverage",
                ".cache",
            }

            filtered = []
            for m in matches:
                # Skip if in skip directory
                if any(skip in m for skip in skip_dirs):
                    continue

                # Make relative
                rel = os.path.relpath(m, resolved)
                filtered.append(rel)

            return {"matches": sorted(filtered)[:1000]}

        except SecurityError:
            raise
        except Exception as e:
            return {"error": str(e)}

    def grep(
        self,
        pattern: str,
        path: str = ".",
        glob: str = None,
        ignore_case: bool = False,
        literal: bool = False,
        context: int = 0,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """
        Search file contents using regex

        Args:
            pattern: Search pattern
            path: Directory or file to search
            glob: Filter by glob (e.g., "*.py")
            ignore_case: Case insensitive
            literal: Treat pattern as literal string
            context: Lines of context around match
            limit: Max matches

        Returns:
            {"matches": [{"file": str, "line": int, "content": str}]}
        """
        try:
            import re

            resolved = self._resolve_path(path)

            # Compile regex
            flags = re.IGNORECASE if ignore_case else 0
            if literal:
                pattern = re.escape(pattern)

            regex = re.compile(pattern, flags)

            matches = []

            # Walk directory
            for root, dirs, files in os.walk(resolved):
                # Skip certain directories
                dirs[:] = [d for d in dirs if d not in {".git", "__pycache__", "node_modules"}]

                for filename in files:
                    # Filter by glob
                    if glob and not filename.endswith(glob.lstrip("*")):
                        continue

                    filepath = os.path.join(root, filename)

                    # Skip binary and large files
                    if os.path.getsize(filepath) > 2 * 1024 * 1024:
                        continue

                    try:
                        with open(filepath, "r", encoding="utf-8") as f:
                            lines = f.readlines()

                            for i, line in enumerate(lines):
                                if regex.search(line):
                                    rel_path = os.path.relpath(filepath, resolved)

                                    match_data = {
                                        "file": rel_path,
                                        "line": i + 1,
                                        "content": line.strip()[:200],
                                    }

                                    # Add context
                                    if context > 0:
                                        start = max(0, i - context)
                                        end = min(len(lines), i + context + 1)
                                        match_data["context"] = "".join(lines[start:end])

                                    matches.append(match_data)

                                    if len(matches) >= limit:
                                        break

                    except (UnicodeDecodeError, PermissionError):
                        continue

                    if len(matches) >= limit:
                        break

                if len(matches) >= limit:
                    break

            return {"matches": matches}

        except SecurityError:
            raise
        except Exception as e:
            return {"error": str(e)}

    def ls(self, path: str = ".", limit: int = 500) -> Dict[str, Any]:
        """
        List directory contents

        Args:
            path: Directory path
            limit: Max entries

        Returns:
            {"items": [{"name": str, "type": str, "size": int}]}
        """
        try:
            resolved = self._resolve_path(path)

            if not os.path.isdir(resolved):
                return {"error": "Not a directory"}

            items = []
            for entry in os.listdir(resolved)[:limit]:
                entry_path = os.path.join(resolved, entry)

                stat = os.stat(entry_path)

                item = {
                    "name": entry,
                    "type": "dir" if os.path.isdir(entry_path) else "file",
                    "size": stat.st_size,
                }

                items.append(item)

            # Sort: directories first, then alphabetically
            items.sort(key=lambda x: (x["type"] != "dir", x["name"].lower()))

            return {"items": items, "path": path}

        except SecurityError:
            raise
        except Exception as e:
            return {"error": str(e)}

    # ========== CONVENIENCE METHODS ==========

    def exists(self, path: str) -> bool:
        """Check if file/directory exists"""
        try:
            resolved = self._resolve_path(path)
            return os.path.exists(resolved)
        except:
            return False

    def is_dir(self, path: str) -> bool:
        """Check if path is directory"""
        try:
            resolved = self._resolve_path(path)
            return os.path.isdir(resolved)
        except:
            return False

    def get_info(self) -> Dict[str, Any]:
        """Get workspace info"""
        return {
            "workspace": self.workspace,
            "exists": os.path.exists(self.workspace),
            "is_dir": os.path.isdir(self.workspace),
        }


class SecurityError(Exception):
    """Security violation"""

    pass


# ========== STANDALONE CLI ==========


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Cowork")
    parser.add_argument(
        "action", choices=["read", "write", "edit", "bash", "find", "grep", "ls", "info"]
    )
    parser.add_argument("--path", default=".", help="File/directory path")
    parser.add_argument("--workspace", default="~/neugi/workspace", help="Workspace directory")
    parser.add_argument("--content", help="Content for write/edit")
    parser.add_argument("--old", help="Old string for edit")
    parser.add_argument("--new", help="New string for edit")
    parser.add_argument("--command", help="Command for bash")
    parser.add_argument("--pattern", help="Pattern for find/grep")
    parser.add_argument("--glob", help="Glob filter")
    parser.add_argument("--limit", type=int, default=100, help="Result limit")

    args = parser.parse_args()

    try:
        session = CoworkSession(args.workspace)

        if args.action == "read":
            result = session.read(args.path, limit=args.limit)

        elif args.action == "write":
            result = session.write(args.path, args.content or "")

        elif args.action == "edit":
            result = session.edit(args.path, args.old, args.new)

        elif args.action == "bash":
            result = session.bash(args.command or "")

        elif args.action == "find":
            result = session.find(args.pattern or "*", args.path)

        elif args.action == "grep":
            result = session.grep(args.pattern or "", args.path, args.glob, limit=args.limit)

        elif args.action == "ls":
            result = session.ls(args.path, args.limit)

        elif args.action == "info":
            result = session.get_info()

        print(json.dumps(result, indent=2))

    except SecurityError as e:
        print(json.dumps({"error": f"Security violation: {e}"}))
    except Exception as e:
        print(json.dumps({"error": str(e)}))


if __name__ == "__main__":
    import json

    main()
