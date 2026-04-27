"""
NEUGI v2 MCP Protocol Types
=============================

JSON-RPC 2.0 message types and MCP-specific types per the Model Context
Protocol specification. Includes serialization, deserialization, and
standard error codes.

Reference: https://spec.modelcontextprotocol.io
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from enum import IntEnum
from typing import Any, Optional, Union


# -- JSON-RPC 2.0 Error Codes ------------------------------------------------

class ErrorCode(IntEnum):
    """Standard JSON-RPC 2.0 and MCP error codes."""

    PARSE_ERROR = -32700
    INVALID_REQUEST = -32600
    METHOD_NOT_FOUND = -32601
    INVALID_PARAMS = -32602
    INTERNAL_ERROR = -32603

    # MCP-specific error codes
    RESOURCE_NOT_FOUND = -32002
    TOOL_NOT_FOUND = -32003
    PROMPT_NOT_FOUND = -32004
    RESOURCE_SUBSCRIPTION_NOT_SUPPORTED = -32005
    TOO_MANY_REQUESTS = -32006
    REQUEST_TIMEOUT = -32007


# -- MCP Error ---------------------------------------------------------------

@dataclass
class MCPError:
    """An MCP/JSON-RPC error object.

    Attributes:
        code: Numeric error code.
        message: Human-readable error description.
        data: Optional additional error data.
    """

    code: int
    message: str
    data: Optional[Any] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"code": self.code, "message": self.message}
        if self.data is not None:
            d["data"] = self.data
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MCPError:
        return cls(
            code=data["code"],
            message=data["message"],
            data=data.get("data"),
        )


# -- JSON-RPC 2.0 Messages ---------------------------------------------------

@dataclass
class JSONRPCRequest:
    """A JSON-RPC 2.0 request object.

    Attributes:
        jsonrpc: Protocol version ("2.0").
        id: Request identifier (null for notifications).
        method: Method name to invoke.
        params: Method parameters.
    """

    method: str
    id: Optional[Union[str, int]] = None
    params: Optional[dict[str, Any]] = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"jsonrpc": self.jsonrpc, "method": self.method}
        if self.id is not None:
            d["id"] = self.id
        if self.params is not None:
            d["params"] = self.params
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JSONRPCRequest:
        return cls(
            jsonrpc=data.get("jsonrpc", "2.0"),
            id=data.get("id"),
            method=data["method"],
            params=data.get("params"),
        )

    @classmethod
    def parse(cls, raw: str) -> JSONRPCRequest:
        """Parse a JSON-RPC request from a JSON string."""
        data = json.loads(raw)
        return cls.from_dict(data)


@dataclass
class JSONRPCResponse:
    """A JSON-RPC 2.0 response object.

    Attributes:
        jsonrpc: Protocol version ("2.0").
        id: Matching request identifier.
        result: Method result (mutually exclusive with error).
        error: Error object (mutually exclusive with result).
    """

    id: Optional[Union[str, int]]
    result: Optional[Any] = None
    error: Optional[MCPError] = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"jsonrpc": self.jsonrpc, "id": self.id}
        if self.error is not None:
            d["error"] = self.error.to_dict()
        else:
            d["result"] = self.result if self.result is not None else {}
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)

    @classmethod
    def success(
        cls, request_id: Optional[Union[str, int]], result: Any
    ) -> JSONRPCResponse:
        return cls(id=request_id, result=result)

    @classmethod
    def error(
        cls, request_id: Optional[Union[str, int]], err: MCPError
    ) -> JSONRPCResponse:
        return cls(id=request_id, error=err)


@dataclass
class JSONRPCNotification:
    """A JSON-RPC 2.0 notification (no id, no response expected).

    Attributes:
        jsonrpc: Protocol version ("2.0").
        method: Notification method name.
        params: Notification parameters.
    """

    method: str
    params: Optional[dict[str, Any]] = None
    jsonrpc: str = "2.0"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"jsonrpc": self.jsonrpc, "method": self.method}
        if self.params is not None:
            d["params"] = self.params
        return d

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False)


# -- Implementation Info -----------------------------------------------------

@dataclass
class Implementation:
    """Server/client implementation metadata.

    Attributes:
        name: Implementation name.
        version: Implementation version string.
    """

    name: str
    version: str

    def to_dict(self) -> dict[str, Any]:
        return {"name": self.name, "version": self.version}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Implementation:
        return cls(name=data["name"], version=data["version"])


# -- Server Capabilities -----------------------------------------------------

@dataclass
class ServerCapabilities:
    """Capabilities advertised by the server during initialization.

    Attributes:
        tools: Tool support configuration.
        resources: Resource support configuration.
        prompts: Prompt support configuration.
        logging: Logging level support.
        experimental: Experimental feature flags.
    """

    tools: Optional[dict[str, Any]] = None
    resources: Optional[dict[str, Any]] = None
    prompts: Optional[dict[str, Any]] = None
    logging: Optional[dict[str, Any]] = None
    experimental: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.tools is not None:
            d["tools"] = self.tools
        if self.resources is not None:
            d["resources"] = self.resources
        if self.prompts is not None:
            d["prompts"] = self.prompts
        if self.logging is not None:
            d["logging"] = self.logging
        if self.experimental is not None:
            d["experimental"] = self.experimental
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ServerCapabilities:
        return cls(
            tools=data.get("tools"),
            resources=data.get("resources"),
            prompts=data.get("prompts"),
            logging=data.get("logging"),
            experimental=data.get("experimental"),
        )

    @classmethod
    def full_capabilities(cls) -> ServerCapabilities:
        """Create capabilities with all features enabled."""
        return cls(
            tools={"listChanged": True},
            resources={"listChanged": True, "subscribe": True},
            prompts={"listChanged": True},
            logging={},
        )


# -- Initialize Result -------------------------------------------------------

@dataclass
class InitializeResult:
    """Response to the initialize request.

    Attributes:
        protocol_version: MCP protocol version string.
        capabilities: Server capabilities.
        server_info: Server implementation metadata.
        instructions: Optional human-readable instructions.
    """

    protocol_version: str
    capabilities: ServerCapabilities
    server_info: Implementation
    instructions: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "protocolVersion": self.protocol_version,
            "capabilities": self.capabilities.to_dict(),
            "serverInfo": self.server_info.to_dict(),
        }
        if self.instructions is not None:
            d["instructions"] = self.instructions
        return d


# -- Content Blocks ----------------------------------------------------------

@dataclass
class TextContent:
    """Text content block.

    Attributes:
        type: Always "text".
        text: The text content.
    """

    text: str
    type: str = "text"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "text": self.text}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TextContent:
        return cls(text=data["text"])


@dataclass
class ImageContent:
    """Image content block (base64 encoded).

    Attributes:
        type: Always "image".
        data: Base64-encoded image data.
        mime_type: MIME type (e.g. "image/png").
    """

    data: str
    mime_type: str
    type: str = "image"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "data": self.data, "mimeType": self.mime_type}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ImageContent:
        return cls(data=data["data"], mime_type=data["mimeType"])


@dataclass
class ResourceContent:
    """Embedded resource content block.

    Attributes:
        type: Always "resource".
        resource: The embedded resource data.
    """

    resource: dict[str, Any]
    type: str = "resource"

    def to_dict(self) -> dict[str, Any]:
        return {"type": self.type, "resource": self.resource}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResourceContent:
        return cls(resource=data["resource"])


ContentBlock = Union[TextContent, ImageContent, ResourceContent]


def content_from_dict(data: dict[str, Any]) -> ContentBlock:
    """Deserialize a content block from a dict."""
    ctype = data.get("type", "text")
    if ctype == "image":
        return ImageContent.from_dict(data)
    elif ctype == "resource":
        return ResourceContent.from_dict(data)
    return TextContent.from_dict(data)


def content_to_dict(content: ContentBlock) -> dict[str, Any]:
    """Serialize a content block to a dict."""
    return content.to_dict()


# -- Tool Types --------------------------------------------------------------

@dataclass
class Tool:
    """A tool definition advertised by the server.

    Attributes:
        name: Unique tool name.
        description: Human-readable description.
        input_schema: JSON Schema for tool arguments.
        annotations: Optional tool annotations.
    """

    name: str
    description: str
    input_schema: dict[str, Any]
    annotations: Optional[dict[str, Any]] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
        }
        if self.annotations is not None:
            d["annotations"] = self.annotations
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Tool:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            input_schema=data.get("inputSchema", {"type": "object", "properties": {}}),
            annotations=data.get("annotations"),
        )


@dataclass
class ToolResult:
    """Result from a tool invocation.

    Attributes:
        content: List of content blocks.
        is_error: Whether the tool execution failed.
    """

    content: list[ContentBlock]
    is_error: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "content": [content_to_dict(c) for c in self.content],
            "isError": self.is_error,
        }

    @classmethod
    def from_text(cls, text: str, is_error: bool = False) -> ToolResult:
        return cls(content=[TextContent(text=text)], is_error=is_error)


# -- Pagination --------------------------------------------------------------

@dataclass
class CursorResult:
    """Paginated result with optional cursor.

    Attributes:
        items: List of result items.
        next_cursor: Cursor for the next page (None if no more).
    """

    items: list[Any]
    next_cursor: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {}
        if self.next_cursor is not None:
            d["nextCursor"] = self.next_cursor
        return d


# -- Resource Types ----------------------------------------------------------

@dataclass
class Resource:
    """A resource definition.

    Attributes:
        uri: Resource URI.
        name: Human-readable name.
        description: Optional description.
        mime_type: Optional MIME type.
        size: Optional size in bytes.
    """

    uri: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None
    size: Optional[int] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "uri": self.uri,
            "name": self.name,
        }
        if self.description is not None:
            d["description"] = self.description
        if self.mime_type is not None:
            d["mimeType"] = self.mime_type
        if self.size is not None:
            d["size"] = self.size
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Resource:
        return cls(
            uri=data["uri"],
            name=data["name"],
            description=data.get("description"),
            mime_type=data.get("mimeType"),
            size=data.get("size"),
        )


@dataclass
class ResourceTemplate:
    """A parameterized resource URI template.

    Attributes:
        uri_template: URI template with {placeholders}.
        name: Human-readable name.
        description: Optional description.
        mime_type: Optional MIME type.
    """

    uri_template: str
    name: str
    description: Optional[str] = None
    mime_type: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "uriTemplate": self.uri_template,
            "name": self.name,
        }
        if self.description is not None:
            d["description"] = self.description
        if self.mime_type is not None:
            d["mimeType"] = self.mime_type
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResourceTemplate:
        return cls(
            uri_template=data["uriTemplate"],
            name=data["name"],
            description=data.get("description"),
            mime_type=data.get("mimeType"),
        )


@dataclass
class ResourceContents:
    """Contents of a resource.

    Attributes:
        uri: Resource URI.
        mime_type: Optional MIME type.
        text: Text content (for text resources).
        blob: Base64-encoded binary content (for binary resources).
    """

    uri: str
    text: Optional[str] = None
    blob: Optional[str] = None
    mime_type: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"uri": self.uri}
        if self.mime_type is not None:
            d["mimeType"] = self.mime_type
        if self.text is not None:
            d["text"] = self.text
        if self.blob is not None:
            d["blob"] = self.blob
        return d


# -- Prompt Types ------------------------------------------------------------

@dataclass
class PromptArgument:
    """A prompt template argument.

    Attributes:
        name: Argument name.
        description: Optional description.
        required: Whether the argument is required.
    """

    name: str
    description: Optional[str] = None
    required: bool = False

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"name": self.name}
        if self.description is not None:
            d["description"] = self.description
        if self.required:
            d["required"] = True
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> PromptArgument:
        return cls(
            name=data["name"],
            description=data.get("description"),
            required=data.get("required", False),
        )


@dataclass
class Prompt:
    """A prompt template definition.

    Attributes:
        name: Unique prompt name.
        description: Human-readable description.
        arguments: List of prompt arguments.
    """

    name: str
    description: str
    arguments: list[PromptArgument] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "name": self.name,
            "description": self.description,
        }
        if self.arguments:
            d["arguments"] = [a.to_dict() for a in self.arguments]
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Prompt:
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            arguments=[
                PromptArgument.from_dict(a)
                for a in data.get("arguments", [])
            ],
        )


@dataclass
class PromptMessage:
    """A message within a prompt result.

    Attributes:
        role: Message role ("user" or "assistant").
        content: Content block.
    """

    role: str
    content: ContentBlock

    def to_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "content": content_to_dict(self.content),
        }


@dataclass
class PromptResult:
    """Result from getting a prompt template.

    Attributes:
        messages: List of prompt messages.
        description: Optional description.
    """

    messages: list[PromptMessage]
    description: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "messages": [m.to_dict() for m in self.messages],
        }
        if self.description is not None:
            d["description"] = self.description
        return d


# -- Notification Types ------------------------------------------------------

@dataclass
class ProgressNotification:
    """Progress notification for long-running operations.

    Attributes:
        progress_token: Token from the original request.
        progress: Current progress value.
        total: Optional total value.
    """

    progress_token: Union[str, int]
    progress: float
    total: Optional[float] = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {
            "progressToken": self.progress_token,
            "progress": self.progress,
        }
        if self.total is not None:
            d["total"] = self.total
        return d


@dataclass
class ResourceUpdatedNotification:
    """Notification that a resource has been updated.

    Attributes:
        uri: URI of the updated resource.
    """

    uri: str

    def to_dict(self) -> dict[str, Any]:
        return {"uri": self.uri}


# -- Serialization Helpers ---------------------------------------------------

def serialize_message(obj: Any) -> str:
    """Serialize any MCP message to a JSON string."""
    if hasattr(obj, "to_dict"):
        return json.dumps(obj.to_dict(), ensure_ascii=False)
    return json.dumps(obj, ensure_ascii=False)


def deserialize_message(raw: str) -> dict[str, Any]:
    """Deserialize a JSON string into a dict."""
    return json.loads(raw)


def generate_id() -> str:
    """Generate a unique request ID."""
    return uuid.uuid4().hex[:12]
