"""
NEUGI v2 Hook System - Lifecycle event interception and processing.

Provides a hook system for intercepting system events with support for
priority-based ordering, chaining, abort, context passing, and timeout
protection.

Usage:
    hooks = HookManager()
    hooks.register("pre_tool_call", my_handler, priority=10)
    result = hooks.fire("pre_tool_call", context={"tool": "search"})
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


# -- Hook events --------------------------------------------------------------

class HookEvent(str, Enum):
    """
    Standard hook event types in the NEUGI v2 system.

    Plugins can register handlers for any of these events to intercept
    and modify system behavior.
    """

    # Tool call lifecycle
    PRE_TOOL_CALL = "pre_tool_call"
    """Fired before a tool is called. Can modify args or abort."""

    POST_TOOL_CALL = "post_tool_call"
    """Fired after a tool returns. Can modify result."""

    # Response lifecycle
    PRE_RESPONSE = "pre_response"
    """Fired before a response is sent to the user."""

    POST_RESPONSE = "post_response"
    """Fired after a response is sent."""

    # Error handling
    ON_ERROR = "on_error"
    """Fired when an error occurs in the system."""

    # Memory events
    ON_MEMORY_SAVE = "on_memory_save"
    """Fired when a memory entry is saved."""

    # Session lifecycle
    ON_SESSION_START = "on_session_start"
    """Fired when a new session begins."""

    ON_SESSION_END = "on_session_end"
    """Fired when a session ends."""


# -- Hook priority ------------------------------------------------------------

class HookPriority:
    """
    Standard priority levels for hook execution order.

    Lower numbers execute first. Use these constants for clarity.
    """

    CRITICAL = -100
    """Critical hooks that must run first (security, validation)."""

    HIGH = -10
    """High priority hooks (authentication, rate limiting)."""

    NORMAL = 0
    """Default priority for most hooks."""

    LOW = 10
    """Low priority hooks (logging, analytics)."""

    CLEANUP = 100
    """Cleanup hooks that run last."""


# -- Hook context -------------------------------------------------------------

@dataclass
class HookContext:
    """
    Context passed between hooks in a chain.

    Hooks can read and modify the data dict to pass information
    to subsequent hooks. The abort flag stops further processing.

    Attributes:
        event: The hook event name.
        data: Mutable dict shared between all hooks in the chain.
        abort: If True, stop processing further hooks.
        abort_reason: Reason for aborting (set when abort=True).
        result: The final result value (set by hooks that produce output).
        metadata: Immutable metadata about the event.
    """

    event: str
    data: dict[str, Any] = field(default_factory=dict)
    abort: bool = False
    abort_reason: str = ""
    result: Any = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def abort_processing(self, reason: str = "") -> None:
        """
        Signal that no further hooks should process this event.

        Args:
            reason: Human-readable reason for aborting.
        """
        self.abort = True
        self.abort_reason = reason
        logger.debug("Hook chain aborted for %s: %s", self.event, reason)

    def get(self, key: str, default: Any = None) -> Any:
        """Get a value from the shared data dict."""
        return self.data.get(key, default)

    def set(self, key: str, value: Any) -> None:
        """Set a value in the shared data dict."""
        self.data[key] = value


# -- Hook result --------------------------------------------------------------

@dataclass
class HookResult:
    """
    Result of firing a hook chain.

    Attributes:
        event: The hook event name.
        success: Whether all hooks executed successfully.
        aborted: Whether the chain was aborted.
        abort_reason: Reason for abort (if aborted).
        handlers_executed: Number of handlers that ran.
        handlers_failed: Number of handlers that raised exceptions.
        total_time: Total execution time in seconds.
        errors: List of error messages from failed handlers.
        final_context: The HookContext after all handlers ran.
    """

    event: str
    success: bool = True
    aborted: bool = False
    abort_reason: str = ""
    handlers_executed: int = 0
    handlers_failed: int = 0
    total_time: float = 0.0
    errors: list[str] = field(default_factory=list)
    final_context: Optional[HookContext] = None

    @property
    def was_aborted(self) -> bool:
        """Whether the hook chain was aborted."""
        return self.aborted

    @property
    def had_errors(self) -> bool:
        """Whether any handlers failed."""
        return self.handlers_failed > 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dict."""
        return {
            "event": self.event,
            "success": self.success,
            "aborted": self.aborted,
            "abort_reason": self.abort_reason,
            "handlers_executed": self.handlers_executed,
            "handlers_failed": self.handlers_failed,
            "total_time": round(self.total_time, 4),
            "errors": self.errors,
        }


