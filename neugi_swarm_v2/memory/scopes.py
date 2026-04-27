"""
Memory scope management for NEUGI v2.

Provides hierarchical scope paths (like filesystem paths), scope resolution
with parent inheritance, scope-based access control, and memory slices
(read-only views across multiple disjoint scopes).

Scopes define visibility boundaries for memories:
    /swarm/           - Swarm-wide shared knowledge
    /agent/{id}/      - Per-agent private + shared memories
    /task/{id}/       - Task-scoped ephemeral context
    /user/{id}/       - User-specific preferences and history
    /global/          - Cross-cutting system knowledge
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath
from typing import Iterable, Optional


class ScopeError(Exception):
    """Base exception for scope-related errors."""
    pass


class ScopeValidationError(ScopeError):
    """Raised when a scope path is malformed."""
    pass


class ScopeAccessError(ScopeError):
    """Raised when an agent attempts to access a forbidden scope."""
    pass


class ScopeLevel(Enum):
    """Hierarchy levels for memory scopes."""
    GLOBAL = "global"
    SWARM = "swarm"
    USER = "user"
    AGENT = "agent"
    TASK = "task"


@dataclass(frozen=True)
class ScopePath:
    """
    Immutable hierarchical scope path, modelled after filesystem paths.

    Examples:
        ScopePath.from_string("/global/")
        ScopePath.from_string("/agent/cipher/")
        ScopePath.from_string("/agent/cipher/tasks/abc123")
        ScopePath(agent_id="cipher", task_id="abc123")

    Paths are always absolute, normalized, and trailing-slash-stripped
    (except root "/").
    """

    parts: tuple[str, ...] = field(default=())

    def __post_init__(self) -> None:
        # Validate each part
        for part in self.parts:
            if not part:
                raise ScopeValidationError("Empty scope part")
            if not re.match(r"^[a-zA-Z0-9_\-]+$", part):
                raise ScopeValidationError(f"Invalid scope part: {part!r}")

    # -- Factory constructors ------------------------------------------------

    @classmethod
    def root(cls) -> ScopePath:
        return cls(parts=())

    @classmethod
    def from_string(cls, path: str) -> ScopePath:
        """Parse a scope string like '/agent/cipher/tasks/abc123'."""
        if not path.startswith("/"):
            raise ScopeValidationError(f"Scope path must start with '/': {path!r}")
        # Strip leading/trailing slashes and split
        raw = path.strip("/")
        if not raw:
            return cls.root()
        parts = tuple(raw.split("/"))
        return cls(parts=parts)

    @classmethod
    def global_scope(cls) -> ScopePath:
        return cls(parts=("global",))

    @classmethod
    def swarm_scope(cls) -> ScopePath:
        return cls(parts=("swarm",))

    @classmethod
    def agent_scope(cls, agent_id: str) -> ScopePath:
        return cls(parts=("agent", agent_id))

    @classmethod
    def task_scope(cls, agent_id: str, task_id: str) -> ScopePath:
        return cls(parts=("agent", agent_id, "tasks", task_id))

    @classmethod
    def user_scope(cls, user_id: str) -> ScopePath:
        return cls(parts=("user", user_id))

    # -- Path operations -----------------------------------------------------

    @property
    def level(self) -> Optional[ScopeLevel]:
        """Determine the scope level from the first path component."""
        if not self.parts:
            return None
        first = self.parts[0]
        try:
            return ScopeLevel(first)
        except ValueError:
            return None

    @property
    def is_root(self) -> bool:
        return len(self.parts) == 0

    @property
    def parent(self) -> Optional[ScopePath]:
        """Return the parent scope, or None if this is root."""
        if self.is_root:
            return None
        return ScopePath(parts=self.parts[:-1])

    def child(self, name: str) -> ScopePath:
        """Return a new scope path with *name* appended."""
        return ScopePath(parts=self.parts + (name,))

    def is_ancestor_of(self, other: ScopePath) -> bool:
        """True if this scope is a strict ancestor of *other*."""
        if self.is_root:
            return not other.is_root
        return (
            len(other.parts) > len(self.parts)
            and other.parts[: len(self.parts)] == self.parts
        )

    def is_descendant_of(self, other: ScopePath) -> bool:
        """True if this scope is a strict descendant of *other*."""
        return other.is_ancestor_of(self)

    def is_subtree_of(self, other: ScopePath) -> bool:
        """True if this scope equals or is a descendant of *other*."""
        if self == other:
            return True
        return self.is_descendant_of(other)

    def common_ancestor(self, other: ScopePath) -> ScopePath:
        """Return the deepest common ancestor of two scope paths."""
        common: list[str] = []
        for a, b in zip(self.parts, other.parts):
            if a == b:
                common.append(a)
            else:
                break
        return ScopePath(parts=tuple(common))

    def relative_to(self, ancestor: ScopePath) -> ScopePath:
        """Return the relative path from *ancestor* to this scope."""
        if not self.is_subtree_of(ancestor):
            raise ScopeValidationError(
                f"{self} is not a subtree of {ancestor}"
            )
        return ScopePath(parts=self.parts[len(ancestor.parts):])

    # -- Access control helpers ----------------------------------------------

    def can_read(self, agent_id: str) -> bool:
        """
        Determine if *agent_id* has read access to this scope.

        Rules:
        - /global/          -> everyone
        - /swarm/           -> every swarm agent
        - /agent/{aid}/...  -> only that agent
        - /user/{uid}/...   -> denied (reserved for user-facing layer)
        - /agent/{aid}/tasks/{tid} -> only that agent
        """
        if not self.parts:
            return False
        first = self.parts[0]
        if first == "global":
            return True
        if first == "swarm":
            return True
        if first == "agent" and len(self.parts) >= 2:
            return self.parts[1] == agent_id
        if first == "user":
            return False  # user scope requires separate auth layer
        return False

    def can_write(self, agent_id: str) -> bool:
        """
        Determine if *agent_id* has write access to this scope.

        Write is more restrictive: agents can only write to their own
        scope and task sub-scopes, plus /swarm/ for shared knowledge.
        """
        if not self.parts:
            return False
        first = self.parts[0]
        if first == "swarm":
            return True
        if first == "agent" and len(self.parts) >= 2:
            return self.parts[1] == agent_id
        return False

    # -- Serialization -------------------------------------------------------

    def __str__(self) -> str:
        if self.is_root:
            return "/"
        return "/" + "/".join(self.parts) + "/"

    def __repr__(self) -> str:
        return f"ScopePath({str(self)!r})"

    def __hash__(self) -> int:
        return hash(self.parts)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, ScopePath):
            return NotImplemented
        return self.parts == other.parts


@dataclass
class MemoryScope:
    """
    A named scope with metadata and optional access rules.

    Used to register scopes in the memory system and attach
    per-scope configuration (e.g. retention policies, scoring weights).
    """

    path: ScopePath
    label: str = ""
    retention_days: Optional[int] = None
    max_entries: Optional[int] = None
    metadata: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.label:
            self.label = str(self.path)


@dataclass(frozen=True)
class MemorySlice:
    """
    A read-only view that aggregates memories from multiple disjoint scopes.

    Useful for "cross-cutting" queries, e.g. an agent reading its own
    memories plus global knowledge plus a specific task context.

    Slices are immutable; create a new slice to change the scope set.
    """

    name: str
    scopes: tuple[ScopePath, ...]
    agent_id: Optional[str] = None

    def __init__(
        self,
        name: str,
        scopes: Iterable[ScopePath],
        agent_id: Optional[str] = None,
    ) -> None:
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "scopes", tuple(scopes))
        object.__setattr__(self, "agent_id", agent_id)

    def validate_access(self) -> None:
        """Raise ScopeAccessError if the agent cannot read any scope."""
        if self.agent_id is None:
            return
        for scope in self.scopes:
            if not scope.can_read(self.agent_id):
                raise ScopeAccessError(
                    f"Agent {self.agent_id!r} cannot read scope {scope}"
                )

    def add_scope(self, scope: ScopePath) -> MemorySlice:
        """Return a new slice with *scope* added."""
        return MemorySlice(
            name=self.name,
            scopes=(*self.scopes, scope),
            agent_id=self.agent_id,
        )

    def remove_scope(self, scope: ScopePath) -> MemorySlice:
        """Return a new slice with *scope* removed."""
        return MemorySlice(
            name=self.name,
            scopes=tuple(s for s in self.scopes if s != scope),
            agent_id=self.agent_id,
        )

    def __str__(self) -> str:
        scopes_str = ", ".join(str(s) for s in self.scopes)
        return f"MemorySlice({self.name!r}, [{scopes_str}])"
