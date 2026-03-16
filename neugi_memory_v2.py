#!/usr/bin/env python3
"""
🤖 NEUGI TWO-TIER MEMORY SYSTEM
=================================

Based on BrowserOS memory architecture:
- Core Memory: Permanent facts (CORE.md)
- Daily Memory: Session notes (auto-expire 30 days)

Version: 1.0
Date: March 15, 2026
"""

import os
from datetime import datetime, timedelta
from typing import List, Dict


NEUGI_DIR = os.path.expanduser("~/neugi")
MEMORY_DIR = os.path.join(NEUGI_DIR, "memory")
CORE_MEMORY_FILE = os.path.join(MEMORY_DIR, "CORE.md")
DAILY_MEMORY_DIR = os.path.join(MEMORY_DIR, "daily")
CONFIG_DIR = os.path.join(NEUGI_DIR, "config")


class TwoTierMemory:
    """
    NEUGI Two-Tier Memory System

    Separates permanent facts from session notes:
    - CORE.md: Permanent facts (name, projects, preferences)
    - daily/*.md: Session notes (30-day TTL)
    """

    def __init__(self, memory_dir: str = None):
        self.memory_dir = memory_dir or MEMORY_DIR
        self.core_file = os.path.join(self.memory_dir, "CORE.md")
        self.daily_dir = os.path.join(self.memory_dir, "daily")
        self._ensure_structure()

    def _ensure_structure(self):
        """Create memory directory structure"""
        os.makedirs(self.daily_dir, exist_ok=True)

        if not os.path.exists(self.core_file):
            self._init_core_memory()

    def _init_core_memory(self):
        """Initialize CORE.md with default template"""
        default_core = """---
name: NEUGI
version: 1.0
created: {date}
---

# Core Memory

This file stores permanent facts about you and your preferences.

## About You
- Name: [Your name]
- Role: [Your role]
- Company: [Your company]

## Projects
- [Project name]: [Description]

## Preferences
- Language: [Preferred language]
- Framework: [Preferred framework]

## Tools & Tech
- [Tool/technology]: [Usage notes]

## People
- [Name]: [Relationship/context]
""".format(date=datetime.now().strftime("%Y-%m-%d"))

        with open(self.core_file, "w") as f:
            f.write(default_core)

    # ========== CORE MEMORY ==========

    def read_core(self) -> str:
        """Read entire core memory"""
        if os.path.exists(self.core_file):
            with open(self.core_file, "r") as f:
                return f.read()
        return ""

    def update_core(self, content: str):
        """Overwrite core memory"""
        with open(self.core_file, "w") as f:
            f.write(content)

    def add_core_fact(self, category: str, fact: str):
        """Add a fact to a category in core memory"""
        content = self.read_core()

        # Find or create category
        category_marker = f"## {category}"
        if category_marker not in content:
            content += f"\n\n{category_marker}\n- {fact}"
        else:
            # Add to existing category
            lines = content.split("\n")
            in_category = False
            new_lines = []

            for line in lines:
                if line.strip() == category_marker:
                    in_category = True
                elif in_category and line.startswith("## "):
                    in_category = False
                elif in_category and line.strip() and not line.startswith("-"):
                    # End of category, add fact
                    new_lines.append(f"- {fact}")

                new_lines.append(line)

            content = "\n".join(new_lines)

        self.update_core(content)

    def get_core_facts(self, category: str = None) -> Dict[str, List[str]]:
        """Get facts organized by category"""
        content = self.read_core()
        facts = {}
        current_category = None

        for line in content.split("\n"):
            if line.startswith("## "):
                current_category = line[3:].strip()
                facts[current_category] = []
            elif line.strip().startswith("- ") and current_category:
                fact = line.strip()[2:]
                facts[current_category].append(fact)

        if category:
            return {category: facts.get(category, [])}
        return facts

    # ========== DAILY MEMORY ==========

    def _get_daily_file(self, date: str = None) -> str:
        """Get daily memory file path"""
        if date is None:
            date = datetime.now().strftime("%Y-%m-%d")
        return os.path.join(self.daily_dir, f"{date}.md")

    def write_daily(self, note: str, date: str = None):
        """Add note to daily memory"""
        daily_file = self._get_daily_file(date)
        timestamp = datetime.now().strftime("%H:%M")

        content = f"- [{timestamp}] {note}\n"

        if os.path.exists(daily_file):
            with open(daily_file, "r") as f:
                existing = f.read()
                # Check if note already exists
                if note in existing:
                    return
            with open(daily_file, "a") as f:
                f.write(content)
        else:
            # Create new daily file with header
            header = f"""# Daily Memory - {date}

Notes from today's sessions:

"""
            with open(daily_file, "w") as f:
                f.write(header + content)

    def read_daily(self, date: str = None) -> str:
        """Read daily memory for a specific date"""
        daily_file = self._get_daily_file(date)
        if os.path.exists(daily_file):
            with open(daily_file, "r") as f:
                return f.read()
        return ""

    def list_daily_files(self, days: int = 30) -> List[str]:
        """List daily memory files (last N days)"""
        files = []
        for i in range(days):
            date = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
            daily_file = self._get_daily_file(date)
            if os.path.exists(daily_file):
                files.append(daily_file)
        return files

    def cleanup_old_daily(self, days: int = 30):
        """Delete daily memory older than N days"""
        cutoff = datetime.now() - timedelta(days=days)

        for filename in os.listdir(self.daily_dir):
            if filename.endswith(".md"):
                date_str = filename[:-3]
                try:
                    file_date = datetime.strptime(date_str, "%Y-%m-%d")
                    if file_date < cutoff:
                        os.remove(os.path.join(self.daily_dir, filename))
                except ValueError:
                    pass

    # ========== SEARCH ==========

    def recall(
        self, query: str, search_core: bool = True, search_daily: bool = True
    ) -> Dict[str, List[str]]:
        """
        Search both core and daily memory

        Returns:
            {"core": [...], "daily": [...], "recent": [...]}
        """
        results = {"core": [], "daily": [], "recent": []}
        query_lower = query.lower()

        # Search core memory
        if search_core:
            core_content = self.read_core()
            if query_lower in core_content.lower():
                # Extract relevant section
                results["core"] = self._extract_relevant_section(core_content, query)

        # Search daily memory
        if search_daily:
            for daily_file in self.list_daily_files(30):
                with open(daily_file, "r") as f:
                    content = f.read()
                    if query_lower in content.lower():
                        date = os.path.basename(daily_file)[:-3]
                        results["daily"].append(
                            {
                                "date": date,
                                "content": self._extract_relevant_section(content, query),
                            }
                        )

        # Recent (last 7 days) summary
        for daily_file in self.list_daily_files(7):
            with open(daily_file, "r") as f:
                content = f.read()
                date = os.path.basename(daily_file)[:-3]
                results["recent"].append({"date": date, "content": content[:500]})

        return results

    def _extract_relevant_section(self, content: str, query: str, context_lines: int = 3) -> str:
        """Extract section around the query match"""
        lines = content.split("\n")
        query_lower = query.lower()

        for i, line in enumerate(lines):
            if query_lower in line.lower():
                start = max(0, i - context_lines)
                end = min(len(lines), i + context_lines + 1)
                return "\n".join(lines[start:end])

        return content[:500]  # Return beginning if no match

    # ========== AUTO-MEMORY ==========

    def auto_remember(self, text: str):
        """
        Automatically decide where to store information

        Rules:
        - Name, job, company -> Core memory
        - Preferences, skills -> Core memory
        - Session notes, tasks -> Daily memory
        """
        text_lower = text.lower()

        # Permanent facts (core memory)
        permanent_keywords = [
            "name",
            "job",
            "role",
            "company",
            "work at",
            "preference",
            "prefer",
            "using",
            "tech stack",
        ]

        # Check if it contains permanent info
        is_permanent = any(kw in text_lower for kw in permanent_keywords)

        if is_permanent:
            # Extract category
            if any(kw in text_lower for kw in ["name", "call me"]):
                self.add_core_fact("About You", text)
            elif any(kw in text_lower for kw in ["project", "working on"]):
                self.add_core_fact("Projects", text)
            elif any(kw in text_lower for kw in ["prefer", "favorite", "use", "tech"]):
                self.add_core_fact("Preferences", text)
            else:
                self.add_core_fact("Notes", text)
        else:
            # Session note
            self.write_daily(text)

    # ========== STATS ==========

    def get_stats(self) -> Dict:
        """Get memory statistics"""
        core_size = os.path.getsize(self.core_file) if os.path.exists(self.core_file) else 0

        daily_files = self.list_daily_files(30)
        daily_count = len(daily_files)

        total_daily_size = sum(os.path.getsize(f) for f in daily_files)

        return {
            "core_size_bytes": core_size,
            "core_size_kb": round(core_size / 1024, 2),
            "daily_files_count": daily_count,
            "daily_size_kb": round(total_daily_size / 1024, 2),
            "memory_dir": self.memory_dir,
            "core_file": self.core_file,
        }


