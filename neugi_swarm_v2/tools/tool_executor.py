"""
Advanced tool executor for NEUGI v2.

Provides retry with exponential backoff, timeout handling, result caching,
rate limiting, circuit breakers, result transformation, and execution tracing.
"""

import hashlib
import json
import logging
import threading
import time
from collections import OrderedDict, deque
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import (
    Any,
)

from observability import get_event_bus
from tools.tool_registry import ToolComplexity, ToolRegistry

try:
    from security import (
        CommandValidator,
        ExecutionSandbox,
        SandboxViolation,
    )
except ImportError:
    ExecutionSandbox = None  # type: ignore
    SandboxViolation = None  # type: ignore
    CommandValidator = None  # type: ignore

try:
    from governance import ApprovalGate
except ImportError:
    ApprovalGate = None  # type: ignore

try:
    from governance.budget import BudgetTracker
except ImportError:
    BudgetTracker = None  # type: ignore

logger = logging.getLogger(__name__)


@dataclass
class ExecutionResult:
    """Result of a tool execution."""

    tool_name: str
    success: bool
    result: Any = None
    error: str | None = None
    latency_ms: float = 0.0
    cached: bool = False
    retries: int = 0
    trace_id: str = ""

    def __repr__(self) -> str:
        status = "OK" if self.success else "FAIL"
        return f"ExecutionResult({self.tool_name}, {status}, {self.latency_ms:.1f}ms)"


@dataclass
class ExecutionTrace:
    """Full trace of an execution chain."""

    trace_id: str
    root_tool: str
    steps: list[dict[str, Any]] = field(default_factory=list)
    total_latency_ms: float = 0.0
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None

    def add_step(
        self,
        tool_name: str,
        success: bool,
        latency_ms: float,
        error: str | None = None,
        cached: bool = False,
        retries: int = 0,
    ) -> None:
        """Add a step to the trace."""
        self.steps.append(
            {
                "tool": tool_name,
                "success": success,
                "latency_ms": latency_ms,
                "error": error,
                "cached": cached,
                "retries": retries,
                "timestamp": time.time(),
            }
        )
        self.total_latency_ms += latency_ms

    def complete(self) -> None:
        """Mark trace as complete."""
        self.completed_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        """Convert trace to dictionary."""
        return {
            "trace_id": self.trace_id,
            "root_tool": self.root_tool,
            "steps": self.steps,
            "total_latency_ms": self.total_latency_ms,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
        }


class ExecutionError(Exception):
    """Base exception for execution failures."""

    def __init__(self, tool_name: str, message: str, cause: Exception | None = None):
        self.tool_name = tool_name
        self.cause = cause
        super().__init__(f"Tool '{tool_name}' failed: {message}")


class TimeoutError(ExecutionError):
    """Raised when a tool execution exceeds its timeout."""

    pass


class CircuitOpenError(ExecutionError):
    """Raised when a tool's circuit breaker is open."""

    pass


class RateLimitExceededError(ExecutionError):
    """Raised when a tool's rate limit is exceeded."""

    pass


