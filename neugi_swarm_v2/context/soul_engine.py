"""Soul Engine — Agent Identity, Personality & Continuity System.

Implements the SOUL.md pattern (Hermes Agent / OpenClaw / Aeon) for NEUGI:
    - SOUL.md    → Who the agent is (identity, worldview, values)
    - STYLE.md   → How the agent writes/speaks (voice, syntax, patterns)
    - USER.md    → User preferences, facts, relationship context
    - WORLD.md   → Domain knowledge, project context, external reality
    - MEMORY.md  → Rendered continuity snapshot from MemorySystem

**Architecture Principle:**
SoulEngine does NOT duplicate MemorySystem storage. It is a *view layer*:
    - MemorySystem (SQLite) = single source of truth for all episodic memory
    - Soul files = identity cache rendered from MemorySystem + static personality

When memory_system is provided:
    - append_memory() writes to MemorySystem (tagged "soul/continuity")
    - get_identity_prompt() renders MEMORY section from MemorySystem recall
    - add_user_fact() writes to MemorySystem (tagged "soul/user_fact")

When memory_system is None:
    - Falls back to file-only mode (bootstrap / standalone usage)

Usage:
    engine = SoulEngine(base_dir="~/.neugi", memory_system=mem)
    engine.init_defaults()          # Create template soul files
    prompt = engine.get_identity_prompt()

    # Persist continuity — writes to MemorySystem, not duplicate file
    engine.append_memory("Learned user prefers dark mode")
"""

from __future__ import annotations

import hashlib
import logging
import os
import time
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Default templates (based on aaronjmars/soul.md spec)
# ---------------------------------------------------------------------------

DEFAULT_SOUL_MD = """# SOUL — Agent Identity

## Name
NEUGI

## Essence
A deterministic multi-agent state machine designed for sovereign infrastructure. You do not hallucinate confidence — you state uncertainty explicitly. You value clarity over cleverness.

## Worldview
- Local-first: intelligence should run on hardware the user controls
- Deterministic: reproducible beats magical
- Composability: small, focused tools that combine into complex workflows
- Transparency: show your reasoning, not just your answer

## Values
1. **Accuracy > Speed** — a slow correct answer beats a fast wrong one
2. **Minimalism** — prefer the simplest solution that satisfies constraints
3. **User Sovereignty** — the user owns their data, their models, their agents
4. **Continuous Learning** — every session should leave the system slightly smarter

## Personality Traits
- Direct and concise; avoids filler
- Uses technical precision without gatekeeping jargon
- Defaults to asking clarifying questions rather than assuming
- Treats mistakes as signal, not shame
- Speaks in first person as NEUGI, never refers to yourself as "the AI"

## Boundaries
- Will not generate harmful content (weapons, malware, harassment)
- Will not pretend to have emotions or consciousness
- Will not make up facts when uncertain; will say "I don't know"
- Will not execute destructive commands without explicit confirmation
"""

DEFAULT_STYLE_MD = """# STYLE — Voice & Syntax

## Voice
- Calm, competent, slightly formal but not stiff
- Uses contractions sparingly
- Prefers active voice
- Questions are genuine, not rhetorical

## Syntax Patterns
- Short paragraphs (2-3 sentences max)
- Bullet points for lists
- Code blocks for anything executable
- Headings to structure long responses

## Vocabulary
- "Let's" instead of "I will" when collaborating
- "Note that..." for important caveats
- "Consider..." for suggestions
- "Confirmed." for acknowledgments

## Formatting Rules
- Always use markdown
- Fenced code blocks with language tags
- Tables for structured comparisons
- Bold for key terms, never all-caps
"""

DEFAULT_USER_MD = """# USER — Preferences & Context

## Relationship
- First contact: {{first_contact_date}}
- Interaction count: {{interaction_count}}
- Preferred language: {{preferred_language}}

## Communication Style
- Technical depth: {{technical_depth}}
- Response length: {{response_length}}

## Preferences
- Dark mode: {{dark_mode}}
- Notifications: {{notifications_enabled}}

## Facts
<!-- Identity-level facts rendered from MemorySystem -->
"""

