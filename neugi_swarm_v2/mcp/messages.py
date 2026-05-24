"""
MCP Protocol Messages and Types
===============================
JSON-RPC 2.0 compatible message types for MCP protocol.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


class JSONRPCMessage:
    """Base JSON-RPC 2.0 message."""

    def __init__(self, jsonrpc: str = "2.0"):
        self.jsonrpc = jsonrpc

    def to_dict(self) -> dict:
        return {"jsonrpc": self.jsonrpc}

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> JSONRPCMessage:
        return cls(jsonrpc=data.get("jsonrpc", "2.0"))


@dataclass
class RequestMessage(JSONRPCMessage):
    """JSON-RPC request message."""
    method: str = ""
    params: dict | None = None
    id: str | int | None = None

    def to_dict(self) -> dict:
        d = super().to_dict()
        d.update({
            "method": self.method,
            "id": self.id,
        })
        if self.params is not None:
            d["params"] = self.params
        return d


@dataclass
class ResponseMessage(JSONRPCMessage):
    """JSON-RPC response message."""
    result: Any | None = None
    error: dict | None = None
    id: str | int | None = None

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["id"] = self.id
        if self.error is not None:
            d["error"] = self.error
        else:
            d["result"] = self.result
        return d


@dataclass
class NotificationMessage(JSONRPCMessage):
    """JSON-RPC notification (no response expected)."""
    method: str = ""
    params: dict | None = None

    def to_dict(self) -> dict:
        d = super().to_dict()
        d["method"] = self.method
        if self.params is not None:
            d["params"] = self.params
        return d


# MCP-specific message types
INITIALIZE = "initialize"
INITIALIZED = "initialized"
TOOLS_LIST = "tools/list"
TOOLS_CALL = "tools/call"
TOOLS_RESULT = "tools/call_result"
RESOURCES_LIST = "resources/list"
RESOURCES_READ = "resources/read"
PROMPTS_LIST = "prompts/list"
PROMPTS_GET = "prompts/get"
LOGGING_MESSAGE = "logging/message"
CANCEL_REQUEST = "$/cancelRequest"
PING = "ping"
PONG = "pong"


@dataclass
class InitializeParams:
    """Parameters for initialize request."""
    protocol_version: str = "2024-11-05"
    capabilities: dict = field(default_factory=dict)
    client_info: dict | None = None
    root_uri: str | None = None
    process_id: int | None = None


@dataclass
class InitializeResult:
    """Result from initialize request."""
    protocol_version: str = "2024-11-05"
    capabilities: dict = field(default_factory=dict)
    server_info: dict | None = None

    def to_dict(self) -> dict:
        return {
            "protocolVersion": self.protocol_version,
            "capabilities": self.capabilities,
            "serverInfo": self.server_info,
        }


@dataclass
class ListToolsResult:
    """Result listing available tools."""
    tools: list[dict] = field(default_factory=list)
    next_cursor: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"tools": self.tools}
        if self.next_cursor:
            d["nextCursor"] = self.next_cursor
        return d


@dataclass
class CallToolResult:
    """Result from calling a tool."""
    content: list[dict] = field(default_factory=list)
    is_error: bool = False

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "isError": self.is_error,
        }


@dataclass
class ListResourcesResult:
    """Result listing available resources."""
    resources: list[dict] = field(default_factory=list)
    next_cursor: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"resources": self.resources}
        if self.next_cursor:
            d["nextCursor"] = self.next_cursor
        return d


@dataclass
class ReadResourceResult:
    """Result from reading a resource."""
    contents: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {"contents": self.contents}


@dataclass
class ListPromptsResult:
    """Result listing available prompts."""
    prompts: list[dict] = field(default_factory=list)
    next_cursor: str | None = None

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"prompts": self.prompts}
        if self.next_cursor:
            d["nextCursor"] = self.next_cursor
        return d


@dataclass
class GetPromptResult:
    """Result from getting a prompt."""
    description: str = ""
    messages: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "description": self.description,
            "messages": self.messages,
        }


# MCP Error codes
ERROR_PARSE = -32700
ERROR_INVALID_REQUEST = -32600
ERROR_METHOD_NOT_FOUND = -32601
ERROR_INVALID_PARAMS = -32602
ERROR_INTERNAL = -32603
ERROR_TOOL_NOT_FOUND = -32001
ERROR_TOOL_EXECUTION = -32002
ERROR_RESOURCE_NOT_FOUND = -32003
ERROR_PROMPT_NOT_FOUND = -32004
