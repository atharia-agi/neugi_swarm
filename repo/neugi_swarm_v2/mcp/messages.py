"""
MCP Protocol Messages and Types
===============================
JSON-RPC 2.0 compatible message types for MCP protocol.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional
import json


class JSONRPCMessage:
    """Base JSON-RPC 2.0 message."""

    def __init__(self, jsonrpc: str = "2.0"):
        self.jsonrpc = jsonrpc

    def to_dict(self) -> dict:
        return {"jsonrpc": self.jsonrpc}

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict) -> "JSONRPCMessage":
        return cls(jsonrpc=data.get("jsonrpc", "2.0"))


@dataclass
class RequestMessage(JSONRPCMessage):
    """JSON-RPC request message."""
    method: str = ""
    params: Optional[dict] = None
    id: Optional[str | int] = None

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
    result: Optional[Any] = None
    error: Optional[dict] = None
    id: Optional[str | int] = None

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
    params: Optional[dict] = None

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
    client_info: Optional[dict] = None
    root_uri: Optional[str] = None
    process_id: Optional[int] = None


@dataclass
class InitializeResult:
    """Result from initialize request."""
    protocol_version: str = "2024-11-05"
    capabilities: dict = field(default_factory=dict)
    server_info: Optional[dict] = None


@dataclass
class ListToolsResult:
    """Result listing available tools."""
    tools: list[dict] = field(default_factory=list)
    next_cursor: Optional[str] = None


@dataclass
class CallToolResult:
    """Result from calling a tool."""
    content: list[dict] = field(default_factory=list)
    is_error: bool = False


@dataclass
class ListResourcesResult:
    """Result listing available resources."""
    resources: list[dict] = field(default_factory=list)
    next_cursor: Optional[str] = None


@dataclass
class ReadResourceResult:
    """Result from reading a resource."""
    contents: list[dict] = field(default_factory=list)


@dataclass
class ListPromptsResult:
    """Result listing available prompts."""
    prompts: list[dict] = field(default_factory=list)
    next_cursor: Optional[str] = None


@dataclass
class GetPromptResult:
    """Result from getting a prompt."""
    description: str = ""
    messages: list[dict] = field(default_factory=list)


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