# -- Hook registration entry --------------------------------------------------

@dataclass
class HookEntry:
    """
    A single registered hook handler.

    Attributes:
        event: The event this hook listens to.
        handler: The callable to invoke.
        priority: Execution priority (lower = earlier).
        plugin_name: Name of the plugin that registered this hook.
        timeout: Maximum execution time in seconds.
        enabled: Whether the hook is currently active.
    """

    event: str
    handler: Callable
    priority: int = HookPriority.NORMAL
    plugin_name: str = "system"
    timeout: float = 10.0
    enabled: bool = True

    def __lt__(self, other: object) -> bool:
        """Sort by priority (lower first)."""
        if not isinstance(other, HookEntry):
            return NotImplemented
        return self.priority < other.priority


# -- Hook manager -------------------------------------------------------------

class HookManager:
    """
    Central manager for lifecycle hooks.

    Supports:
    - Registration with priority ordering
    - Chaining (multiple hooks per event)
    - Abort (stop processing mid-chain)
    - Context passing between hooks
    - Timeout protection per handler
    - Enable/disable individual hooks
    - Statistics and monitoring

    Usage:
        hooks = HookManager()
        hooks.register("pre_tool_call", validate_args, priority=HookPriority.HIGH)
        hooks.register("pre_tool_call", log_tool_call, priority=HookPriority.LOW)

        ctx = HookContext("pre_tool_call", data={"tool": "search", "args": {...}})
        result = hooks.fire(ctx)
        if result.aborted:
            print(f"Aborted: {result.abort_reason}")
    """

    def __init__(self, default_timeout: float = 10.0) -> None:
        """
        Initialize the hook manager.

        Args:
            default_timeout: Default timeout for hook handlers in seconds.
        """
        self._hooks: dict[str, list[HookEntry]] = {}
        self._lock = threading.RLock()
        self._default_timeout = default_timeout

        # Statistics
        self._stats: dict[str, dict[str, Any]] = {}

    def register(
        self,
        event: str,
        handler: Callable,
        priority: int = HookPriority.NORMAL,
        plugin_name: str = "system",
        timeout: Optional[float] = None,
    ) -> None:
        """
        Register a hook handler for an event.

        Args:
            event: Hook event name (e.g. "pre_tool_call").
            handler: Callable that takes a HookContext and returns None or modifies context.
            priority: Execution priority (lower = earlier).
            plugin_name: Name of the registering plugin.
            timeout: Maximum execution time in seconds (uses default if None).
        """
        entry = HookEntry(
            event=event,
            handler=handler,
            priority=priority,
            plugin_name=plugin_name,
            timeout=timeout or self._default_timeout,
        )

        with self._lock:
            if event not in self._hooks:
                self._hooks[event] = []
            self._hooks[event].append(entry)
            # Sort by priority
            self._hooks[event].sort()

        # Initialize stats
        with self._lock:
            if event not in self._stats:
                self._stats[event] = {
                    "total_fires": 0,
                    "total_aborts": 0,
                    "total_errors": 0,
                    "total_time": 0.0,
                }

        logger.debug(
            "Registered hook: %s (plugin=%s, priority=%d)",
            event, plugin_name, priority,
        )

    def unregister(
        self,
        event: str,
        handler: Optional[Callable] = None,
        plugin_name: Optional[str] = None,
    ) -> int:
        """
        Unregister hook handlers.

        Args:
            event: Hook event name.
            handler: Specific handler to remove (None to remove all for plugin).
            plugin_name: Remove all hooks for this plugin (None to match any).

        Returns:
            Number of hooks removed.
        """
        with self._lock:
            if event not in self._hooks:
                return 0

            original_count = len(self._hooks[event])

            if handler is not None:
                self._hooks[event] = [
                    h for h in self._hooks[event] if h.handler is not handler
                ]
            elif plugin_name is not None:
                self._hooks[event] = [
                    h for h in self._hooks[event] if h.plugin_name != plugin_name
                ]
            else:
                self._hooks[event] = []

            removed = original_count - len(self._hooks[event])
            return removed

    def unregister_all_for_plugin(self, plugin_name: str) -> int:
        """
        Unregister all hooks for a specific plugin.

        Args:
            plugin_name: Plugin name.

        Returns:
            Total number of hooks removed.
        """
        total = 0
        with self._lock:
            for event in list(self._hooks.keys()):
                before = len(self._hooks[event])
                self._hooks[event] = [
                    h for h in self._hooks[event] if h.plugin_name != plugin_name
                ]
                total += before - len(self._hooks[event])
        return total

    def enable_hook(self, event: str, handler: Callable) -> bool:
        """Enable a specific hook handler."""
        with self._lock:
            for entry in self._hooks.get(event, []):
                if entry.handler is handler:
                    entry.enabled = True
                    return True
        return False

    def disable_hook(self, event: str, handler: Callable) -> bool:
        """Disable a specific hook handler."""
        with self._lock:
            for entry in self._hooks.get(event, []):
                if entry.handler is handler:
                    entry.enabled = False
                    return True
        return False

    def fire(self, context: HookContext) -> HookResult:
        """
        Fire a hook chain for an event.

        Executes all registered handlers in priority order. Stops if
        a handler sets context.abort = True.

        Args:
            context: HookContext with event name and shared data.

        Returns:
            HookResult with execution summary.
        """
        start_time = time.monotonic()
        result = HookResult(event=context.event)

        with self._lock:
            entries = list(self._hooks.get(context.event, []))
            # Update stats
            if context.event in self._stats:
                self._stats[context.event]["total_fires"] += 1

        executed = 0
        failed = 0

        for entry in entries:
            if context.abort:
                result.aborted = True
                result.abort_reason = context.abort_reason
                break

            if not entry.enabled:
                continue

            executed += 1
            try:
                self._execute_handler(entry, context)
            except HookAbortError as e:
                context.abort_processing(str(e))
                result.aborted = True
                result.abort_reason = str(e)
                break
            except Exception as e:
                failed += 1
                error_msg = f"Handler error in {entry.plugin_name}: {e}"
                result.errors.append(error_msg)
                logger.error(error_msg)

                with self._lock:
                    if context.event in self._stats:
                        self._stats[context.event]["total_errors"] += 1

        total_time = time.monotonic() - start_time
        result.handlers_executed = executed
        result.handlers_failed = failed
        result.total_time = total_time
        result.success = failed == 0
        result.final_context = context

        with self._lock:
            if context.event in self._stats:
                self._stats[context.event]["total_time"] += total_time
                if result.aborted:
                    self._stats[context.event]["total_aborts"] += 1

        if result.aborted:
            logger.debug(
                "Hook chain %s aborted after %d handlers (%.4fs): %s",
                context.event, executed, total_time, result.abort_reason,
            )
        else:
            logger.debug(
                "Hook chain %s completed: %d handlers, %d failed (%.4fs)",
                context.event, executed, failed, total_time,
            )

        return result

    def fire_sync(self, event: str, data: Optional[dict[str, Any]] = None, **metadata: Any) -> HookResult:
        """
        Convenience method to fire a hook with inline data.

        Args:
            event: Hook event name.
            data: Initial data dict for the context.
            **metadata: Additional metadata for the context.

        Returns:
            HookResult with execution summary.
        """
        context = HookContext(
            event=event,
            data=data or {},
            metadata=metadata,
        )
        return self.fire(context)

    def _execute_handler(self, entry: HookEntry, context: HookContext) -> None:
        """
        Execute a single hook handler with timeout protection.

        Args:
            entry: The hook entry to execute.
            context: The shared hook context.

        Raises:
            HookAbortError: If the handler times out.
            Exception: Any exception from the handler.
        """
        hook_result: list[Any] = []
        hook_error: list[Exception] = []

        def _target() -> None:
            try:
                handler = entry.handler
                # Handlers can accept 0, 1 (context), or more args
                import inspect
                sig = inspect.signature(handler)
                params = list(sig.parameters.values())

                if len(params) == 0:
                    result = handler()
                elif len(params) == 1:
                    result = handler(context)
                else:
                    result = handler(context)

                hook_result.append(result)
            except Exception as e:
                hook_error.append(e)

        thread = threading.Thread(
            target=_target, daemon=True, name=f"hook-{entry.event}-{entry.plugin_name}"
        )
        thread.start()
        thread.join(timeout=entry.timeout)

        if thread.is_alive():
            raise HookAbortError(
                f"Hook handler timed out after {entry.timeout}s "
                f"(plugin={entry.plugin_name}, event={entry.event})"
            )

        if hook_error:
            raise hook_error[0]

    def get_hooks_for_event(self, event: str) -> list[HookEntry]:
        """Get all registered hooks for an event."""
        with self._lock:
            return list(self._hooks.get(event, []))

    def get_registered_events(self) -> list[str]:
        """Get all events that have registered hooks."""
        with self._lock:
            return list(self._hooks.keys())

    def get_stats(self) -> dict[str, dict[str, Any]]:
        """Get hook execution statistics."""
        with self._lock:
            return {
                event: dict(stats)
                for event, stats in self._stats.items()
            }

    def clear(self) -> None:
        """Clear all registered hooks."""
        with self._lock:
            self._hooks.clear()
            self._stats.clear()
        logger.info("All hooks cleared")


