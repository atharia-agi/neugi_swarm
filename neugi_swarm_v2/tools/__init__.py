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

from tools.tool_registry import (
    ToolRegistry,
    ToolSchema,
    ToolCategory,
    ToolMetadata,
    ToolStats,
    ToolHealth,
    ToolNotFoundError,
    ToolAlreadyRegisteredError,
    ToolDeprecatedError,
)
from tools.tool_composer import (
    ToolComposer,
    SequentialComposer,
    ParallelComposer,
    ConditionalComposer,
    LoopComposer,
    CompositionResult,
    CompositionType,
    CompositionValidationError,
)
from tools.tool_generator import (
    ToolGenerator,
    GeneratedTool,
    ToolQualityReport,
    APISpecParser,
    PatternObserver,
    ToolQualityError,
)
from tools.tool_executor import (
    ToolExecutor,
    ExecutionResult,
    ExecutionTrace,
    CacheBackend,
    RateLimiter,
    CircuitBreaker,
    ExecutionError,
    TimeoutError,
    CircuitOpenError,
    RateLimitExceededError,
)
from tools.builtins import (
    register_builtin_tools,
    WebTools,
    CodeTools,
    FileTools,
    DataTools,
    CommTools,
    SystemTools,
    AITools,
    GitTools,
    DockerTools,
    SecurityTools,
)
from tools.web_search import (
    WebSearch,
    WebSearchConfig,
    SearchResult,
    WebSearchError,
)
from tools.browser import (
    BrowserTool,
    BrowserConfig,
    BrowserAction,
    DOMElement,
    BrowserToolError,
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
