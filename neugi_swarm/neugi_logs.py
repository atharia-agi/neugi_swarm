#!/usr/bin/env python3
"""
🤖 NEUGI LOG AGGREGATOR
==========================

Centralized log management:
- Log collection
- Log parsing
- Search & filtering
- Log rotation

Version: 1.0
Date: March 16, 2026
"""

import os
import re
import json
import time
import uuid
import threading
from typing import Dict, List, Optional
from datetime import datetime
from collections import defaultdict, deque

NEUGI_DIR = os.path.expanduser("~/neugi")
LOGS_DIR = os.path.join(NEUGI_DIR, "logs")
os.makedirs(LOGS_DIR, exist_ok=True)


class LogEntry:
    """Log entry"""

    LEVELS = {"DEBUG": 10, "INFO": 20, "WARNING": 30, "ERROR": 40, "CRITICAL": 50}

    def __init__(
        self, message: str, level: str = "INFO", source: str = "app", metadata: Dict = None
    ):
        self.id = str(uuid.uuid4())[:12]
        self.message = message
        self.level = level.upper()
        self.source = source
        self.metadata = metadata or {}
        self.timestamp = datetime.now().isoformat()
        self.tags = []

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "message": self.message,
            "level": self.level,
            "source": self.source,
            "metadata": self.metadata,
            "timestamp": self.timestamp,
            "tags": self.tags,
        }

    @classmethod
    def from_dict(cls, data: Dict) -> "LogEntry":
        entry = cls(data["message"], data["level"], data["source"], data.get("metadata"))
        entry.id = data["id"]
        entry.timestamp = data["timestamp"]
        entry.tags = data.get("tags", [])
        return entry


class LogAggregator:
    """Centralized log aggregator"""

    def __init__(self, max_memory: int = 10000):
        self.max_memory = max_memory
        self.logs: deque = deque(maxlen=max_memory)
        self._lock = threading.RLock()
        self.sources: Dict[str, int] = defaultdict(int)
        self.levels: Dict[str, int] = defaultdict(int)

    def add_log(self, entry: LogEntry):
        """Add log entry"""
        with self._lock:
            self.logs.append(entry)
            self.sources[entry.source] += 1
            self.levels[entry.level] += 1

            self._persist_entry(entry)

    def _persist_entry(self, entry: LogEntry):
        """Persist entry to disk"""
        log_file = os.path.join(
            LOGS_DIR, f"{entry.source}_{datetime.now().strftime('%Y%m%d')}.jsonl"
        )

        with open(log_file, "a") as f:
            f.write(json.dumps(entry.to_dict()) + "\n")

    def get_logs(
        self, level: str = None, source: str = None, search: str = None, limit: int = 100
    ) -> List[Dict]:
        """Get filtered logs"""
        with self._lock:
            results = []

            for entry in reversed(self.logs):
                if level and entry.level != level.upper():
                    continue
                if source and entry.source != source:
                    continue
                if search and search.lower() not in entry.message.lower():
                    continue

                results.append(entry.to_dict())

                if len(results) >= limit:
                    break

            return results

    def get_stats(self) -> Dict:
        """Get log statistics"""
        with self._lock:
            return {
                "total": len(self.logs),
                "sources": dict(self.sources),
                "levels": dict(self.levels),
                "oldest": self.logs[0].timestamp if self.logs else None,
                "newest": self.logs[-1].timestamp if self.logs else None,
            }

    def search(self, query: str, limit: int = 100) -> List[Dict]:
        """Full-text search"""
        with self._lock:
            results = []
            query_lower = query.lower()

            for entry in reversed(self.logs):
                if (
                    query_lower in entry.message.lower()
                    or query_lower in str(entry.metadata).lower()
                ):
                    results.append(entry.to_dict())

                if len(results) >= limit:
                    break

            return results

    def clear(self, source: str = None):
        """Clear logs"""
        with self._lock:
            if source:
                self.logs = deque(
                    [l for l in self.logs if l.source != source], maxlen=self.max_memory
                )
            else:
                self.logs.clear()
            self.sources.clear()
            self.levels.clear()