# -- Hook abort exception -----------------------------------------------------

class HookAbortError(Exception):
    """
    Raised by a hook handler to abort the hook chain.

    This is caught by the HookManager and converted into an
    aborted HookResult rather than propagating as an error.
    """

    pass


# -- Convenience decorators ----------------------------------------------------

def hook(event: str, priority: int = HookPriority.NORMAL, timeout: Optional[float] = None):
    """
    Decorator to register a function as a hook handler.

    Usage:
        @hook("pre_tool_call", priority=HookPriority.HIGH)
        def validate_tool_call(ctx: HookContext) -> None:
            if "dangerous" in ctx.data.get("tool", ""):
                ctx.abort_processing("Dangerous tool blocked")

    Note: The decorated function must be registered with HookManager
    manually, or use the HookManager.register() method directly.
    This decorator adds metadata to the function for easier registration.
    """
    def decorator(fn: Callable) -> Callable:
        fn._hook_event = event
        fn._hook_priority = priority
        fn._hook_timeout = timeout
        return fn
    return decorator


def register_hooks_from_module(hook_manager: HookManager, module: Any, plugin_name: str = "system") -> int:
    """
    Auto-register all @hook-decorated functions from a module.

    Args:
        hook_manager: HookManager instance.
        module: Module to scan for decorated functions.
        plugin_name: Plugin name for registration.

    Returns:
        Number of hooks registered.
    """
    count = 0
    for attr_name in dir(module):
        attr = getattr(module, attr_name)
        if callable(attr) and hasattr(attr, "_hook_event"):
            hook_manager.register(
                event=attr._hook_event,
                handler=attr,
                priority=getattr(attr, "_hook_priority", HookPriority.NORMAL),
                plugin_name=plugin_name,
                timeout=getattr(attr, "_hook_timeout", None),
            )
            count += 1
    return count
