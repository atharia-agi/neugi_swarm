"""
NEUGI v2 MCP Resource System
==============================

Resource management for the Model Context Protocol. Supports file resources,
memory resources, agent resources, skill resources, parameterized templates,
and subscription-based notifications.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional
from urllib.parse import unquote, urlparse

from neugi_swarm_v2.mcp.protocol import (
    Resource,
    ResourceContents,
    ResourceTemplate,
    ResourceUpdatedNotification,
    JSONRPCNotification,
)

logger = logging.getLogger(__name__)


# -- Resource Handler --------------------------------------------------------

@dataclass
class ResourceHandler:
    """A handler that provides content for a resource.

    Attributes:
        uri: Resource URI or URI pattern.
        name: Human-readable name.
        description: Optional description.
        mime_type: Optional MIME type.
        read_fn: Callable that returns resource content.
        is_template: Whether the URI is a template with placeholders.
    """

    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None
    read_fn: Optional[Callable[..., str | bytes]] = None
    is_template: bool = False

    def to_resource(self) -> Resource:
        """Convert to an MCP Resource definition."""
        return Resource(
            uri=self.uri,
            name=self.name,
            description=self.description,
            mime_type=self.mime_type,
        )

    def to_template(self) -> ResourceTemplate:
        """Convert to an MCP ResourceTemplate."""
        return ResourceTemplate(
            uri_template=self.uri,
            name=self.name,
            description=self.description,
            mime_type=self.mime_type,
        )


# -- Subscription ------------------------------------------------------------

@dataclass
class ResourceSubscription:
    """A subscription to resource updates.

    Attributes:
        uri: Resource URI being watched.
        callback: Function to call on update.
        created_at: Subscription creation time.
    """

    uri: str
    callback: Callable[[ResourceUpdatedNotification], None]
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# -- URI Template Matcher ----------------------------------------------------

class URITemplateMatcher:
    """Matches URIs against URI templates with {placeholders}.

    Supports RFC 6570 Level 1 templates: {name}, {name*}.
    """

    _PATTERN = re.compile(r"\{(\w+)(\*?)\}")

    def __init__(self, template: str) -> None:
        self.template = template
        self._regex, self._param_names = self._compile(template)

    def _compile(self, template: str) -> tuple[re.Pattern, list[str]]:
        """Compile a URI template into a regex pattern."""
        pattern = template
        param_names: list[str] = []

        def replacer(match: re.Match) -> str:
            name = match.group(1)
            explode = match.group(2)
            param_names.append(name)
            if explode:
                return r"(?P<{}>[^/]+)".format(name)
            return r"(?P<{}>[^/]+)".format(name)

        pattern = self._PATTERN.sub(replacer, pattern)
        pattern = "^" + pattern + "$"
        return re.compile(pattern), param_names

    def match(self, uri: str) -> Optional[dict[str, str]]:
        """Match a URI against the template.

        Returns:
            Dict of parameter values if matched, None otherwise.
        """
        m = self._regex.match(uri)
        if m is None:
            return None
        return {k: unquote(v) for k, v in m.groupdict().items()}

    def expand(self, params: dict[str, str]) -> str:
        """Expand the template with parameter values."""
        result = self.template
        for name in self._param_names:
            value = params.get(name, "")
            result = result.replace("{" + name + "}", value)
            result = result.replace("{" + name + "*}", value)
        return result


# -- Resource Registry -------------------------------------------------------

class ResourceRegistry:
    """Registry for MCP resources with template matching and subscriptions.

    Supports:
    - File resources (read files from workspace)
    - Memory resources (read from memory system)
    - Agent resources (agent status, capabilities)
    - Skill resources (skill definitions, instructions)
    - Resource templates (parameterized resource URIs)
    - Resource subscriptions (notify on changes)

    Usage:
        registry = ResourceRegistry()

        # Register a static resource
        registry.register_resource(
            Resource(uri="neugi://config", name="NEUGI Configuration"),
            read_fn=lambda: json.dumps(config.to_dict()),
        )

        # Register a template
        registry.register_template(
            ResourceTemplate(uri_template="neugi://memory/{id}", name="Memory Entry"),
            read_fn=lambda id: memory_system.get(id).content,
        )

        # Read a resource
        contents = registry.read_resource("neugi://config")
    """

    def __init__(self, workspace_root: Optional[str] = None) -> None:
        """Initialize the resource registry.

        Args:
            workspace_root: Root directory for file:// resources.
        """
        self._resources: dict[str, ResourceHandler] = {}
        self._templates: list[tuple[ResourceTemplate, URITemplateMatcher, Callable]] = []
        self._subscriptions: dict[str, list[ResourceSubscription]] = {}
        self._workspace_root = Path(workspace_root) if workspace_root else Path.cwd()
        self._on_resource_registered: Optional[Callable[[Resource], None]] = None

    def register_resource(
        self,
        resource: Resource,
        read_fn: Optional[Callable[..., str | bytes]] = None,
    ) -> None:
        """Register a static resource.

        Args:
            resource: Resource definition.
            read_fn: Callable that returns resource content.
        """
        handler = ResourceHandler(
            uri=resource.uri,
            name=resource.name,
            description=resource.description,
            mime_type=resource.mime_type,
            read_fn=read_fn,
        )
        self._resources[resource.uri] = handler
        logger.info("Registered resource: %s", resource.uri)
        if self._on_resource_registered:
            self._on_resource_registered(resource)

    def register_template(
        self,
        template: ResourceTemplate,
        read_fn: Callable[..., str | bytes],
    ) -> None:
        """Register a parameterized resource template.

        Args:
            template: Resource template definition.
            read_fn: Callable with parameters matching template placeholders.
        """
        matcher = URITemplateMatcher(template.uri_template)
        self._templates.append((template, matcher, read_fn))
        logger.info("Registered resource template: %s", template.uri_template)

    def unregister(self, uri: str) -> bool:
        """Remove a resource from the registry.

        Returns:
            True if the resource was found and removed.
        """
        if uri in self._resources:
            del self._resources[uri]
            # Clean up subscriptions
            self._subscriptions.pop(uri, None)
            logger.info("Unregistered resource: %s", uri)
            return True
        return False

    def get_resource(self, uri: str) -> Optional[Resource]:
        """Get a resource definition by URI."""
        handler = self._resources.get(uri)
        if handler:
            return handler.to_resource()

        # Check templates
        for template, matcher, _ in self._templates:
            if matcher.match(uri):
                return Resource(
                    uri=uri,
                    name=template.name,
                    description=template.description,
                    mime_type=template.mime_type,
                )

        return None

    def list_resources(self) -> list[Resource]:
        """List all registered resources."""
        resources = [h.to_resource() for h in self._resources.values()]
        # Templates are listed separately via list_templates()
        return resources

    def list_templates(self) -> list[ResourceTemplate]:
        """List all registered resource templates."""
        return [t for t, _, _ in self._templates]

    def read_resource(self, uri: str) -> ResourceContents:
        """Read a resource's content by URI.

        Args:
            uri: Resource URI.

        Returns:
            ResourceContents with text or blob data.

        Raises:
            ValueError: If the resource is not found.
        """
        # Check static resources
        handler = self._resources.get(uri)
        if handler:
            return self._read_handler(handler)

        # Check templates
        for template, matcher, read_fn in self._templates:
            params = matcher.match(uri)
            if params:
                try:
                    content = read_fn(**params)
                    return self._make_contents(uri, content, template.mime_type)
                except Exception as exc:
                    raise ValueError(f"Failed to read resource {uri}: {exc}") from exc

        raise ValueError(f"Resource not found: {uri}")

    def _read_handler(self, handler: ResourceHandler) -> ResourceContents:
        """Read content from a resource handler."""
        if handler.read_fn is None:
            return ResourceContents(uri=handler.uri, text="")

        try:
            content = handler.read_fn()
            return self._make_contents(handler.uri, content, handler.mime_type)
        except Exception as exc:
            raise ValueError(
                f"Failed to read resource {handler.uri}: {exc}"
            ) from exc

    def _make_contents(
        self, uri: str, content: str | bytes, mime_type: Optional[str] = None
    ) -> ResourceContents:
        """Create ResourceContents from raw content."""
        if isinstance(content, bytes):
            import base64
            return ResourceContents(
                uri=uri,
                blob=base64.b64encode(content).decode("ascii"),
                mime_type=mime_type or "application/octet-stream",
            )
        return ResourceContents(
            uri=uri,
            text=content,
            mime_type=mime_type or "text/plain",
        )

    # -- Subscription Management ---------------------------------------------

    def subscribe(
        self,
        uri: str,
        callback: Callable[[ResourceUpdatedNotification], None],
    ) -> None:
        """Subscribe to resource updates.

        Args:
            uri: Resource URI to watch.
            callback: Function called when the resource changes.
        """
        if uri not in self._subscriptions:
            self._subscriptions[uri] = []
        self._subscriptions[uri].append(
            ResourceSubscription(uri=uri, callback=callback)
        )
        logger.info("Subscribed to resource: %s", uri)

    def unsubscribe(
        self,
        uri: str,
        callback: Optional[Callable[[ResourceUpdatedNotification], None]] = None,
    ) -> int:
        """Unsubscribe from resource updates.

        Args:
            uri: Resource URI.
            callback: Specific callback to remove (None removes all).

        Returns:
            Number of subscriptions removed.
        """
        if uri not in self._subscriptions:
            return 0

        if callback is None:
            count = len(self._subscriptions[uri])
            del self._subscriptions[uri]
            return count

        before = len(self._subscriptions[uri])
        self._subscriptions[uri] = [
            s for s in self._subscriptions[uri] if s.callback != callback
        ]
        removed = before - len(self._subscriptions[uri])
        if not self._subscriptions[uri]:
            del self._subscriptions[uri]
        return removed

    def notify_update(self, uri: str) -> int:
        """Notify all subscribers that a resource has been updated.

        Args:
            uri: Resource URI that changed.

        Returns:
            Number of notifications sent.
        """
        subs = self._subscriptions.get(uri, [])
        notification = ResourceUpdatedNotification(uri=uri)
        for sub in subs:
            try:
                sub.callback(notification)
            except Exception as exc:
                logger.error("Subscription callback failed for %s: %s", uri, exc)
        return len(subs)

    @property
    def subscription_count(self) -> int:
        """Total number of active subscriptions."""
        return sum(len(subs) for subs in self._subscriptions.values())

    # -- Built-in Resource Registration --------------------------------------

    def register_neugi_resources(
        self,
        memory_system: Optional[Any] = None,
        skill_manager: Optional[Any] = None,
        agent_manager: Optional[Any] = None,
        config: Optional[Any] = None,
    ) -> None:
        """Register NEUGI subsystem resources.

        Args:
            memory_system: MemorySystem instance.
            skill_manager: SkillManager instance.
            agent_manager: AgentManager instance.
            config: NeugiConfig instance.
        """
        # Config resource
        if config:
            self.register_resource(
                Resource(
                    uri="neugi://config",
                    name="NEUGI Configuration",
                    description="Current NEUGI v2 configuration",
                    mime_type="application/json",
                ),
                read_fn=lambda: json.dumps(config.to_dict(), indent=2, default=str),
            )

        # Memory resources
        if memory_system:
            self.register_resource(
                Resource(
                    uri="neugi://memory/stats",
                    name="Memory Statistics",
                    description="Memory system statistics",
                    mime_type="application/json",
                ),
                read_fn=lambda: json.dumps(memory_system.stats, indent=2),
            )

            self.register_template(
                ResourceTemplate(
                    uri_template="neugi://memory/{id}",
                    name="Memory Entry",
                    description="Read a specific memory entry by ID",
                    mime_type="text/plain",
                ),
                read_fn=lambda id: self._read_memory_entry(memory_system, id),
            )

            self.register_resource(
                Resource(
                    uri="neugi://memory/core",
                    name="Core Memories",
                    description="All core-tier memories",
                    mime_type="text/markdown",
                ),
                read_fn=lambda: self._read_core_memories(memory_system),
            )

        # Skill resources
        if skill_manager:
            self.register_resource(
                Resource(
                    uri="neugi://skills/list",
                    name="Skills List",
                    description="List of all loaded skills",
                    mime_type="application/json",
                ),
                read_fn=lambda: self._list_skills_json(skill_manager),
            )

            self.register_template(
                ResourceTemplate(
                    uri_template="neugi://skills/{name}",
                    name="Skill Definition",
                    description="Read a skill definition by name",
                    mime_type="text/markdown",
                ),
                read_fn=lambda name: self._read_skill(skill_manager, name),
            )

        # Agent resources
        if agent_manager:
            self.register_resource(
                Resource(
                    uri="neugi://agents/list",
                    name="Agents List",
                    description="List of all registered agents",
                    mime_type="application/json",
                ),
                read_fn=lambda: self._list_agents_json(agent_manager),
            )

            self.register_template(
                ResourceTemplate(
                    uri_template="neugi://agents/{name}",
                    name="Agent Details",
                    description="Read agent status and capabilities",
                    mime_type="application/json",
                ),
                read_fn=lambda name: self._read_agent(agent_manager, name),
            )

        # File resources template
        self.register_template(
            ResourceTemplate(
                uri_template="file://{path}",
                name="Workspace File",
                description="Read a file from the workspace",
            ),
            read_fn=lambda path: self._read_file(path),
        )

    def _read_memory_entry(self, memory_system: Any, id: str) -> str:
        """Read a memory entry by ID."""
        entry = memory_system.get(id)
        if entry is None:
            return f"Memory entry '{id}' not found"
        return json.dumps(entry.to_dict(), indent=2, default=str)

    def _read_core_memories(self, memory_system: Any) -> str:
        """Read all core-tier memories as markdown."""
        from neugi_swarm_v2.memory import MemoryTier

        with memory_system._store_lock:
            entries = [
                e for e in memory_system._store.values()
                if e.tier == MemoryTier.CORE and not e.is_expired()
            ]

        entries.sort(key=lambda e: e.importance, reverse=True)
        lines = ["# Core Memories\n"]
        for entry in entries:
            lines.append(f"\n## {entry.id} (importance: {entry.importance:.2f})\n")
            lines.append(f"Scope: {entry.scope}\n")
            lines.append(f"Tags: {', '.join(entry.tags)}\n")
            lines.append(f"\n{entry.content}\n")
        return "\n".join(lines)

    def _list_skills_json(self, skill_manager: Any) -> str:
        """List all skills as JSON."""
        skills = skill_manager.get_all()
        items = [
            {
                "name": s.name,
                "description": s.frontmatter.description,
                "tier": s.tier.value,
                "tags": s.frontmatter.tags,
                "enabled": s.is_enabled,
            }
            for s in skills.values()
        ]
        return json.dumps(items, indent=2, ensure_ascii=False)

    def _read_skill(self, skill_manager: Any, name: str) -> str:
        """Read a skill definition."""
        skill = skill_manager.get(name)
        if skill is None:
            return f"Skill '{name}' not found"
        return skill.to_skill_md() if hasattr(skill, "to_skill_md") else str(skill)

    def _list_agents_json(self, agent_manager: Any) -> str:
        """List all agents as JSON."""
        agents = agent_manager.list_agents()
        items = [
            {
                "id": a.id,
                "name": a.name,
                "role": a.role.value,
                "level": a.level,
                "status": a.status.value,
                "xp": a.xp,
            }
            for a in agents
        ]
        return json.dumps(items, indent=2)

    def _read_agent(self, agent_manager: Any, name: str) -> str:
        """Read agent details."""
        agent = agent_manager.get(name)
        if agent is None:
            return json.dumps({"error": f"Agent '{name}' not found"})
        return json.dumps(agent.to_dict(), indent=2, default=str)

    def _read_file(self, path: str) -> str:
        """Read a file from the workspace."""
        full_path = self._workspace_root / path
        if not full_path.exists():
            raise FileNotFoundError(f"File not found: {full_path}")
        if not full_path.is_file():
            raise IsADirectoryError(f"Not a file: {full_path}")
        return full_path.read_text(encoding="utf-8")

    @property
    def stats(self) -> dict[str, Any]:
        """Get registry statistics."""
        return {
            "resources": len(self._resources),
            "templates": len(self._templates),
            "subscriptions": self.subscription_count,
        }
