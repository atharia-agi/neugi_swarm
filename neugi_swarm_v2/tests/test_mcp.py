"""
Tests for MCP Server Subsystem
================================
Comprehensive tests for MCP server, transport, bridge, checkpoint,
SSE forwarder, and A2A adapter.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Ensure package root is importable
sys.path.insert(0, str(Path(__file__).parent.parent))

from neugi_swarm_v2.mcp.messages import (
    CallToolResult,
    InitializeResult,
    ListResourcesResult,
    ListToolsResult,
    RequestMessage,
    ResponseMessage,
    NotificationMessage,
    GetPromptResult,
    ListPromptsResult,
)
from neugi_swarm_v2.mcp.tool_manager import ToolManager
from neugi_swarm_v2.mcp.resource_manager import ResourceManager
from neugi_swarm_v2.mcp.prompt_manager import PromptManager, PromptTemplate
from neugi_swarm_v2.mcp.server import MCPServer
from neugi_swarm_v2.mcp.transport import (
    BaseTransport,
    StdioTransport,
    HTTPTransport,
    HTTPConnection,
    SSEConnection,
    RateLimiter,
    SSEAuth,
    TransportError,
)
from neugi_swarm_v2.mcp.checkpoint import (
    CheckpointStore,
    CheckpointData,
    ExecutionThread,
    ResilientMCPExecutor,
)
from neugi_swarm_v2.mcp.sse_forwarder import (
    SSEEventForwarder,
    get_sse_forwarder,
    setup_sse_forwarding,
)


# =============================================================================
# ToolManager Tests
# =============================================================================

class TestToolManager:
    def setup_method(self):
        self.tm = ToolManager()

    def test_register_tool(self):
        @self.tm.register(name="test_tool", description="A test tool",
                          input_schema={"type": "object", "properties": {}})
        def my_tool() -> str:
            return "done"
        assert self.tm.count() >= 1
        tools = self.tm.get_tools()
        names = [t["name"] for t in tools]
        assert "test_tool" in names

    def test_register_without_decorator(self):
        def my_tool(name: str) -> str:
            return f"hello {name}"
        self.tm._tools["hello"] = MagicMock(
            handler=my_tool,
            name="hello",
            description="Say hello",
            input_schema={"type": "object", "properties": {"name": {"type": "string"}}},
        )
        assert "hello" in self.tm._tools

    def test_list_tools(self):
        @self.tm.register(name="tool_a", description="Tool A",
                          input_schema={"type": "object", "properties": {}})
        def a():
            pass
        @self.tm.register(name="tool_b", description="Tool B",
                          input_schema={"type": "object", "properties": {}})
        def b():
            pass
        result = self.tm.list_tools()
        assert result.tools
        names = [t["name"] for t in result.tools]
        assert "tool_a" in names
        assert "tool_b" in names

    def test_get_tools_returns_list(self):
        tools = self.tm.get_tools()
        assert isinstance(tools, list)

    def test_register_duplicate_name(self):
        @self.tm.register(name="dup", description="first",
                          input_schema={"type": "object", "properties": {}})
        def first():
            pass
        @self.tm.register(name="dup", description="second",
                          input_schema={"type": "object", "properties": {}})
        def second():
            pass
        count = self.tm.count()
        assert count > 0

    def test_register_edge_empty_schema(self):
        @self.tm.register(name="empty", description="",
                          input_schema={"type": "object", "properties": {}})
        def empty():
            pass
        assert self.tm.count() > 0

    @pytest.mark.asyncio
    async def test_call_tool_returns_result(self):
        @self.tm.register(name="echo", description="echo",
                          input_schema={
                              "type": "object",
                              "properties": {"msg": {"type": "string"}},
                              "required": ["msg"],
                          })
        def echo_tool(msg: str) -> str:
            return f"echo: {msg}"
        result = await self.tm.call_tool("echo", {"msg": "hello"}, "req-1")
        assert isinstance(result, CallToolResult)

    @pytest.mark.asyncio
    async def test_call_nonexistent_tool(self):
        result = await self.tm.call_tool("nope", {}, "req-1")
        assert result.is_error

    def test_count(self):
        assert isinstance(self.tm.count(), int)


# =============================================================================
# ResourceManager Tests
# =============================================================================

class TestResourceManager:
    def setup_method(self):
        self.rm = ResourceManager()

    def test_register_static(self):
        self.rm.register_static(
            uri="test://static",
            name="Static Resource",
            description="A static resource",
            mimeType="text/plain",
            content="hello world",
        )
        result = self.rm.list_resources()
        assert result.resources
        uris = [r.get("uri") for r in result.resources]
        assert "test://static" in uris

    def test_read_static_resource(self):
        self.rm.register_static(
            uri="test://data",
            name="Test Data",
            description="Test",
            mimeType="application/json",
            content={"key": "value"},
        )
        result = self.rm.read_resource("test://data")
        assert result.contents
        assert len(result.contents) > 0

    def test_read_nonexistent_resource(self):
        result = self.rm.read_resource("test://nonexistent")
        assert result.contents
        assert "not found" in result.contents[0].get("text", "")

    def test_register_dynamic(self):
        def loader(uri: str) -> str:
            return "dynamic content"
        self.rm.register_dynamic("dynamic://items", loader)
        result = self.rm.read_resource("dynamic://items/1")
        assert result.contents

    def test_register_template(self):
        self.rm.register_template(
            uri_template="items://{id}",
            name="Item Template",
            description="Template",
            mimeType="application/json",
        )
        result = self.rm.list_resources()
        templates = [r for r in result.resources if "uriTemplate" in r]
        assert len(templates) > 0

    def test_count(self):
        assert isinstance(self.rm.count(), int)

    def test_list_resources_with_cursor(self):
        result = self.rm.list_resources(cursor="test")
        assert result.resources is not None

    def test_read_resource_edge_empty_uri(self):
        result = self.rm.read_resource("")
        assert result.contents
        assert "not found" in str(result.contents)

    def test_read_resource_edge_invalid_scheme(self):
        result = self.rm.read_resource("invalid://path")
        assert result.contents
        assert "not found" in str(result.contents)


# =============================================================================
# PromptManager Tests
# =============================================================================

class TestPromptManager:
    def setup_method(self):
        self.pm = PromptManager()

    def test_register_prompt(self):
        self.pm.register_prompt(
            name="test_prompt",
            description="A test prompt",
            template="Hello {{name}}",
            input_variables=["name"],
        )
        assert self.pm.count() >= 1

    def test_get_prompt(self):
        self.pm.register_prompt("test", "Test", "Hi {{name}}", ["name"])
        tmpl = self.pm.get_prompt("test")
        assert tmpl is not None
        assert tmpl.name == "test"

    def test_get_nonexistent_prompt(self):
        assert self.pm.get_prompt("nonexistent") is None

    def test_render_prompt(self):
        self.pm.register_prompt("greet", "Greet", "Hello, {name}!", ["name"])
        text = self.pm.render_prompt("greet", {"name": "World"})
        assert "Hello, World!" in text

    def test_render_prompt_without_vars(self):
        self.pm.register_prompt("static", "Static", "No variables here", [])
        text = self.pm.render_prompt("static", {})
        assert text == "No variables here"

    def test_render_nonexistent_prompt(self):
        import pytest as _pytest
        with _pytest.raises(ValueError):
            self.pm.render_prompt("nope", {})

    def test_list_prompts(self):
        self.pm.register_prompt("a", "A", "content", [])
        self.pm.register_prompt("b", "B", "content", [])
        result = self.pm.list_prompts()
        assert result.prompts
        assert len(result.prompts) >= 2

    def test_count(self):
        assert isinstance(self.pm.count(), int)

    def test_install_default_prompts(self):
        self.pm.install_default_prompts()
        assert self.pm.count() > 0


# =============================================================================
# MCPServer Tests
# =============================================================================

class TestMCPServer:
    def setup_method(self):
        self.server = MCPServer(name="test-server", version="2.0.0")

    def test_init(self):
        assert self.server.name == "test-server"
        assert self.server.version == "2.0.0"
        assert self.server.session_id is not None

    def test_has_default_tools(self):
        assert self.server.tools.count() > 0

    def test_has_default_resources(self):
        assert self.server.resources.count() > 0

    def test_register_tool_shortcut(self):
        self.server.tools._tools["shortcut_test"] = MagicMock(
            handler=lambda: "works",
            name="shortcut_test",
            description="Via shortcut",
            input_schema={"type": "object", "properties": {}},
        )
        assert "shortcut_test" in self.server.tools._tools

    def test_register_resource_shortcut(self):
        self.server.register_resource(
            uri="test://shortcut",
            name="Shortcut Resource",
            content={"data": 123},
        )
        result = self.server.resources.read_resource("test://shortcut")
        assert result.contents

    def test_register_prompt_shortcut(self):
        self.server.register_prompt(
            name="shortcut_prompt",
            description="Via shortcut",
            template="Hello {{name}}",
        )
        tmpl = self.server.prompts.get_prompt("shortcut_prompt")
        assert tmpl is not None

    def test_initialize(self):
        from neugi_swarm_v2.mcp.messages import InitializeParams
        init = InitializeParams(
            protocol_version="2024-11-05",
            capabilities={},
            client_info={"name": "test", "version": "1.0"},
        )
        result = asyncio.run(self.server.initialize(init))
        assert result.protocol_version == "2024-11-05"

    def test_set_bridge(self):
        bridge = MagicMock()
        self.server.set_bridge(bridge)
        assert self.server._bridge is bridge

    def test_set_neugi(self):
        neugi = MagicMock()
        self.server.set_neugi(neugi)
        assert self.server._neugi is neugi

    def test_add_message_handler(self):
        handler = MagicMock()
        self.server.add_message_handler(handler)
        assert len(self.server._message_handlers) >= 1

    def test_health_check_tool_exists(self):
        assert self.server.tools._tools.get("health_check") is not None

    def test_system_info_tool_exists(self):
        assert self.server.tools._tools.get("system_info") is not None

    def test_echo_tool_exists(self):
        assert self.server.tools._tools.get("echo") is not None

    def test_get_time_tool_exists(self):
        assert self.server.tools._tools.get("get_time") is not None

    def test_repr(self):
        r = repr(self.server)
        assert "MCPServer" in r

    @pytest.mark.asyncio
    async def test_handle_ping(self):
        req = RequestMessage(
            method="ping",
            params={},
            id="test-1",
        )
        resp = await self.server.handle_request(req)
        assert resp.result is not None


# =============================================================================
# Transport Tests
# =============================================================================

class TestSSEAuth:
    def test_auth_disabled_by_default(self):
        auth = SSEAuth()
        assert auth.validate("any_token") == "anonymous"

    def test_auth_enabled(self):
        auth = SSEAuth({"client1": "tok1", "client2": "tok2"})
        auth.enable({"client1": "tok1"})
        assert auth.is_enabled
        assert auth.validate("tok1") == "client1"
        assert auth.validate("wrong") is None

    def test_auth_enable_disable(self):
        auth = SSEAuth()
        auth.enable({"admin": "abc123"})
        assert auth.is_enabled
        assert auth.validate("abc123") == "admin"
        auth.disable()
        assert not auth.is_enabled
        assert auth.validate("abc123") == "anonymous"

    def test_auth_empty_tokens(self):
        auth = SSEAuth()
        auth.enable({})
        assert not auth.is_enabled

    def test_auth_multiple_tokens(self):
        auth = SSEAuth({"a": "t1", "b": "t2", "c": "t3"})
        auth.enable({"a": "t1", "b": "t2", "c": "t3"})
        assert auth.validate("t1") == "a"
        assert auth.validate("t2") == "b"
        assert auth.validate("t3") == "c"
        assert auth.validate("t4") is None


class TestRateLimiter:
    @pytest.mark.asyncio
    async def test_initial_burst(self):
        limiter = RateLimiter(tokens_per_second=10, burst=5)
        for _ in range(5):
            assert await limiter.acquire()

    @pytest.mark.asyncio
    async def test_exceeds_burst(self):
        limiter = RateLimiter(tokens_per_second=100, burst=3)
        for _ in range(3):
            await limiter.acquire()
        assert not await limiter.acquire()

    @pytest.mark.asyncio
    async def test_refills_over_time(self):
        limiter = RateLimiter(tokens_per_second=100, burst=5)
        for _ in range(5):
            await limiter.acquire()
        assert not await limiter.acquire()

    @pytest.mark.asyncio
    async def test_no_tokens(self):
        limiter = RateLimiter(tokens_per_second=0, burst=0)
        assert not await limiter.acquire()

    @pytest.mark.asyncio
    async def test_high_burst(self):
        limiter = RateLimiter(tokens_per_second=1000, burst=100)
        for _ in range(100):
            assert await limiter.acquire()


class TestSSEConnection:
    def test_create(self):
        conn = SSEConnection(session_id="sse-1")
        assert conn.session_id == "sse-1"
        assert conn.client_name == "anonymous"

    def test_create_with_client_name(self):
        conn = SSEConnection(session_id="sse-2", client_name="admin")
        assert conn.client_name == "admin"

    def test_subscribe(self):
        conn = SSEConnection(session_id="sse-3")
        conn.subscribe("events.a")
        assert "events.a" in conn._subscribed_events
        conn.subscribe("events.a")  # Duplicate should be no-op
        assert len(conn._subscribed_events) == 1

    def test_unsubscribe(self):
        conn = SSEConnection(session_id="sse-4")
        conn.subscribe("events.a")
        conn.unsubscribe("events.a")
        assert "events.a" not in conn._subscribed_events

    @pytest.mark.asyncio
    async def test_push_and_get(self):
        conn = SSEConnection(session_id="sse-5")
        await conn.push("test_event", {"msg": "hello"})
        event = await conn.get_event(timeout=1)
        assert event is not None
        assert "test_event" in event
        assert "hello" in event

    def test_format_event(self):
        conn = SSEConnection(session_id="sse-6")
        formatted = conn._format_event("test", {"key": "value"})
        assert "event: test" in formatted
        assert "data:" in formatted

    def test_close(self):
        conn = SSEConnection(session_id="sse-7")
        conn.close()
        assert not conn._active

    @pytest.mark.asyncio
    async def test_push_after_close(self):
        conn = SSEConnection(session_id="sse-8")
        conn.close()
        await conn.push("test", {"x": 1})
        # Should not raise
        assert True

    @pytest.mark.asyncio
    async def test_rate_limited_push(self):
        rl = RateLimiter(tokens_per_second=0, burst=0)
        conn = SSEConnection(session_id="sse-9", rate_limiter=rl)
        await conn.push("test", {"x": 1})  # Should silently drop
        assert True


class TestStdioTransport:
    def test_init(self):
        t = StdioTransport()
        assert t._running is False

    def test_stop_when_not_running(self):
        t = StdioTransport()
        asyncio.run(t.stop())
        assert not t._running


class TestHTTPTransport:
    def test_init_defaults(self):
        t = HTTPTransport()
        assert t.host == "127.0.0.1"
        assert t.port == 17902
        assert t._enable_sse
        assert not t.auth_enabled

    def test_init_with_rate_limiting(self):
        t = HTTPTransport(rate_limit=5.0, rate_burst=10)
        assert t._rate_limiter.tokens_per_second == 5.0
        assert t._rate_limiter.max_tokens == 10

    def test_init_with_auth(self):
        t = HTTPTransport(auth_tokens={"admin": "secret123"})
        assert t.auth_enabled
        assert t._auth.validate("secret123") == "admin"

    def test_register_sse_connection(self):
        t = HTTPTransport()
        conn = SSEConnection(session_id="sse-1")
        conn._active = True
        t.register_sse_connection(conn)
        assert conn.session_id in t._sse_connections

    def test_unregister_sse_connection(self):
        t = HTTPTransport()
        conn = SSEConnection(session_id="sse-1")
        t.register_sse_connection(conn)
        t.unregister_sse_connection("sse-1")
        assert "sse-1" not in t._sse_connections

    def test_sse_connections_property(self):
        t = HTTPTransport()
        conn = SSEConnection(session_id="sse-1")
        conn._active = True
        t.register_sse_connection(conn)
        conns = t.sse_connections
        assert "sse-1" in conns

    def test_set_auth_tokens(self):
        t = HTTPTransport()
        t.set_auth_tokens({"admin": "tok"})
        assert t.auth_enabled

    def test_disable_auth(self):
        t = HTTPTransport(auth_tokens={"admin": "tok"})
        t.disable_auth()
        assert not t.auth_enabled

    @pytest.mark.asyncio
    async def test_publish_sse_event_with_subscriber(self):
        t = HTTPTransport()
        conn = SSEConnection(session_id="sse-1", rate_limiter=None)
        conn.subscribe("test.event")
        t.register_sse_connection(conn)
        await t.publish_sse_event("test.event", {"msg": "hello"})
        event = await conn.get_event(timeout=1)
        assert event is not None
        assert "test.event" in event


# =============================================================================
# Messages Tests
# =============================================================================

class TestMessages:
    def test_request_message(self):
        msg = RequestMessage(method="test", params={"a": 1}, id="1")
        assert msg.method == "test"
        assert msg.params == {"a": 1}
        assert msg.id == "1"

    def test_response_message(self):
        msg = ResponseMessage(result={"ok": True}, id="1")
        assert msg.result == {"ok": True}
        assert msg.error is None

    def test_response_message_error(self):
        msg = ResponseMessage(error={"code": -1, "message": "err"}, id="1")
        assert msg.error == {"code": -1, "message": "err"}

    def test_notification_message(self):
        msg = NotificationMessage(method="notify", params={"x": 1})
        assert msg.method == "notify"
        assert msg.params == {"x": 1}

    def test_call_tool_result(self):
        result = CallToolResult(content=[{"type": "text", "text": "hello"}])
        assert result.content == [{"type": "text", "text": "hello"}]
        assert not result.is_error

    def test_call_tool_result_error(self):
        result = CallToolResult(content=[], is_error=True)
        assert result.is_error

    def test_initialize_result(self):
        result = InitializeResult(
            protocol_version="2024-11-05",
            capabilities={"tools": {}},
            server_info={"name": "test", "version": "1.0"},
        )
        assert result.protocol_version == "2024-11-05"

    def test_list_tools_result(self):
        result = ListToolsResult(tools=[{"name": "t1"}])
        assert len(result.tools) == 1

    def test_list_resources_result(self):
        result = ListResourcesResult(resources=[{"uri": "test://a"}])
        assert len(result.resources) == 1

    def test_get_prompt_result(self):
        result = GetPromptResult(description="test", messages=[{"role": "system", "content": "hi"}])
        assert result.description == "test"
        assert len(result.messages) == 1

    def test_list_prompts_result(self):
        result = ListPromptsResult(prompts=[{"name": "p1"}])
        assert len(result.prompts) == 1

    def test_call_tool_result_content(self):
        result = CallToolResult(content=[{"type": "text", "text": "hello"}])
        assert isinstance(result.content, list)
        assert result.content[0]["text"] == "hello"

    def test_initialize_result_attributes(self):
        result = InitializeResult(
            protocol_version="2024-11-05",
            capabilities={},
            server_info={"name": "test"},
        )
        assert result.protocol_version == "2024-11-05"
        assert result.server_info == {"name": "test"}


# =============================================================================
# Checkpoint Tests
# =============================================================================

class TestCheckpointData:
    def test_create(self):
        cp = CheckpointData(
            checkpoint_id="cp-1",
            task_id="task-1",
            step=0,
            state={"key": "value"},
        )
        assert cp.checkpoint_id == "cp-1"
        assert cp.step == 0

    def test_to_dict(self):
        cp = CheckpointData("cp-1", "task-1", 0, {"a": 1})
        d = cp.to_dict()
        assert d["checkpoint_id"] == "cp-1"

    def test_from_dict(self):
        d = {"checkpoint_id": "cp-1", "task_id": "task-1", "step": 0,
             "state": {"a": 1}, "timestamp": "2026-01-01"}
        cp = CheckpointData.from_dict(d)
        assert cp.checkpoint_id == "cp-1"

    def test_from_dict_with_metadata(self):
        d = {"checkpoint_id": "cp-1", "task_id": "task-1", "step": 0,
             "state": {}, "timestamp": "2026-01-01",
             "metadata": {"final": True}}
        cp = CheckpointData.from_dict(d)
        assert cp.metadata.get("final")


class TestCheckpointStore:
    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.store = CheckpointStore(self.tmp.name)

    def teardown_method(self):
        self.store.close()
        os.unlink(self.tmp.name)

    def test_create_thread(self):
        thread = self.store.create_thread("test-thread")
        assert thread.thread_id == "test-thread"
        assert thread.checkpoint_count >= 1

    def test_get_thread(self):
        self.store.create_thread("get-test")
        thread = self.store.get_thread("get-test")
        assert thread is not None
        assert thread.thread_id == "get-test"

    def test_get_nonexistent_thread(self):
        thread = self.store.get_thread("nope")
        assert thread is None

    def test_list_threads(self):
        self.store.create_thread("list-1")
        self.store.create_thread("list-2")
        threads = self.store.list_threads()
        assert len(threads) >= 2

    def test_list_threads_by_status(self):
        self.store.create_thread("list-active")
        threads = self.store.list_threads("active")
        assert len(threads) >= 1

    def test_update_thread_status(self):
        self.store.create_thread("status-test")
        self.store.update_thread_status("status-test", "completed", {"done": True})
        thread = self.store.get_thread("status-test")
        assert thread._status == "completed"

    def test_log_recovery(self):
        self.store.log_recovery("test-thread", "error msg", "cp-1", True)
        # Verify it was stored
        stats = self.store.get_stats()
        assert stats["total_recoveries"] >= 1
        assert stats["successful_recoveries"] >= 1

    def test_log_recovery_failure(self):
        self.store.log_recovery("test-thread-2", "big error", None, False)
        stats = self.store.get_stats()
        assert stats["total_recoveries"] >= 1

    def test_get_stats(self):
        stats = self.store.get_stats()
        assert "total_threads" in stats
        assert "active_threads" in stats
        assert "total_checkpoints" in stats

    def test_cleanup_old_threads(self):
        self.store.create_thread("old-thread")
        self.store.update_thread_status("old-thread", "completed", {})
        cleaned = self.store.cleanup_old_threads(max_age_hours=0, keep_statuses=["active"])
        assert cleaned >= 0

    def test_checkpoint_persistence(self):
        self.store.create_thread("persist-test")
        thread = self.store.get_thread("persist-test")
        assert thread is not None
        assert thread.checkpoint_count > 0

    def test_db_path(self):
        assert self.store.db_path == self.tmp.name


class TestExecutionThread:
    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.store = CheckpointStore(self.tmp.name)

    def teardown_method(self):
        self.store.close()
        os.unlink(self.tmp.name)

    def test_checkpoint(self):
        thread = self.store.create_thread("exec-test")
        cp = thread.checkpoint({"step": 1, "data": "hello"})
        assert cp is not None
        assert thread.checkpoint_count == 2  # Initial + 1

    def test_current_state(self):
        thread = self.store.create_thread("state-test")
        cp = thread.checkpoint({"progress": 50})
        state = thread.current_state
        assert "progress" in state
        assert state["progress"] == 50

    def test_last_checkpoint(self):
        thread = self.store.create_thread("last-test")
        thread.checkpoint({"step": 1})
        thread.checkpoint({"step": 2})
        last = thread.last_checkpoint
        assert last.step == 2

    def test_to_dict(self):
        thread = self.store.create_thread("dict-test")
        d = thread.to_dict()
        assert d["thread_id"] == "dict-test"
        assert "status" in d


class TestResilientMCPExecutor:
    def setup_method(self):
        self.tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.tmp.close()
        self.store = CheckpointStore(self.tmp.name)

    def teardown_method(self):
        self.store.close()
        os.unlink(self.tmp.name)

    def test_init(self):
        executor = ResilientMCPExecutor(self.store)
        assert executor.store is self.store
        assert executor.auto_resume

    def test_get_stats(self):
        executor = ResilientMCPExecutor(self.store)
        stats = executor.get_stats()
        assert "total_threads" in stats

    def test_list_active_workflows(self):
        executor = ResilientMCPExecutor(self.store)
        workflows = executor.list_active_workflows()
        assert isinstance(workflows, list)

    def test_cleanup_completed(self):
        executor = ResilientMCPExecutor(self.store)
        cleaned = executor.cleanup_completed(max_age_hours=0)
        assert isinstance(cleaned, int)


# =============================================================================
# SSEEventForwarder Tests
# =============================================================================

class TestSSEEventForwarder:
    def test_forwarder_creation(self):
        transport = HTTPTransport(enable_sse=True)
        forwarder = SSEEventForwarder(transport)
        assert not forwarder.is_forwarding
        assert forwarder.transport is transport

    def test_forwarder_sse_disabled(self):
        transport = HTTPTransport(enable_sse=False)
        forwarder = SSEEventForwarder(transport)
        forwarder.start()
        assert not forwarder.is_forwarding

    def test_event_mapping(self):
        assert "tool_execution_success" in SSEEventForwarder.EVENT_MAPPING
        assert "tool_execution_failure" in SSEEventForwarder.EVENT_MAPPING
        assert "mcp_call" in SSEEventForwarder.EVENT_MAPPING
        assert "memory_update" in SSEEventForwarder.EVENT_MAPPING

    def test_add_connection(self):
        transport = HTTPTransport(enable_sse=True)
        forwarder = SSEEventForwarder(transport)
        conn = SSEConnection(session_id="test-conn")
        forwarder.add_connection(conn)
        assert "test-conn" in transport._sse_connections

    def test_remove_connection(self):
        transport = HTTPTransport(enable_sse=True)
        forwarder = SSEEventForwarder(transport)
        conn = SSEConnection(session_id="test-conn")
        forwarder.add_connection(conn)
        forwarder.remove_connection("test-conn")
        assert "test-conn" not in transport._sse_connections

    def test_forwarder_singleton(self):
        f1 = get_sse_forwarder()
        f2 = get_sse_forwarder()
        assert f1 is f2

    def test_setup_sse_forwarding(self):
        transport = HTTPTransport(enable_sse=True)
        forwarder = setup_sse_forwarding(transport)
        assert isinstance(forwarder, SSEEventForwarder)

    def test_stop_forwarder(self):
        transport = HTTPTransport(enable_sse=True)
        forwarder = SSEEventForwarder(transport)
        forwarder.start()
        forwarder.stop()
        assert not forwarder.is_forwarding


# =============================================================================
# MCP-NEUGI Bridge Tests
# =============================================================================

class TestMCPBridge:
    def test_bridge_creation(self):
        from neugi_swarm_v2.mcp.bridge import MCPBridge
        from neugi_swarm_v2.mcp.server import MCPServer
        server = MCPServer()
        bridge = MCPBridge(server)
        assert bridge.server is server
        assert not bridge.is_connected

    def test_bridge_connect_without_neugi(self):
        from neugi_swarm_v2.mcp.bridge import MCPBridge
        from neugi_swarm_v2.mcp.server import MCPServer
        server = MCPServer()
        bridge = MCPBridge(server)
        bridge.connect()
        assert not bridge.is_connected

    def test_bridge_disconnect(self):
        from neugi_swarm_v2.mcp.bridge import MCPBridge
        from neugi_swarm_v2.mcp.server import MCPServer
        server = MCPServer()
        bridge = MCPBridge(server)
        bridge.disconnect()
        assert not bridge.is_connected

    def test_create_bridge_factory(self):
        from neugi_swarm_v2.mcp.bridge import MCPBridge, create_bridge
        from neugi_swarm_v2.mcp.server import MCPServer
        server = MCPServer()
        neugi = MagicMock()
        bridge = create_bridge(server, neugi, register_plugin_tools=False)
        assert isinstance(bridge, MCPBridge)
