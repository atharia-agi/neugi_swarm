"""
MCP Resource Manager - Manages resource registration and access
==============================================================
"""

from __future__ import annotations

import logging
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from neugi_swarm_v2.mcp.messages import (
    ListResourcesResult,
    ReadResourceResult,
)

logger = logging.getLogger(__name__)


@dataclass
class ResourceTemplate:
    """Template for dynamic resource URIs."""
    uri_template: str
    name: str
    description: str
    mimeType: Optional[str] = None
    annotations: Optional[dict] = None


@dataclass
class Resource:
    """Represents a registered MCP resource."""
    uri: str
    name: str
    description: str
    mimeType: Optional[str] = None
    annotations: Optional[dict] = None
    content: Any = None
    loader: Optional[Callable] = None

    def read(self) -> Any:
        """Read resource content, using loader if available."""
        if self.loader is not None:
            return self.loader(self.uri)
        return self.content


class ResourceManager:
    """Manages resource registration and access for MCP clients."""

    def __init__(self):
        self._static_resources: Dict[str, Resource] = {}
        self._templates: Dict[str, ResourceTemplate] = {}
        self._dynamic_handlers: Dict[str, Callable] = {}
        self._cache: Dict[str, Any] = {}
        self._cache_ttl: Dict[str, float] = {}

    def register_static(
        self,
        uri: str,
        name: str,
        description: str = "",
        mimeType: Optional[str] = None,
        annotations: Optional[dict] = None,
        content: Any = None,
    ) -> Resource:
        """Register a static resource with fixed content."""
        resource = Resource(
            uri=uri,
            name=name,
            description=description,
            mimeType=mimeType,
            annotations=annotations,
            content=content,
        )
        self._static_resources[uri] = resource
        logger.debug("Registered static resource: %s", uri)
        return resource

    def register_template(
        self,
        uri_template: str,
        name: str,
        description: str = "",
        mimeType: Optional[str] = None,
        annotations: Optional[dict] = None,
    ) -> ResourceTemplate:
        """Register a resource template for dynamic URIs."""
        template = ResourceTemplate(
            uri_template=uri_template,
            name=name,
            description=description,
            mimeType=mimeType,
            annotations=annotations,
        )
        self._templates[uri_template] = template
        logger.debug("Registered resource template: %s", uri_template)
        return template

    def register_dynamic(
        self,
        uri_prefix: str,
        handler: Callable,
    ) -> None:
        """Register a dynamic handler for URI prefix.

        Args:
            uri_prefix: URI prefix (e.g., "memory://")
            handler: Function called with full URI, returns content
        """
        self._dynamic_handlers[uri_prefix] = handler
        logger.debug("Registered dynamic handler for prefix: %s", uri_prefix)

    def register_file(
        self,
        file_path: str,
        uri: Optional[str] = None,
        name: Optional[str] = None,
        mimeType: Optional[str] = None,
    ) -> Resource:
        """Register a local file as a resource."""
        if uri is None:
            uri = f"file://{file_path}"
        if name is None:
            name = Path(file_path).name

        def file_loader(uri: str) -> Any:
            path = uri.replace("file://", "")
            try:
                content = Path(path).read_text(encoding="utf-8")
                return content
            except Exception as e:
                logger.error("Failed to read file %s: %s", path, e)
                raise

        return self.register_static(
            uri=uri,
            name=name,
            description=f"Local file: {file_path}",
            mimeType=mimeType or "text/plain",
            loader=file_loader,
        )

    def register_memory_resource(
        self,
        key: str,
        name: str,
        memory_system: Any,
    ) -> None:
        """Register a memory-based resource.

        Args:
            key: Memory key or scope
            name: Human-readable name
            memory_system: MemorySystem instance
        """
        def memory_loader(uri: str) -> Any:
            try:
                # Extract key from URI
                parts = uri.replace("memory://", "").split("/")
                search_key = parts[-1] if parts else key

                # Try to retrieve from memory
                entries = memory_system.search(search_key, limit=5)
                return json.dumps([
                    {
                        "key": entry.key,
                        "value": entry.value,
                        "timestamp": entry.timestamp.isoformat() if hasattr(entry, 'timestamp') else None,
                    }
                    for entry in entries
                ], indent=2, default=str)
            except Exception as e:
                logger.error("Failed to load memory resource %s: %s", uri, e)
                return json.dumps({"error": str(e)})

        self.register_dynamic(
            uri_prefix=f"memory://{key}",
            handler=memory_loader,
        )

    def list_resources(self, cursor: Optional[str] = None) -> ListResourcesResult:
        """List all available resources."""
        resources = []

        # Static resources
        for resource in self._static_resources.values():
            entry = {
                "uri": resource.uri,
                "name": resource.name,
                "description": resource.description,
            }
            if resource.mimeType:
                entry["mimeType"] = resource.mimeType
            if resource.annotations:
                entry["annotations"] = resource.annotations
            resources.append(entry)

        # Templates
        for template in self._templates.values():
            resources.append({
                "uriTemplate": template.uri_template,
                "name": template.name,
                "description": template.description,
                "mimeType": template.mimeType,
                "annotations": template.annotations,
            })

        # Dynamic handlers (list prefixes)
        for prefix in self._dynamic_handlers:
            resources.append({
                "uri": f"{prefix}*",
                "name": f"Dynamic: {prefix}",
                "description": f"Dynamic resource handler for prefix {prefix}",
            })

        return ListResourcesResult(resources=resources)

    def read_resource(self, uri: str) -> ReadResourceResult:
        """Read a specific resource by URI."""
        contents = []

        # Check static resources
        if uri in self._static_resources:
            resource = self._static_resources[uri]
            content = resource.read()
            contents.append({
                "uri": uri,
                "text": str(content),
                "mimeType": resource.mimeType or "text/plain",
            })
            return ReadResourceResult(contents=contents)

        # Check dynamic handlers
        for prefix, handler in self._dynamic_handlers.items():
            if uri.startswith(prefix):
                try:
                    content = handler(uri)
                    contents.append({
                        "uri": uri,
                        "text": str(content),
                        "mimeType": "application/json",
                    })
                    return ReadResourceResult(contents=contents)
                except Exception as e:
                    return ReadResourceResult(contents=[
                        {
                            "uri": uri,
                            "text": f"Error: {e}",
                            "mimeType": "text/plain",
                        }
                    ])

        # Check templates
        for template in self._templates.values():
            if self._matches_template(uri, template.uri_template):
                try:
                    content = f"Template resource: {uri}"
                    contents.append({
                        "uri": uri,
                        "text": content,
                        "mimeType": template.mimeType or "text/plain",
                    })
                    return ReadResourceResult(contents=contents)
                except Exception as e:
                    return ReadResourceResult(contents=[
                        {
                            "uri": uri,
                            "text": f"Error: {e}",
                            "mimeType": "text/plain",
                        }
                    ])

        return ReadResourceResult(contents=[{
            "uri": uri,
            "text": f"Resource not found: {uri}",
            "mimeType": "text/plain",
        }])

    @staticmethod
    def _matches_template(uri: str, template: str) -> bool:
        """Check if URI matches a template pattern."""
        # Simple pattern matching: replace {var} with wildcard
        import re
        pattern = re.sub(r'\{[^}]+\}', r'[^/]+', template)
        return bool(re.fullmatch(pattern, uri))

    def count(self) -> int:
        """Return number of registered resources."""
        return len(self._static_resources) + len(self._templates) + len(self._dynamic_handlers)

    def clear(self) -> None:
        """Clear all registered resources."""
        self._static_resources.clear()
        self._templates.clear()
        self._dynamic_handlers.clear()
        self._cache.clear()
        logger.debug("Cleared all MCP resources")