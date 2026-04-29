"""
NEUGI v2 Tool Composition Engine.

The most advanced tool system for agentic frameworks — tools that compose
other tools, generate new tools, and self-improve.

Core modules:
    - ToolRegistry: Central registration, discovery, and health monitoring
    - ToolComposer: Sequential, parallel, conditional, and loop composition
    - ToolGenerator: Dynamic tool generation from NL, patterns, and APIs
    - ToolExecutor: Retry, caching, rate limiting, circuit breakers
    - Builtins: 50+ production-ready built-in tools

Example:
    >>> from tools import ToolRegistry, ToolComposer, ToolExecutor
    >>> registry = ToolRegistry()
    >>> registry.register_tool("hello", lambda: "world", category="system")
    >>> executor = ToolExecutor(registry)
    >>> result = executor.execute("hello")
"""

from tools.browser import (
    BrowserAction,
    BrowserConfig,
    BrowserTool,
    BrowserToolError,
    DOMElement,
)
from tools.builtins import (
    AITools,
    CodeTools,
    CommTools,
    DataTools,
    DockerTools,
    FileTools,
    GitTools,
    SecurityTools,
    SystemTools,
    WebTools,
    register_builtin_tools,
)
from tools.tool_composer import (
    CompositionResult,
    CompositionType,
    CompositionValidationError,
    ConditionalComposer,
    LoopComposer,
    ParallelComposer,
    SequentialComposer,
    ToolComposer,
)
from tools.tool_executor import (
    CacheBackend,
    CircuitBreaker,
    CircuitOpenError,
    ExecutionError,
    ExecutionResult,
    ExecutionTrace,
    RateLimiter,
    RateLimitExceededError,
    TimeoutError,
    ToolExecutor,
)
from tools.tool_generator import (
    APISpecParser,
    GeneratedTool,
    PatternObserver,
    ToolGenerator,
    ToolQualityError,
    ToolQualityReport,
)
from tools.tool_registry import (
    ToolAlreadyRegisteredError,
    ToolCategory,
    ToolDeprecatedError,
    ToolHealth,
    ToolMetadata,
    ToolNotFoundError,
    ToolRegistry,
    ToolSchema,
    ToolStats,
)
from tools.web_search import (
    SearchResult,
    WebSearch,
    WebSearchConfig,
    WebSearchError,
)

__all__ = [
    # Registry
    "ToolRegistry",
    "ToolSchema",
    "ToolCategory",
    "ToolMetadata",
    "ToolStats",
    "ToolHealth",
    "ToolNotFoundError",
    "ToolAlreadyRegisteredError",
    "ToolDeprecatedError",
    # Composer
    "ToolComposer",
    "SequentialComposer",
    "ParallelComposer",
    "ConditionalComposer",
    "LoopComposer",
    "CompositionResult",
    "CompositionType",
    "CompositionValidationError",
    # Generator
    "ToolGenerator",
    "GeneratedTool",
    "ToolQualityReport",
    "APISpecParser",
    "PatternObserver",
    "ToolQualityError",
    # Executor
    "ToolExecutor",
    "ExecutionResult",
    "ExecutionTrace",
    "CacheBackend",
    "RateLimiter",
    "CircuitBreaker",
    "ExecutionError",
    "TimeoutError",
    "CircuitOpenError",
    "RateLimitExceededError",
    # Builtins
    "register_builtin_tools",
    "WebTools",
    "CodeTools",
    "FileTools",
    "DataTools",
    "CommTools",
    "SystemTools",
    "AITools",
    "GitTools",
    "DockerTools",
    "SecurityTools",
    # Web Search
    "WebSearch",
    "WebSearchConfig",
    "SearchResult",
    "WebSearchError",
    # Browser
    "BrowserTool",
    "BrowserConfig",
    "BrowserAction",
    "DOMElement",
    "BrowserToolError",
]

__version__ = "2.1.1"
