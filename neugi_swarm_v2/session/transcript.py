"""
Transcript management for session conversations.

Provides JSONL-based transcript storage with append-only writes,
line-range reading, search capabilities, export formats, and
pruning of old tool results.
"""

import json
import logging
import os
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)


class TranscriptFormat(str, Enum):
    """Export formats for transcripts."""
    JSON = "json"
    MARKDOWN = "markdown"
    PLAIN_TEXT = "plain_text"


@dataclass
class TranscriptEntry:
    """A single entry in the transcript."""
    role: str
    content: str
    timestamp: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    line_number: int = 0

    def to_json(self) -> str:
        """Serialize to a JSON line."""
        return json.dumps({
            "role": self.role,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }, ensure_ascii=False)

    @classmethod
    def from_json(cls, line: str, line_number: int = 0) -> "TranscriptEntry":
        """Deserialize from a JSON line."""
        data = json.loads(line)
        return cls(
            role=data.get("role", "unknown"),
            content=data.get("content", ""),
            timestamp=data.get("timestamp", ""),
            metadata=data.get("metadata", {}),
            line_number=line_number,
        )

    def token_estimate(self) -> int:
        """Estimate token count for this entry."""
        return max(1, len(self.content) // 4)

    def is_tool_result(self) -> bool:
        """Check if this entry is a tool result."""
        return self.role == "tool" or self.metadata.get("type") == "tool_result"

    def is_tool_call(self) -> bool:
        """Check if this entry is a tool call."""
        return self.role == "assistant" and self.metadata.get("type") == "tool_call"


class TranscriptSearch:
    """
    Search operations on a transcript.

    Provides methods to search entries by role, content, or timestamp.
    """

    def __init__(self, entries: List[TranscriptEntry]) -> None:
        self._entries = entries

    def by_role(self, role: str) -> List[TranscriptEntry]:
        """Find all entries with a specific role."""
        return [e for e in self._entries if e.role == role]

    def by_content(self, query: str, case_sensitive: bool = False) -> List[TranscriptEntry]:
        """Find entries containing the query string."""
        results = []
        search_query = query if case_sensitive else query.lower()

        for entry in self._entries:
            content = entry.content if case_sensitive else entry.content.lower()
            if search_query in content:
                results.append(entry)

        return results

    def by_timestamp(
        self,
        start: Optional[str] = None,
        end: Optional[str] = None,
    ) -> List[TranscriptEntry]:
        """Find entries within a timestamp range (ISO format)."""
        results = []
        for entry in self._entries:
            ts = entry.timestamp
            if start and ts < start:
                continue
            if end and ts > end:
                continue
            results.append(entry)
        return results

    def by_metadata(self, key: str, value: Any) -> List[TranscriptEntry]:
        """Find entries with a specific metadata key-value pair."""
        return [e for e in self._entries if e.metadata.get(key) == value]

    def tool_calls(self) -> List[TranscriptEntry]:
        """Find all tool call entries."""
        return [e for e in self._entries if e.is_tool_call()]

    def tool_results(self) -> List[TranscriptEntry]:
        """Find all tool result entries."""
        return [e for e in self._entries if e.is_tool_result()]

    def recent(self, count: int = 10) -> List[TranscriptEntry]:
        """Get the most recent entries."""
        return self._entries[-count:] if len(self._entries) > count else self._entries

    def compact(self) -> "TranscriptSearch":
        """Return a new search over compacted entries (non-tool results)."""
        non_tool = [e for e in self._entries if not e.is_tool_result()]
        return TranscriptSearch(non_tool)


class Transcript:
    """
    Append-only JSONL transcript for session conversations.

    Each line is a JSON object representing a single message entry.
    Writes are atomic with fsync for durability. Supports line-range
    reading, search, export, and pruning.

    Thread-safe for concurrent reads and writes.

    Usage:
        transcript = Transcript("session_123/transcript.jsonl")
        transcript.append("user", "Hello!")
        transcript.append("assistant", "Hi there!")
        entries = transcript.read()
        search = transcript.search()
        results = search.by_role("assistant")
    """

    def __init__(self, path: str) -> None:
        self.path = Path(path)
        self._lock = threading.Lock()
        self._path.parent.mkdir(parents=True, exist_ok=True)

        if not self.path.exists():
            self.path.touch()

    def append(
        self,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        timestamp: Optional[str] = None,
    ) -> TranscriptEntry:
        """
        Append a new entry to the transcript.

        Thread-safe append-only write with fsync for durability.

        Args:
            role: Message role (user, assistant, system, tool).
            content: Message content.
            metadata: Optional metadata dictionary.
            timestamp: Optional ISO timestamp (generated if not provided).

        Returns:
            The created TranscriptEntry.
        """
        ts = timestamp or datetime.now(timezone.utc).isoformat()
        entry = TranscriptEntry(
            role=role,
            content=content,
            timestamp=ts,
            metadata=metadata or {},
        )

        with self._lock:
            line_number = self._count_lines() + 1
            entry.line_number = line_number

            try:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(entry.to_json() + "\n")
                    f.flush()
                    os.fsync(f.fileno())
            except OSError as e:
                logger.error("Failed to append to transcript %s: %s", self.path, e)
                raise

        return entry

    def append_entry(self, entry: TranscriptEntry) -> None:
        """Append an existing TranscriptEntry to the transcript."""
        with self._lock:
            line_number = self._count_lines() + 1
            entry.line_number = line_number

            try:
                with open(self.path, "a", encoding="utf-8") as f:
                    f.write(entry.to_json() + "\n")
                    f.flush()
                    os.fsync(f.fileno())
            except OSError as e:
                logger.error("Failed to append entry to transcript %s: %s", self.path, e)
                raise

    def read(
        self,
        start_line: Optional[int] = None,
        end_line: Optional[int] = None,
    ) -> List[TranscriptEntry]:
        """
        Read entries from the transcript.

        Args:
            start_line: First line to read (1-indexed, inclusive).
            end_line: Last line to read (1-indexed, inclusive).

        Returns:
            List of TranscriptEntry objects.
        """
        with self._lock:
            entries = []
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue

                        if start_line and line_num < start_line:
                            continue
                        if end_line and line_num > end_line:
                            break

                        try:
                            entry = TranscriptEntry.from_json(line, line_num)
                            entries.append(entry)
                        except json.JSONDecodeError:
                            logger.warning(
                                "Skipping malformed line %d in %s", line_num, self.path
                            )
            except OSError as e:
                logger.error("Failed to read transcript %s: %s", self.path, e)

            return entries

    def read_tail(self, count: int = 20) -> List[TranscriptEntry]:
        """Read the last N entries from the transcript."""
        total = self.count()
        if total <= count:
            return self.read()
        return self.read(start_line=total - count + 1)

    def read_range(self, start: int, end: int) -> List[TranscriptEntry]:
        """Read entries in a specific line range (1-indexed, inclusive)."""
        return self.read(start_line=start, end_line=end)

    def count(self) -> int:
        """Count total lines in the transcript."""
        with self._lock:
            return self._count_lines()

    def _count_lines(self) -> int:
        """Count lines without holding the lock (caller must hold lock)."""
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                return sum(1 for line in f if line.strip())
        except OSError:
            return 0

    def search(self) -> TranscriptSearch:
        """Create a search object over the current transcript."""
        entries = self.read()
        return TranscriptSearch(entries)

    def iterate(self) -> Iterator[TranscriptEntry]:
        """
        Lazily iterate over transcript entries.

        Memory-efficient for large transcripts.
        """
        with self._lock:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            yield TranscriptEntry.from_json(line, line_num)
                        except json.JSONDecodeError:
                            logger.warning(
                                "Skipping malformed line %d in %s", line_num, self.path
                            )
            except OSError as e:
                logger.error("Failed to iterate transcript %s: %s", self.path, e)

    def export(self, format: TranscriptFormat = TranscriptFormat.MARKDOWN) -> str:
        """
        Export the transcript in the specified format.

        Args:
            format: Output format (JSON, MARKDOWN, PLAIN_TEXT).

        Returns:
            Formatted transcript string.
        """
        entries = self.read()

        if format == TranscriptFormat.JSON:
            return self._export_json(entries)
        elif format == TranscriptFormat.MARKDOWN:
            return self._export_markdown(entries)
        elif format == TranscriptFormat.PLAIN_TEXT:
            return self._export_plain_text(entries)
        else:
            raise ValueError(f"Unknown export format: {format}")

    def _export_json(self, entries: List[TranscriptEntry]) -> str:
        """Export as a JSON array."""
        data = [
            {
                "role": e.role,
                "content": e.content,
                "timestamp": e.timestamp,
                "metadata": e.metadata,
            }
            for e in entries
        ]
        return json.dumps(data, indent=2, ensure_ascii=False)

    def _export_markdown(self, entries: List[TranscriptEntry]) -> str:
        """Export as markdown with role headers."""
        lines = ["# Transcript\n"]

        for entry in entries:
            ts = entry.timestamp[:19] if entry.timestamp else "unknown"
            role_label = entry.role.upper()
            lines.append(f"## {role_label} ({ts})\n")
            lines.append(entry.content)
            lines.append("")

            if entry.metadata:
                meta_str = ", ".join(f"{k}={v}" for k, v in entry.metadata.items())
                lines.append(f"*Metadata: {meta_str}*\n")

        return "\n".join(lines)

    def _export_plain_text(self, entries: List[TranscriptEntry]) -> str:
        """Export as plain text with role prefixes."""
        lines = []

        for entry in entries:
            ts = entry.timestamp[:19] if entry.timestamp else ""
            prefix = f"[{entry.role.upper()}]"
            if ts:
                prefix = f"{prefix} {ts}"
            lines.append(f"{prefix}: {entry.content}")
            lines.append("")

        return "\n".join(lines)

    def prune_old_tool_results(self, keep_recent: int = 10) -> int:
        """
        Remove old tool result entries, keeping only the most recent ones.

        Tool results can be large and are often not needed after the
        conversation moves on. This prunes them while preserving the
        conversation flow.

        Args:
            keep_recent: Number of recent tool results to keep.

        Returns:
            Number of entries removed.
        """
        with self._lock:
            entries = []
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line:
                            try:
                                entries.append(TranscriptEntry.from_json(line))
                            except json.JSONDecodeError:
                                pass
            except OSError as e:
                logger.error("Failed to read transcript for pruning: %s", e)
                return 0

            tool_results = [e for e in entries if e.is_tool_result()]
            if len(tool_results) <= keep_recent:
                return 0

            to_remove = len(tool_results) - keep_recent
            removed_ids = set()

            removed_count = 0
            for entry in entries:
                if entry.is_tool_result() and removed_count < to_remove:
                    removed_ids.add(id(entry))
                    removed_count += 1

            kept = [e for e in entries if id(e) not in removed_ids]

            try:
                with open(self.path, "w", encoding="utf-8") as f:
                    for entry in kept:
                        f.write(entry.to_json() + "\n")
                    f.flush()
                    os.fsync(f.fileno())
            except OSError as e:
                logger.error("Failed to write pruned transcript: %s", e)
                return 0

            logger.info(
                "Pruned %d old tool results from %s (kept %d)",
                to_remove,
                self.path,
                keep_recent,
            )
            return to_remove

    def prune_before_line(self, line_number: int) -> int:
        """
        Remove all entries before the specified line number.

        Args:
            line_number: Line number (1-indexed) to keep from.

        Returns:
            Number of entries removed.
        """
        with self._lock:
            entries = []
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    for idx, line in enumerate(f, 1):
                        line = line.strip()
                        if line:
                            try:
                                entries.append((idx, line))
                            except json.JSONDecodeError:
                                pass
            except OSError as e:
                logger.error("Failed to read transcript for pruning: %s", e)
                return 0

            removed = sum(1 for idx, _ in entries if idx < line_number)
            if removed == 0:
                return 0

            kept_lines = [line for idx, line in entries if idx >= line_number]

            try:
                with open(self.path, "w", encoding="utf-8") as f:
                    for line in kept_lines:
                        f.write(line + "\n")
                    f.flush()
                    os.fsync(f.fileno())
            except OSError as e:
                logger.error("Failed to write pruned transcript: %s", e)
                return 0

            logger.info("Pruned %d entries before line %d from %s", removed, line_number, self.path)
            return removed

    def summarize_tool_results(self) -> Dict[str, Any]:
        """
        Generate a summary of tool results in the transcript.

        Returns:
            Dictionary with tool result statistics.
        """
        entries = self.read()
        tool_results = [e for e in entries if e.is_tool_result()]
        tool_calls = [e for e in entries if e.is_tool_call()]

        tool_names: Dict[str, int] = {}
        for entry in tool_calls:
            name = entry.metadata.get("tool_name", "unknown")
            tool_names[name] = tool_names.get(name, 0) + 1

        total_tool_content = sum(len(e.content) for e in tool_results)

        return {
            "total_tool_calls": len(tool_calls),
            "total_tool_results": len(tool_results),
            "tool_names": tool_names,
            "total_tool_content_chars": total_tool_content,
            "estimated_tool_tokens": total_tool_content // 4,
        }

    def get_last_entry(self) -> Optional[TranscriptEntry]:
        """Get the last entry in the transcript without reading all entries."""
        with self._lock:
            try:
                last_line = None
                with open(self.path, "r", encoding="utf-8") as f:
                    for line in f:
                        stripped = line.strip()
                        if stripped:
                            last_line = stripped

                if last_line:
                    return TranscriptEntry.from_json(last_line)
            except (OSError, json.JSONDecodeError) as e:
                logger.error("Failed to read last entry: %s", e)

            return None

    def clear(self) -> int:
        """
        Clear all entries from the transcript.

        Returns:
            Number of entries that were removed.
        """
        with self._lock:
            count = self._count_lines()
            try:
                with open(self.path, "w", encoding="utf-8") as f:
                    f.flush()
                    os.fsync(f.fileno())
            except OSError as e:
                logger.error("Failed to clear transcript: %s", e)
                return 0

            logger.info("Cleared %d entries from %s", count, self.path)
            return count

    def exists(self) -> bool:
        """Check if the transcript file exists."""
        return self.path.exists()

    def size_bytes(self) -> int:
        """Get the transcript file size in bytes."""
        try:
            return self.path.stat().st_size
        except OSError:
            return 0