class LogParser:
    """Parse various log formats"""

    @staticmethod
    def parse_syslog(line: str) -> Optional[Dict]:
        """Parse syslog format"""
        pattern = r"(\w+\s+\d+\s+\d+:\d+:\d+)\s+(\S+)\s+(\S+):\s+(.*)"
        match = re.match(pattern, line)
        if match:
            return {
                "timestamp": match.group(1),
                "host": match.group(2),
                "source": match.group(3),
                "message": match.group(4),
            }
        return None

    @staticmethod
    def parse_json(line: str) -> Optional[Dict]:
        """Parse JSON log"""
        try:
            return json.loads(line)
        except:
            return None

    @staticmethod
    def parse_apache(line: str) -> Optional[Dict]:
        """Parse Apache log format"""
        pattern = r'(\S+)\s+\S+\s+\S+\s+\[([^\]]+)\]\s+"([^"]+)"\s+(\d+)\s+(\d+)'
        match = re.match(pattern, line)
        if match:
            return {
                "ip": match.group(1),
                "timestamp": match.group(2),
                "request": match.group(3),
                "status": int(match.group(4)),
                "size": int(match.group(5)),
            }
        return None

    @staticmethod
    def parse_nginx(line: str) -> Optional[Dict]:
        """Parse Nginx log format"""
        return LogParser.parse_apache(line)


class LogWatcher:
    """Watch log files"""

    def __init__(self, aggregator: LogAggregator):
        self.aggregator = aggregator
        self.watching: Dict[str, int] = {}
        self._running = False
        self._thread = None

    def watch(self, file_path: str):
        """Start watching file"""
        if not os.path.exists(file_path):
            return

        self.watching[file_path] = 0
        self._start_watching()

    def _start_watching(self):
        """Start watching thread"""
        if self._running:
            return

        self._running = True
        self._thread = threading.Thread(target=self._watch_loop, daemon=True)
        self._thread.start()

    def _watch_loop(self):
        """Watch loop"""
        while self._running:
            for file_path, position in self.watching.items():
                if not os.path.exists(file_path):
                    continue

                try:
                    with open(file_path) as f:
                        f.seek(position)
                        new_lines = f.readlines()

                        for line in new_lines:
                            parsed = LogParser.parse_json(line.strip())
                            if not parsed:
                                parsed = LogParser.parse_syslog(line.strip())
                            if not parsed:
                                parsed = {"message": line.strip()}

                            level = "INFO"
                            if "error" in line.lower():
                                level = "ERROR"
                            elif "warn" in line.lower():
                                level = "WARNING"
                            elif "debug" in line.lower():
                                level = "DEBUG"

                            entry = LogEntry(
                                parsed.get("message", ""),
                                level,
                                os.path.basename(file_path),
                                parsed,
                            )
                            self.aggregator.add_log(entry)

                        self.watching[file_path] = f.tell()
                except:
                    pass

            time.sleep(1)

    def stop(self):
        """Stop watching"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)


log_aggregator = LogAggregator()


def log(level: str, message: str, source: str = "neugi", **metadata):
    """Convenience logging function"""
    entry = LogEntry(message, level, source, metadata)
    log_aggregator.add_log(entry)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Log Aggregator")
    parser.add_argument("--list", action="store_true", help="List recent logs")
    parser.add_argument("--level", type=str, help="Filter by level")
    parser.add_argument("--source", type=str, help="Filter by source")
    parser.add_argument("--search", type=str, help="Search logs")
    parser.add_argument("--stats", action="store_true", help="Show stats")
    parser.add_argument("--watch", type=str, help="Watch log file")
    parser.add_argument("--clear", action="store_true", help="Clear logs")

    args = parser.parse_args()

    if args.list:
        logs = log_aggregator.get_logs(args.level, args.source, args.search)
        print(f"\n📋 Logs ({len(logs)} entries):\n")
        for l in logs:
            print(
                f"  [{l['level']:<8}] {l['timestamp'][-8:]} | {l['source']:<15} | {l['message'][:60]}"
            )

    elif args.search:
        results = log_aggregator.search(args.search)
        print(f"\n🔍 Results for '{args.search}':\n")
        for r in results:
            print(f"  {r['message'][:80]}")

    elif args.stats:
        stats = log_aggregator.get_stats()
        print("\n📊 Log Statistics:")
        print(f"   Total: {stats['total']}")
        print(f"   By Level: {stats['levels']}")
        print(f"   By Source: {stats['sources']}")

    elif args.watch:
        watcher = LogWatcher(log_aggregator)
        watcher.watch(args.watch)
        print(f"Watching {args.watch}...")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            watcher.stop()

    elif args.clear:
        log_aggregator.clear()
        print("Logs cleared")

    else:
        print("NEUGI Log Aggregator")
        print("Usage: python -m neugi_logs [--list|--search QUERY|--stats|--watch FILE|--clear]")


if __name__ == "__main__":
    main()