class CacheBackend:
    """
    Result cache with LRU eviction and TTL support.

    Example:
        >>> cache = CacheBackend(max_size=1000, default_ttl=60)
        >>> cache.set("key1", "value1")
        >>> cache.get("key1")
        'value1'
    """

    def __init__(self, max_size: int = 10000, default_ttl: float = 300.0):
        self._cache: OrderedDict = OrderedDict()
        self._expiry: dict[str, float] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._lock = threading.Lock()
        self._hits = 0
        self._misses = 0

    def _make_key(self, tool_name: str, args: tuple, kwargs: dict) -> str:
        """Create a cache key from tool name and arguments."""
        key_data = json.dumps(
            {"tool": tool_name, "args": args, "kwargs": kwargs},
            sort_keys=True,
            default=str,
        )
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]

    def get(self, tool_name: str, args: tuple, kwargs: dict) -> tuple[bool, Any]:
        """
        Get a cached result.

        Returns:
            (hit, value) tuple.
        """
        key = self._make_key(tool_name, args, kwargs)
        with self._lock:
            if key not in self._cache:
                self._misses += 1
                return False, None
            if key in self._expiry and time.time() > self._expiry[key]:
                del self._cache[key]
                del self._expiry[key]
                self._misses += 1
                return False, None
            self._cache.move_to_end(key)
            self._hits += 1
            return True, self._cache[key]

    def set(
        self, tool_name: str, args: tuple, kwargs: dict, value: Any, ttl: float | None = None
    ) -> None:
        """Cache a result with optional TTL."""
        key = self._make_key(tool_name, args, kwargs)
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = value
            self._expiry[key] = time.time() + (ttl or self._default_ttl)
            if len(self._cache) > self._max_size:
                oldest_key, _ = self._cache.popitem(last=False)
                self._expiry.pop(oldest_key, None)

    def clear(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            self._cache.clear()
            self._expiry.clear()

    def invalidate(self, tool_name: str) -> None:
        """Invalidate all cache entries for a tool."""
        with self._lock:
            keys_to_remove = []
            for key in self._cache:
                if key.startswith(hashlib.sha256(tool_name.encode()).hexdigest()[:8]):
                    keys_to_remove.append(key)
            for key in keys_to_remove:
                del self._cache[key]
                self._expiry.pop(key, None)

    @property
    def hit_rate(self) -> float:
        """Get cache hit rate."""
        total = self._hits + self._misses
        return self._hits / total if total > 0 else 0.0

    @property
    def size(self) -> int:
        """Get current cache size."""
        return len(self._cache)


class RateLimiter:
    """
    Per-tool rate limiter using sliding window.

    Example:
        >>> limiter = RateLimiter()
        >>> limiter.set_limit("tool1", 10)
        >>> limiter.check("tool1")  # True if allowed
    """

    def __init__(self) -> None:
        self._limits: dict[str, int] = {}
        self._windows: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def set_limit(self, tool_name: str, calls_per_minute: int) -> None:
        """Set rate limit for a tool."""
        with self._lock:
            self._limits[tool_name] = calls_per_minute
            if tool_name not in self._windows:
                from collections import deque
                self._windows[tool_name] = deque()

    def check(self, tool_name: str) -> bool:
        """
        Check if a call is allowed under the rate limit.

        Returns:
            True if allowed, False if rate limited.
        """
        with self._lock:
            limit = self._limits.get(tool_name, 60)
            if tool_name not in self._windows:
                from collections import deque
                self._windows[tool_name] = deque()

            window = self._windows[tool_name]
            now = time.time()
            cutoff = now - 60.0

            while window and window[0] < cutoff:
                window.popleft()

            if len(window) >= limit:
                return False

            window.append(now)
            return True

    def get_wait_time(self, tool_name: str) -> float:
        """Get seconds to wait before next allowed call."""
        with self._lock:
            if tool_name not in self._windows:
                return 0.0
            window = self._windows[tool_name]
            if not window:
                return 0.0
            limit = self._limits.get(tool_name, 60)
            if len(window) < limit:
                return 0.0
            return window[0] + 60.0 - time.time()

    def reset(self, tool_name: str) -> None:
        """Reset rate limit window for a tool."""
        with self._lock:
            if tool_name in self._windows:
                self._windows[tool_name].clear()


class CircuitBreaker:
    """
    Circuit breaker for tool execution.

    States: CLOSED (normal) -> OPEN (failing) -> HALF_OPEN (testing)

    Example:
        >>> cb = CircuitBreaker(failure_threshold=5, recovery_timeout=30)
        >>> cb.record_failure("tool1")
        >>> cb.is_open("tool1")  # True after 5 failures
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        half_open_max_calls: int = 1,
    ):
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max_calls = half_open_max_calls
        self._states: dict[str, str] = {}
        self._failure_counts: dict[str, int] = {}
        self._last_failure_time: dict[str, float] = {}
        self._half_open_calls: dict[str, int] = {}
        self._lock = threading.Lock()

    def is_open(self, tool_name: str) -> bool:
        """Check if circuit is open for a tool."""
        with self._lock:
            state = self._states.get(tool_name, self.CLOSED)
            if state == self.CLOSED:
                return False
            if state == self.OPEN:
                last_failure = self._last_failure_time.get(tool_name, 0)
                if time.time() - last_failure >= self._recovery_timeout:
                    self._states[tool_name] = self.HALF_OPEN
                    self._half_open_calls[tool_name] = 0
                    return False
                return True
            if state == self.HALF_OPEN:
                calls = self._half_open_calls.get(tool_name, 0)
                return calls >= self._half_open_max_calls
            return False

    def record_success(self, tool_name: str) -> None:
        """Record a successful call."""
        with self._lock:
            state = self._states.get(tool_name, self.CLOSED)
            if state == self.HALF_OPEN:
                self._states[tool_name] = self.CLOSED
                self._failure_counts[tool_name] = 0
            elif state == self.CLOSED:
                self._failure_counts[tool_name] = 0

    def record_failure(self, tool_name: str) -> None:
        """Record a failed call."""
        with self._lock:
            state = self._states.get(tool_name, self.CLOSED)
            if state == self.HALF_OPEN:
                self._states[tool_name] = self.OPEN
                self._last_failure_time[tool_name] = time.time()
            else:
                self._failure_counts[tool_name] = (
                    self._failure_counts.get(tool_name, 0) + 1
                )
                self._last_failure_time[tool_name] = time.time()
                if self._failure_counts[tool_name] >= self._failure_threshold:
                    self._states[tool_name] = self.OPEN

    def get_state(self, tool_name: str) -> str:
        """Get current circuit state."""
        with self._lock:
            return self._states.get(tool_name, self.CLOSED)

    def reset(self, tool_name: str) -> None:
        """Reset circuit breaker for a tool."""
        with self._lock:
            self._states.pop(tool_name, None)
            self._failure_counts.pop(tool_name, None)
            self._last_failure_time.pop(tool_name, None)
            self._half_open_calls.pop(tool_name, None)


class ToolExecutor:
    """
    Advanced tool executor with retry, caching, rate limiting, and circuit breakers.

    Example:
        >>> registry = ToolRegistry()
        >>> executor = ToolExecutor(registry)
        >>> result = executor.execute("my_tool", param1="value1")
        >>> print(result.success, result.result)
    """

    def __init__(
        self,
        registry: ToolRegistry,
        max_retries: int = 3,
        base_backoff: float = 0.1,
        max_backoff: float = 10.0,
        cache_enabled: bool = True,
        cache_ttl: float = 300.0,
        cache_max_size: int = 10000,
        circuit_failure_threshold: int = 5,
        circuit_recovery_timeout: float = 30.0,
        capability_profile: Any | None = None,
        sandbox: Any | None = None,
        command_validator: Any | None = None,
        approval_gate: Any | None = None,
        budget_tracker: BudgetTracker | None = None,
    ):
        self.registry = registry
        self.capability_profile = capability_profile
        self.sandbox = sandbox
        self.command_validator = command_validator
        self.approval_gate = approval_gate
        self.budget_tracker = budget_tracker
        self.cache_enabled = cache_enabled
        self.cache = CacheBackend(max_size=cache_max_size, default_ttl=cache_ttl)
        self.rate_limiter = RateLimiter()
        self._traces: dict[str, ExecutionTrace] = {}
        self._transformers: dict[str, Callable] = {}
        self._lock = threading.Lock()

        # Adapt execution parameters based on model capability
        adapted = self._adapt_execution_params(
            max_retries, base_backoff, max_backoff,
            circuit_failure_threshold, circuit_recovery_timeout,
        )
        self.max_retries = adapted["max_retries"]
        self.base_backoff = adapted["base_backoff"]
        self.max_backoff = adapted["max_backoff"]
        self.circuit_breaker = CircuitBreaker(
            failure_threshold=adapted["circuit_failure_threshold"],
            recovery_timeout=adapted["circuit_recovery_timeout"],
        )

    def _adapt_execution_params(
        self,
        max_retries: int,
        base_backoff: float,
        max_backoff: float,
        circuit_failure_threshold: int,
        circuit_recovery_timeout: float,
    ) -> dict[str, Any]:
        """Adapt execution parameters based on model capability profile.

        LOCAL tier: fail fast, low retries (weak models struggle with recovery)
        MEDIUM tier: balanced
        CLOUD tier: more retries, longer recovery (complex tools worth retrying)
        """
        if self.capability_profile is None:
            return {
                "max_retries": max_retries,
                "base_backoff": base_backoff,
                "max_backoff": max_backoff,
                "circuit_failure_threshold": circuit_failure_threshold,
                "circuit_recovery_timeout": circuit_recovery_timeout,
            }

        tier = getattr(self.capability_profile, "tier", None)
        tier_value = tier.value if hasattr(tier, "value") else str(tier) if tier else "medium"

        if tier_value == "local":
            return {
                "max_retries": 1,
                "base_backoff": 0.05,
                "max_backoff": 2.0,
                "circuit_failure_threshold": 3,
                "circuit_recovery_timeout": 15.0,
            }
        elif tier_value == "cloud":
            return {
                "max_retries": max(3, max_retries),
                "base_backoff": base_backoff,
                "max_backoff": max_backoff,
                "circuit_failure_threshold": circuit_failure_threshold,
                "circuit_recovery_timeout": circuit_recovery_timeout,
            }
        else:
            return {
                "max_retries": max_retries,
                "base_backoff": base_backoff,
                "max_backoff": max_backoff,
                "circuit_failure_threshold": circuit_failure_threshold,
                "circuit_recovery_timeout": circuit_recovery_timeout,
            }

    def set_rate_limit(self, tool_name: str, calls_per_minute: int) -> None:
        """Set rate limit for a tool."""
        self.rate_limiter.set_limit(tool_name, calls_per_minute)

    def set_transformer(self, tool_name: str, transformer: Callable) -> None:
        """
        Set a result transformer for a tool.

        The transformer receives the raw result and returns a transformed result.
        """
        self._transformers[tool_name] = transformer

    def _adapt_timeout(self, base_timeout: float, complexity: Any) -> float:
        """Adapt tool timeout based on model capability and tool complexity.

        LOCAL tier: shorter timeouts for complex tools (fail fast)
        CLOUD tier: longer timeouts for complex tools (worth waiting)
        """
        if self.capability_profile is None:
            return base_timeout

        tier = getattr(self.capability_profile, "tier", None)
        tier_value = tier.value if hasattr(tier, "value") else str(tier) if tier else "medium"
        complexity_value = complexity.value if hasattr(complexity, "value") else str(complexity)

        if tier_value == "local":
            # Fail fast on complex tools
            if complexity_value in ("complex", "strategic"):
                return min(base_timeout, 10.0)
            return min(base_timeout, 15.0)
        elif tier_value == "cloud":
            # More patience for complex tools on capable models
            if complexity_value == "strategic":
                return max(base_timeout, 60.0)
            if complexity_value == "complex":
                return max(base_timeout, 45.0)
            return base_timeout
        return base_timeout

    def execute(
        self,
        tool_name: str,
        trace_id: str | None = None,
        timeout_override: float | None = None,
        skip_cache: bool = False,
        **kwargs,
    ) -> ExecutionResult:
        """
        Execute a tool with all advanced features.

        Args:
            tool_name: Name of the tool to execute.
            trace_id: Optional trace ID for execution tracing.
            timeout_override: Override tool's default timeout.
            skip_cache: Skip cache lookup and storage.
            **kwargs: Tool parameters.

        Returns:
            ExecutionResult with outcome.
        """
        start_time = time.time()
        retries = 0
        last_error = None

        try:
            metadata = self.registry.get_tool(tool_name)
            schema = metadata.schema
            func = metadata.func

            if schema.deprecated:
                logger.warning(
                    f"Calling deprecated tool '{tool_name}': {schema.deprecation_message}"
                )

            errors = schema.validate_params(kwargs)
            if errors:
                return ExecutionResult(
                    tool_name=tool_name,
                    success=False,
                    error=f"Parameter validation failed: {'; '.join(errors)}",
                    latency_ms=(time.time() - start_time) * 1000,
                    trace_id=trace_id or "",
                )

            # -- Security: Approval Gate (complex/strategic tools) ----------
            if self.approval_gate and schema.complexity in (ToolComplexity.COMPLEX, ToolComplexity.STRATEGIC):
                try:
                    from governance.approval import RiskLevel
                    needs_approval, _ = self.approval_gate.requires_approval(
                        action_type=tool_name,
                        risk_level=RiskLevel.HIGH,
                    )
                    if needs_approval:
                        request = self.approval_gate.request_approval(
                            agent_id="neugi",
                            action=tool_name,
                            description=f"Tool '{tool_name}' (complexity: {schema.complexity.value}) requires approval",
                            risk_level=RiskLevel.HIGH,
                        )
                        if hasattr(request, "status") and request.status.value != "auto_approved":
                            logger.warning("Approval required for tool %s (request: %s)", tool_name, getattr(request, "request_id", "?"))
                            return ExecutionResult(
                                tool_name=tool_name,
                                success=False,
                                error=f"Approval required for '{tool_name}'. Request ID: {getattr(request, 'request_id', '?')}",
                                latency_ms=(time.time() - start_time) * 1000,
                                trace_id=trace_id or "",
                            )
                except Exception as e:
                    logger.warning("Approval gate check failed for %s: %s", tool_name, e)

            # -- Governance: Budget check -----------------------------------
            if self.budget_tracker:
                try:
                    budget_id = "default"
                    if not self.budget_tracker.can_spend(budget_id, tokens=0, cost=0.0):
                        logger.warning("Budget exceeded for tool %s", tool_name)
                        return ExecutionResult(
                            tool_name=tool_name,
                            success=False,
                            error="Budget exceeded",
                            latency_ms=(time.time() - start_time) * 1000,
                            trace_id=trace_id or "",
                        )
                except ValueError:
                    # Budget ID does not exist — skip check gracefully
                    logger.debug("Budget '%s' not configured, skipping budget check", "default")
                except Exception as e:
                    logger.warning("Budget check failed for %s: %s", tool_name, e)

            # -- Security: Command Validator (subprocess-based tools) -------
            if self.command_validator and tool_name in ("system_execute_command", "docker_run", "docker_exec", "docker_compose_up"):
                try:
                    command = kwargs.get("command", "")
                    if command:
                        verdict = self.command_validator.validate(str(command))
                        if hasattr(verdict, "is_safe") and not verdict.is_safe:
                            explanation = getattr(verdict, "explanation", "Command validation failed")
                            logger.warning("Command validator blocked %s: %s", tool_name, explanation)
                            return ExecutionResult(
                                tool_name=tool_name,
                                success=False,
                                error=f"Command blocked: {explanation}",
                                latency_ms=(time.time() - start_time) * 1000,
                                trace_id=trace_id or "",
                            )
                except Exception as e:
                    logger.warning("Command validation failed for %s: %s", tool_name, e)

            if self.circuit_breaker.is_open(tool_name):
                raise CircuitOpenError(
                    tool_name,
                    f"Circuit breaker is open for tool '{tool_name}'",
                )

            if not self.rate_limiter.check(tool_name):
                raise RateLimitExceededError(
                    tool_name,
                    f"Rate limit exceeded for tool '{tool_name}'",
                )

            if self.cache_enabled and schema.cacheable and not skip_cache:
                hit, cached_result = self.cache.get(tool_name, (), kwargs)
                if hit:
                    latency = (time.time() - start_time) * 1000
                    self.registry.record_stats(tool_name, latency, True)
                    self.circuit_breaker.record_success(tool_name)
                    return ExecutionResult(
                        tool_name=tool_name,
                        success=True,
                        result=cached_result,
                        latency_ms=latency,
                        cached=True,
                        trace_id=trace_id or "",
                    )

            # Adapt timeout based on tool complexity and model capability
            base_timeout = timeout_override or schema.timeout_seconds
            timeout = self._adapt_timeout(base_timeout, schema.complexity)
            result = None

            # -- Security: ExecutionSandbox (subprocess-based tools) --------
            sandbox_executed = False
            if self.sandbox and tool_name in ("system_execute_command", "docker_run", "docker_exec", "docker_compose_up"):
                try:
                    command = self._build_command_for_sandbox(tool_name, kwargs)
                    if command:
                        sb_result = self.sandbox.execute(command, timeout=timeout)
                        result = {
                            "stdout": sb_result.stdout,
                            "stderr": sb_result.stderr,
                            "returncode": sb_result.returncode,
                            "killed": sb_result.killed,
                            "kill_reason": sb_result.kill_reason,
                        }
                        sandbox_executed = True
                except SandboxViolation as e:
                    logger.warning("Sandbox blocked %s: %s", tool_name, e)
                    return ExecutionResult(
                        tool_name=tool_name,
                        success=False,
                        error=f"Sandbox blocked: {e}",
                        latency_ms=(time.time() - start_time) * 1000,
                        trace_id=trace_id or "",
                    )
                except Exception as e:
                    logger.warning("Sandbox execution failed for %s: %s", tool_name, e)

            if not sandbox_executed:
                for attempt in range(self.max_retries + 1):
                    try:
                        result = self._execute_with_timeout(func, kwargs, timeout)
                        break
                    except Exception as e:
                        last_error = str(e)
                        retries = attempt
                        if attempt < self.max_retries:
                            backoff = min(
                                self.base_backoff * (2**attempt), self.max_backoff
                            )
                            time.sleep(backoff)
                            logger.warning(
                                f"Tool '{tool_name}' attempt {attempt + 1} failed: {e}, "
                                f"retrying in {backoff:.2f}s"
                            )

            if result is None and last_error:
                raise ExecutionError(tool_name, last_error)

            if tool_name in self._transformers:
                result = self._transformers[tool_name](result)

            latency = (time.time() - start_time) * 1000

            if self.cache_enabled and schema.cacheable and not skip_cache:
                self.cache.set(tool_name, (), kwargs, result)

            self.registry.record_stats(tool_name, latency, True)
            self.circuit_breaker.record_success(tool_name)

            exec_result = ExecutionResult(
                tool_name=tool_name,
                success=True,
                result=result,
                latency_ms=latency,
                retries=retries,
                trace_id=trace_id or "",
            )

            if trace_id:
                self._record_trace_step(trace_id, tool_name, True, latency, retries=retries)

            # Publish successful tool execution event
            event_bus = get_event_bus()
            event_bus.publish(
                "tool_execution_success",
                {
                    "tool_name": tool_name,
                    "latency_ms": latency,
                    "retries": retries,
                    "trace_id": trace_id,
                    "result_type": type(result).__name__ if result is not None else "None"
                },
                source="tool_executor"
            )

            return exec_result

        except (CircuitOpenError, RateLimitExceededError) as e:
            latency = (time.time() - start_time) * 1000
            self.registry.record_stats(tool_name, latency, False, str(e))
            # Publish tool execution failure event
            event_bus = get_event_bus()
            event_bus.publish(
                "tool_execution_failure",
                {
                    "tool_name": tool_name,
                    "error": str(e),
                    "latency_ms": latency,
                    "retries": retries,
                    "trace_id": trace_id,
                    "failure_type": type(e).__name__
                },
                source="tool_executor"
            )
            return ExecutionResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
                latency_ms=latency,
                retries=retries,
                trace_id=trace_id or "",
            )

        except ExecutionError as e:
            latency = (time.time() - start_time) * 1000
            self.registry.record_stats(tool_name, latency, False, str(e))
            self.circuit_breaker.record_failure(tool_name)
            # Publish tool execution failure event
            event_bus = get_event_bus()
            event_bus.publish(
                "tool_execution_failure",
                {
                    "tool_name": tool_name,
                    "error": str(e),
                    "latency_ms": latency,
                    "retries": retries,
                    "trace_id": trace_id,
                    "failure_type": type(e).__name__
                },
                source="tool_executor"
            )
            return ExecutionResult(
                tool_name=tool_name,
                success=False,
                error=str(e),
                latency_ms=latency,
                retries=retries,
                trace_id=trace_id or "",
            )

        except Exception as e:
            latency = (time.time() - start_time) * 1000
            logger.error(
                "Unexpected error executing tool '%s' (kwargs=%s): %s",
                tool_name, list(kwargs.keys()), e,
            )
            self.registry.record_stats(tool_name, latency, False, str(e))
            self.circuit_breaker.record_failure(tool_name)
            # Publish tool execution failure event
            event_bus = get_event_bus()
            event_bus.publish(
                "tool_execution_failure",
                {
                    "tool_name": tool_name,
                    "error": str(e),
                    "latency_ms": latency,
                    "retries": retries,
                    "trace_id": trace_id,
                    "failure_type": type(e).__name__
                },
                source="tool_executor"
            )
            return ExecutionResult(
                tool_name=tool_name,
                success=False,
                error=f"Unexpected error: {str(e)}",
                latency_ms=latency,
                retries=retries,
                trace_id=trace_id or "",
            )

    def _execute_with_timeout(
        self, func: Callable, kwargs: dict[str, Any], timeout: float
    ) -> Any:
        """Execute a function with a timeout."""
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func, **kwargs)
            try:
                return future.result(timeout=timeout)
            except concurrent.futures.TimeoutError as e:
                raise TimeoutError(
                    "unknown",
                    f"Tool execution timed out after {timeout}s",
                ) from e

    def _build_command_for_sandbox(
        self, tool_name: str, kwargs: dict[str, Any]
    ) -> list[str] | None:
        """Build a command list for sandbox execution from tool kwargs.

        Args:
            tool_name: Name of the tool.
            kwargs: Tool parameters.

        Returns:
            Command list for sandbox.execute(), or None if not applicable.
        """
        if tool_name == "system_execute_command":
            command = kwargs.get("command", "")
            shell = kwargs.get("shell", False)
            if shell:
                return ["sh", "-c", str(command)]
            if isinstance(command, list):
                return [str(c) for c in command]
            if isinstance(command, str):
                return command.split()
            return None

        if tool_name == "docker_run":
            image = kwargs.get("image", "")
            cmd = kwargs.get("command", "")
            args = kwargs.get("args", [])
            command = ["docker", "run"]
            if kwargs.get("detached"):
                command.append("-d")
            if kwargs.get("remove"):
                command.append("--rm")
            command.append(str(image))
            if cmd:
                command.append(str(cmd))
            command.extend([str(a) for a in args])
            return command

        if tool_name == "docker_exec":
            container = kwargs.get("container", "")
            cmd = kwargs.get("command", "")
            return ["docker", "exec", str(container), str(cmd)]

        if tool_name == "docker_compose_up":
            file_path = kwargs.get("file", "docker-compose.yml")
            return ["docker-compose", "-f", str(file_path), "up", "-d"]

        return None

    def execute_batch(
        self,
        calls: list[tuple[str, dict[str, Any]]],
        trace_id: str | None = None,
    ) -> list[ExecutionResult]:
        """
        Execute multiple tools in sequence.

        Args:
            calls: List of (tool_name, kwargs) tuples.
            trace_id: Optional trace ID.

        Returns:
            List of ExecutionResult objects.
        """
        results = []
        for tool_name, kwargs in calls:
            result = self.execute(tool_name, trace_id=trace_id, **kwargs)
            results.append(result)
            if not result.success:
                break
        return results

    def create_trace(self, root_tool: str) -> ExecutionTrace:
        """Create a new execution trace."""
        import uuid
        trace_id = str(uuid.uuid4())[:8]
        trace = ExecutionTrace(trace_id=trace_id, root_tool=root_tool)
        with self._lock:
            self._traces[trace_id] = trace
        return trace

    def _record_trace_step(
        self,
        trace_id: str,
        tool_name: str,
        success: bool,
        latency_ms: float,
        error: str | None = None,
        cached: bool = False,
        retries: int = 0,
    ):
        """Record a step in an execution trace."""
        with self._lock:
            if trace_id in self._traces:
                self._traces[trace_id].add_step(
                    tool_name, success, latency_ms, error, cached, retries
                )

    def get_trace(self, trace_id: str) -> ExecutionTrace | None:
        """Get an execution trace by ID."""
        return self._traces.get(trace_id)

    def get_all_traces(self) -> dict[str, ExecutionTrace]:
        """Get all execution traces."""
        return dict(self._traces)

    def clear_cache(self) -> None:
        """Clear the result cache."""
        self.cache.clear()

    def reset_circuit(self, tool_name: str) -> None:
        """Reset circuit breaker for a tool."""
        self.circuit_breaker.reset(tool_name)

    def get_cache_stats(self) -> dict[str, Any]:
        """Get cache statistics."""
        return {
            "size": self.cache.size,
            "hit_rate": self.cache.hit_rate,
            "enabled": self.cache_enabled,
        }