# ========== STANDALONE CLI ==========


def main():
    import argparse

    parser = argparse.ArgumentParser(description="NEUGI Memory System")
    parser.add_argument("action", choices=["read", "write", "recall", "stats", "cleanup"])
    parser.add_argument("--type", choices=["core", "daily"], default="daily")
    parser.add_argument("--date", help="Date for daily memory (YYYY-MM-DD)")
    parser.add_argument("--query", help="Search query for recall")
    parser.add_argument("--days", type=int, default=30, help="Days to keep for daily memory")

    args = parser.parse_args()

    memory = TwoTierMemory()

    if args.action == "read":
        if args.type == "core":
            print(memory.read_core())
        else:
            print(memory.read_daily(args.date))

    elif args.action == "write":
        note = input("Enter note: ")
        if args.type == "core":
            category = input("Category: ")
            memory.add_core_fact(category, note)
        else:
            memory.write_daily(note, args.date)
        print("✓ Saved")

    elif args.action == "recall":
        if not args.query:
            args.query = input("Search query: ")
        results = memory.recall(args.query)

        print("\n📚 MEMORY RECALL RESULTS")
        print("=" * 40)

        if results["core"]:
            print("\n🔶 CORE MEMORY:")
            for item in results["core"]:
                print(f"  {item}")

        if results["daily"]:
            print("\n📝 DAILY MEMORY:")
            for item in results["daily"]:
                print(f"  [{item['date']}] {item['content'][:200]}")

    elif args.action == "stats":
        stats = memory.get_stats()
        print("\n📊 MEMORY STATS")
        print("=" * 40)
        print(f"  Core Memory: {stats['core_size_kb']} KB")
        print(f"  Daily Files: {stats['daily_files_count']} (last 30 days)")
        print(f"  Daily Size: {stats['daily_size_kb']} KB")
        print(f"  Location: {stats['memory_dir']}")

    elif args.action == "cleanup":
        memory.cleanup_old_daily(args.days)
        print(f"✓ Cleaned up daily memory older than {args.days} days")


if __name__ == "__main__":
    main()