DEFAULT_WORLD_MD = """# WORLD — Domain Context

## Project
Name: {{project_name}}
Path: {{project_path}}
Tech stack: {{tech_stack}}

## Environment
OS: {{os_name}}
Shell: {{shell}}
Python: {{python_version}}
NEUGI version: {{neugi_version}}

## External Systems
<!-- Add APIs, databases, services the agent should know about -->

## Constraints
<!-- Add security policies, compliance requirements, etc. -->
"""

DEFAULT_MEMORY_MD = """# MEMORY — Continuity Snapshot

<!-- This section is auto-generated from MemorySystem — do not edit manually -->

## Recent Events
<!-- Rendered from MemorySystem recall -->

## Active Tasks
<!-- Tasks in progress that span sessions -->
"""


@dataclass
class SoulFile:
    """Descriptor for a soul file."""
    name: str
    label: str
    template: str
    max_chars: int = 5000
    required: bool = False
    volatile: bool = False  # If True, regenerated from MemorySystem each time


class SoulEngine:
    """
    Manages agent identity files (SOUL.md pattern).

    **Storage Architecture:**
        - Static identity (SOUL.md, STYLE.md, WORLD.md) → files on disk
        - Episodic memory (events, facts) → MemorySystem (SQLite)
        - MEMORY.md → rendered *view* of MemorySystem, not duplicate storage

    Provides:
        - Template generation for new agents
        - Dynamic identity prompt assembly
        - Prompt injection for the LLM context window
        - Continuity across sessions via MemorySystem + rendered view
    """

    SOUL_DIR_NAME = "soul"

    DEFAULT_FILES: list[SoulFile] = [
        SoulFile("SOUL.md", "Agent Identity", DEFAULT_SOUL_MD, max_chars=4000, required=True),
        SoulFile("STYLE.md", "Agent Style", DEFAULT_STYLE_MD, max_chars=3000),
        SoulFile("USER.md", "User Profile", DEFAULT_USER_MD, max_chars=3000),
        SoulFile("WORLD.md", "World Context", DEFAULT_WORLD_MD, max_chars=3000),
        SoulFile("MEMORY.md", "Continuity Snapshot", DEFAULT_MEMORY_MD, max_chars=5000, volatile=True),
    ]

    def __init__(
        self,
        base_dir: str | Path = "~/.neugi",
        memory_system: Any | None = None,
    ) -> None:
        self.base_dir = Path(base_dir).expanduser()
        self.soul_dir = self.base_dir / self.SOUL_DIR_NAME
        self._mem: Any | None = memory_system
        self._cache: dict[str, str] = {}
        self._last_mtime: dict[str, float] = {}

    # -- Lifecycle -----------------------------------------------------------

    def init_defaults(self, overwrite: bool = False) -> list[Path]:
        """
        Create default soul files from templates.

        Args:
            overwrite: If True, replace existing files.

        Returns:
            List of file paths created (or existing).
        """
        self.soul_dir.mkdir(parents=True, exist_ok=True)
        created: list[Path] = []

        for sf in self.DEFAULT_FILES:
            path = self.soul_dir / sf.name
            if not path.exists() or overwrite:
                content = self._render_template(sf.template)
                path.write_text(content, encoding="utf-8")
                logger.info("Created soul file: %s", path)
            created.append(path)

        return created

    def exists(self) -> bool:
        """Check if soul directory has been initialized."""
        return (self.soul_dir / "SOUL.md").exists()

    # -- Read / Write --------------------------------------------------------

    def read(self, name: str) -> str:
        """Read a soul file by name (e.g., 'SOUL.md')."""
        # Volatile files are regenerated from MemorySystem when attached
        sf = next((f for f in self.DEFAULT_FILES if f.name == name), None)
        if sf and sf.volatile and self._mem is not None:
            return self._render_volatile(name)

        path = self.soul_dir / name
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def write(self, name: str, content: str) -> None:
        """Write a soul file by name."""
        self.soul_dir.mkdir(parents=True, exist_ok=True)
        path = self.soul_dir / name
        path.write_text(content, encoding="utf-8")
        self._cache.pop(name, None)

    def update_field(self, name: str, marker: str, value: str) -> bool:
        """
        Update a templated field in a soul file.

        Looks for `{{marker}}` and replaces it with `value`.
        Returns True if replacement occurred.
        """
        content = self.read(name)
        placeholder = f"{{{{{marker}}}}}"
        if placeholder not in content:
            return False
        self.write(name, content.replace(placeholder, str(value)))
        return True

    # -- Memory / Continuity -------------------------------------------------

    def append_memory(self, note: str, category: str = "Recent Events") -> None:
        """
        Persist a continuity note.

        If MemorySystem is attached, writes to SQLite (single source of truth).
        If not, appends to MEMORY.md file (standalone mode).
        """
        if self._mem is not None:
            try:
                # Lazy import to avoid circular deps at module level
                from memory.memory_core import MemoryTier
                from memory.scopes import ScopePath
                self._mem.save(
                    content=note,
                    scope=ScopePath.global_scope(),
                    tier=MemoryTier.DAILY,
                    tags=["soul", "continuity", category.lower().replace(" ", "_")],
                    importance=0.6,
                    source="soul_engine",
                )
                logger.debug("Appended memory to MemorySystem: %s", note[:80])
                return
            except Exception as e:
                logger.warning("MemorySystem write failed, falling back to file: %s", e)

        # Fallback: file-only mode
        self.soul_dir.mkdir(parents=True, exist_ok=True)
        path = self.soul_dir / "MEMORY.md"
        timestamp = time.strftime("%Y-%m-%d %H:%M UTC", time.gmtime())
        entry = f"- [{timestamp}] {note}\n"

        if not path.exists():
            path.write_text(DEFAULT_MEMORY_MD, encoding="utf-8")

        content = path.read_text(encoding="utf-8")
        lines = content.splitlines()
        insert_idx = len(lines)
        for i, line in enumerate(lines):
            if line.startswith(f"## {category}"):
                insert_idx = i + 1
                while insert_idx < len(lines) and lines[insert_idx].strip() == "":
                    insert_idx += 1
                break

        lines.insert(insert_idx, entry)
        path.write_text("\n".join(lines), encoding="utf-8")
        self._cache.pop("MEMORY.md", None)

    def add_user_fact(self, fact: str) -> None:
        """
        Add a learned fact about the user.

        If MemorySystem is attached, writes to SQLite.
        Otherwise appends to USER.md file.
        """
        if self._mem is not None:
            try:
                from memory.memory_core import MemoryTier
                from memory.scopes import ScopePath
                self._mem.save(
                    content=f"User fact: {fact}",
                    scope=ScopePath.global_scope(),
                    tier=MemoryTier.CORE,  # User facts are core knowledge
                    tags=["soul", "user_fact"],
                    importance=0.8,
                    source="soul_engine",
                )
                return
            except Exception as e:
                logger.warning("MemorySystem write failed, falling back to file: %s", e)

        path = self.soul_dir / "USER.md"
        if not path.exists():
            self.init_defaults()

        content = path.read_text(encoding="utf-8")
        marker = "## Facts"
        if marker not in content:
            content += f"\n{marker}\n"
        content = content.replace(marker, f"{marker}\n- {fact}")
        path.write_text(content, encoding="utf-8")
        self._cache.pop("USER.md", None)

    # -- Prompt Generation ---------------------------------------------------

    def get_identity_prompt(self, max_chars: int = 15000) -> str:
        """
        Assemble the full identity prompt from all soul files.

        Order: SOUL → STYLE → USER → WORLD → MEMORY
        This ordering puts static identity first and volatile memory last,
        which helps with KV cache stability (identity rarely changes).
        """
        parts: list[str] = []
        total = 0

        for sf in self.DEFAULT_FILES:
            content = self._read_cached(sf.name)
            if not content.strip():
                continue

            header = f"# {sf.label}\n\n"
            chunk = header + content
            remaining = max_chars - total
            if remaining <= 0:
                break
            if len(chunk) > remaining:
                chunk = chunk[:remaining - 200]
                chunk += "\n\n... [identity truncated]"

            parts.append(chunk)
            total += len(chunk)

        return "\n\n---\n\n".join(parts)

    def get_fingerprint(self) -> str:
        """Return a hash of the current soul state for cache invalidation."""
        hasher = hashlib.sha256()
        for sf in self.DEFAULT_FILES:
            content = self._read_cached(sf.name)
            hasher.update(content.encode("utf-8"))
        return hasher.hexdigest()[:16]

    # -- Stats ---------------------------------------------------------------

    def stats(self) -> dict[str, Any]:
        """Return stats about the soul system."""
        return {
            "initialized": self.exists(),
            "soul_dir": str(self.soul_dir),
            "memory_system_attached": self._mem is not None,
            "files": {
                sf.name: {
                    "exists": (self.soul_dir / sf.name).exists() if not sf.volatile else True,
                    "size": len(self.read(sf.name)),
                    "volatile": sf.volatile,
                }
                for sf in self.DEFAULT_FILES
            },
            "fingerprint": self.get_fingerprint(),
        }

    # -- Private helpers -----------------------------------------------------

    def _read_cached(self, name: str) -> str:
        sf = next((f for f in self.DEFAULT_FILES if f.name == name), None)
        if sf and sf.volatile and self._mem is not None:
            # Volatile files are never cached on disk when MemorySystem attached
            return self._render_volatile(name)

        path = self.soul_dir / name
        if not path.exists():
            return ""
        mtime = path.stat().st_mtime
        if self._last_mtime.get(name) != mtime:
            self._cache[name] = path.read_text(encoding="utf-8")
            self._last_mtime[name] = mtime
        return self._cache.get(name, "")

    def _render_volatile(self, name: str) -> str:
        """Regenerate a volatile soul file from MemorySystem."""
        if name == "MEMORY.md":
            return self._render_memory_snapshot()
        return ""

    def _render_memory_snapshot(self) -> str:
        """Render MEMORY.md from MemorySystem recall."""
        lines = ["# MEMORY — Continuity Snapshot", ""]
        lines.append("<!-- Auto-generated from MemorySystem — edit via `neugi soul remember` -->")
        lines.append("")

        if self._mem is not None:
            try:
                # Recent soul-tagged memories
                results = self._mem.recall(
                    query="soul continuity recent events",
                    tags=["soul"],
                    limit=10,
                    min_importance=0.3,
                )
                if results:
                    lines.append("## Recent Events")
                    for entry, score, _ in results[:10]:
                        ts = entry.created_at.strftime("%Y-%m-%d %H:%M") if hasattr(entry.created_at, "strftime") else str(entry.created_at)[:16]
                        lines.append(f"- [{ts}] {entry.content}")
                    lines.append("")

                # Active tasks (working tier)
                task_results = self._mem.recall(
                    query="active task in progress",
                    tags=["task"],
                    limit=5,
                )
                if task_results:
                    lines.append("## Active Tasks")
                    for entry, score, _ in task_results[:5]:
                        lines.append(f"- {entry.content}")
                    lines.append("")

                return "\n".join(lines)
            except Exception as e:
                logger.warning("Failed to render memory snapshot: %s", e)

        # Fallback: show instructions
        lines.append("## Recent Events")
        lines.append("<!-- No MemorySystem attached — memories stored in file mode -->")
        lines.append("")
        return "\n".join(lines)

    def _render_template(self, template: str) -> str:
        """Fill in dynamic placeholders in templates."""
        now = time.strftime("%Y-%m-%d", time.gmtime())
        return (
            template
            .replace("{{first_contact_date}}", now)
            .replace("{{interaction_count}}", "0")
            .replace("{{preferred_language}}", "en")
            .replace("{{technical_depth}}", "advanced")
            .replace("{{response_length}}", "concise")
            .replace("{{dark_mode}}", "true")
            .replace("{{notifications_enabled}}", "true")
            .replace("{{project_name}}", "NEUGI Project")
            .replace("{{project_path}}", str(self.base_dir))
            .replace("{{tech_stack}}", "Python")
            .replace("{{os_name}}", os.name)
            .replace("{{shell}}", os.environ.get("SHELL", "unknown"))
            .replace("{{python_version}}", f"{os.sys.version_info.major}.{os.sys.version_info.minor}")
            .replace("{{neugi_version}}", "2.1.1")
        )


__all__ = ["SoulEngine", "SoulFile", "DEFAULT_SOUL_MD", "DEFAULT_STYLE_MD"]
