"""
Tool composition engine for NEUGI v2.

Enables composing multiple tools into meta-tools with sequential, parallel,
conditional, and loop patterns. Includes validation and visualization.
"""

import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Tuple,
    Union,
)

from tools.tool_registry import (
    ToolCategory,
    ToolRegistry,
    ToolSchema,
    ToolNotFoundError,
)
from tools.tool_executor import ToolExecutor, ExecutionResult

logger = logging.getLogger(__name__)


class CompositionType(str, Enum):
    """Types of tool composition."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    LOOP = "loop"


@dataclass
class CompositionResult:
    """Result of a composed tool execution."""

    composition_name: str
    composition_type: CompositionType
    success: bool
    result: Any = None
    error: Optional[str] = None
    step_results: List[ExecutionResult] = field(default_factory=list)
    total_latency_ms: float = 0.0
    steps_executed: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "composition_name": self.composition_name,
            "composition_type": self.composition_type.value,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "step_results": [
                {
                    "tool": r.tool_name,
                    "success": r.success,
                    "result": r.result,
                    "error": r.error,
                    "latency_ms": r.latency_ms,
                }
                for r in self.step_results
            ],
            "total_latency_ms": self.total_latency_ms,
            "steps_executed": self.steps_executed,
        }


class CompositionValidationError(Exception):
    """Raised when a composition fails validation."""

    pass


class ToolComposer:
    """
    Base class for tool composition.

    Provides validation, visualization, and common composition logic.
    """

    def __init__(self, registry: ToolRegistry, executor: ToolExecutor):
        self.registry = registry
        self.executor = executor
        self._composed_tools: Dict[str, Dict[str, Any]] = {}

    def validate_composition(
        self,
        name: str,
        tool_names: List[str],
        composition_type: CompositionType,
    ) -> List[str]:
        """
        Validate a composition before creation.

        Checks:
        - All tools exist in registry
        - No circular dependencies
        - Schema compatibility for sequential compositions

        Args:
            name: Composition name.
            tool_names: List of tool names to compose.
            composition_type: Type of composition.

        Returns:
            List of validation errors (empty if valid).

        Raises:
            CompositionValidationError: If validation fails critically.
        """
        errors = []

        for tool_name in tool_names:
            try:
                self.registry.get_tool(tool_name)
            except ToolNotFoundError:
                errors.append(f"Tool '{tool_name}' not found in registry")

        if not tool_names:
            errors.append("At least one tool is required for composition")

        if len(tool_names) != len(set(tool_names)):
            errors.append("Duplicate tools in composition")

        if errors:
            raise CompositionValidationError(
                f"Composition '{name}' validation failed: {'; '.join(errors)}"
            )

        return errors

    def register_composed_tool(
        self,
        name: str,
        func: Callable,
        composition_type: CompositionType,
        tool_names: List[str],
        description: str = "",
        parameters: Optional[Dict[str, Dict[str, Any]]] = None,
        required_params: Optional[List[str]] = None,
    ) -> ToolSchema:
        """
        Register a composed tool in the registry.

        Args:
            name: Name for the composed tool.
            func: Callable implementing the composition.
            composition_type: Type of composition.
            tool_names: List of constituent tool names.
            description: Human-readable description.
            parameters: Parameter schema.
            required_params: Required parameter names.

        Returns:
            ToolSchema for the composed tool.
        """
        self._composed_tools[name] = {
            "type": composition_type,
            "tools": tool_names,
            "description": description,
        }

        schema = self.registry.register_tool(
            name=name,
            func=func,
            category=ToolCategory.COMPOSED,
            description=description or f"Composed tool ({composition_type.value}): {', '.join(tool_names)}",
            parameters=parameters or {},
            required_params=required_params or [],
            source="composed",
            tags=[f"composed:{composition_type.value}"] + tool_names,
        )
        return schema

    def visualize_composition(
        self,
        name: str,
        tool_names: List[str],
        composition_type: CompositionType,
        conditions: Optional[Dict[str, str]] = None,
    ) -> str:
        """
        Generate a text-based flow diagram of a composition.

        Args:
            name: Composition name.
            tool_names: List of tool names.
            composition_type: Type of composition.
            conditions: Optional condition descriptions for conditional compositions.

        Returns:
            Text-based flow diagram string.
        """
        lines = []
        lines.append(f"╔{'═' * 60}╗")
        lines.append(f"║  Composition: {name:<43}║")
        lines.append(f"║  Type: {composition_type.value:<50}║")
        lines.append(f"╠{'═' * 62}╣")

        if composition_type == CompositionType.SEQUENTIAL:
            for i, tool in enumerate(tool_names):
                connector = "  │" if i < len(tool_names) - 1 else "  "
                lines.append(f"  ▼ [{tool}]")
                if i < len(tool_names) - 1:
                    lines.append(f"  │")
                    lines.append(f"  │ (output → input)")
                    lines.append(f"  ▼")

        elif composition_type == CompositionType.PARALLEL:
            lines.append("  ┌─────────────────────────────────────┐")
            for tool in tool_names:
                lines.append(f"  │  [{tool}]  (parallel)            │")
            lines.append("  └─────────────────────────────────────┘")
            lines.append("  │")
            lines.append("  ▼ (merge results)")

        elif composition_type == CompositionType.CONDITIONAL:
            for i, tool in enumerate(tool_names):
                condition = conditions.get(tool, "default") if conditions else "default"
                if i == 0:
                    lines.append(f"  ▼ [{tool}] (condition: {condition})")
                else:
                    lines.append(f"  │")
                    lines.append(f"  ├─ [{tool}] (else if: {condition})")
            lines.append(f"  │")
            lines.append(f"  └─ (fallback)")

        elif composition_type == CompositionType.LOOP:
            lines.append("  ┌─────────────────────────────────────┐")
            lines.append("  │                                     │")
            for tool in tool_names:
                lines.append(f"  │  [{tool}]                         │")
            lines.append("  │                                     │")
            lines.append("  │  (repeat until condition met)       │")
            lines.append("  └─────────────────────────────────────┘")

        lines.append(f"╚{'═' * 60}╝")
        return "\n".join(lines)

    def get_composition_info(self, name: str) -> Optional[Dict[str, Any]]:
        """Get information about a composed tool."""
        return self._composed_tools.get(name)

    def list_compositions(self) -> Dict[str, Dict[str, Any]]:
        """List all registered compositions."""
        return dict(self._composed_tools)


class SequentialComposer(ToolComposer):
    """
    Sequential composition: output of tool A becomes input of tool B.

    Example:
        >>> composer = SequentialComposer(registry, executor)
        >>> composer.compose(
        ...     "fetch_and_parse",
        ...     ["web_fetch", "data_parse_json"],
        ...     param_mapping={"web_fetch.url": "input_url", "data_parse_json.data": "web_fetch.result"},
        ... )
    """

    def compose(
        self,
        name: str,
        tool_names: List[str],
        param_mapping: Optional[Dict[str, str]] = None,
        description: str = "",
        parameters: Optional[Dict[str, Dict[str, Any]]] = None,
        required_params: Optional[List[str]] = None,
    ) -> ToolSchema:
        """
        Create a sequential composition.

        Args:
            name: Name for the composed tool.
            tool_names: Ordered list of tool names.
            param_mapping: Maps tool parameters to previous results.
                          Format: {"tool_name.param": "prev_tool.result" or "input.param"}
            description: Human-readable description.
            parameters: Input parameter schema.
            required_params: Required input parameters.

        Returns:
            ToolSchema for the composed tool.
        """
        self.validate_composition(name, tool_names, CompositionType.SEQUENTIAL)

        def sequential_func(**kwargs) -> Dict[str, Any]:
            results = {}
            step_results = []

            for tool_name in tool_names:
                tool_kwargs = {}
                if param_mapping:
                    for key, source in param_mapping.items():
                        if key.startswith(f"{tool_name}."):
                            param_name = key[len(tool_name) + 1:]
                            if source.startswith("input."):
                                input_param = source[len("input."):]
                                tool_kwargs[param_name] = kwargs.get(input_param)
                            elif source.endswith(".result"):
                                prev_tool = source.rsplit(".", 1)[0]
                                if prev_tool in results:
                                    tool_kwargs[param_name] = results[prev_tool]

                exec_result = self.executor.execute(tool_name, **tool_kwargs)
                step_results.append(exec_result)

                if not exec_result.success:
                    return {
                        "success": False,
                        "error": f"Tool '{tool_name}' failed: {exec_result.error}",
                        "results": results,
                        "step_results": step_results,
                    }

                results[tool_name] = exec_result.result

            return {
                "success": True,
                "results": results,
                "final_result": results.get(tool_names[-1]),
                "step_results": step_results,
            }

        return self.register_composed_tool(
            name=name,
            func=sequential_func,
            composition_type=CompositionType.SEQUENTIAL,
            tool_names=tool_names,
            description=description or f"Sequential: {' → '.join(tool_names)}",
            parameters=parameters or {"input": {"type": "dict", "description": "Input parameters"}},
            required_params=required_params or [],
        )


class ParallelComposer(ToolComposer):
    """
    Parallel composition: run multiple tools simultaneously, merge results.

    Example:
        >>> composer = ParallelComposer(registry, executor)
        >>> composer.compose(
        ...     "multi_search",
        ...     ["web_search", "code_search", "data_search"],
        ...     merge_strategy="combine",
        ...     query="search term",
        ... )
    """

    def compose(
        self,
        name: str,
        tool_names: List[str],
        merge_strategy: str = "dict",
        description: str = "",
        parameters: Optional[Dict[str, Dict[str, Any]]] = None,
        required_params: Optional[List[str]] = None,
    ) -> ToolSchema:
        """
        Create a parallel composition.

        Args:
            name: Name for the composed tool.
            tool_names: List of tool names to run in parallel.
            merge_strategy: How to merge results ('dict', 'list', 'first_success').
            description: Human-readable description.
            parameters: Input parameter schema.
            required_params: Required input parameters.

        Returns:
            ToolSchema for the composed tool.
        """
        self.validate_composition(name, tool_names, CompositionType.PARALLEL)

        def parallel_func(**kwargs) -> Dict[str, Any]:
            import concurrent.futures

            step_results = []
            results = {}
            errors = []

            def run_tool(tool_name: str) -> ExecutionResult:
                return self.executor.execute(tool_name, **kwargs)

            with concurrent.futures.ThreadPoolExecutor(
                max_workers=len(tool_names)
            ) as executor:
                future_to_tool = {
                    executor.submit(run_tool, tool_name): tool_name
                    for tool_name in tool_names
                }

                for future in concurrent.futures.as_completed(future_to_tool):
                    tool_name = future_to_tool[future]
                    try:
                        exec_result = future.result()
                        step_results.append(exec_result)
                        if exec_result.success:
                            results[tool_name] = exec_result.result
                        else:
                            errors.append(
                                f"{tool_name}: {exec_result.error}"
                            )
                    except Exception as e:
                        errors.append(f"{tool_name}: {str(e)}")
                        step_results.append(
                            ExecutionResult(
                                tool_name=tool_name,
                                success=False,
                                error=str(e),
                            )
                        )

            if merge_strategy == "dict":
                merged = results
            elif merge_strategy == "list":
                merged = list(results.values())
            elif merge_strategy == "first_success":
                merged = next(iter(results.values()), None)
            else:
                merged = results

            return {
                "success": len(results) > 0,
                "results": results,
                "merged": merged,
                "errors": errors,
                "step_results": step_results,
            }

        return self.register_composed_tool(
            name=name,
            func=parallel_func,
            composition_type=CompositionType.PARALLEL,
            tool_names=tool_names,
            description=description or f"Parallel: [{', '.join(tool_names)}]",
            parameters=parameters or {"input": {"type": "dict", "description": "Input parameters"}},
            required_params=required_params or [],
        )


class ConditionalComposer(ToolComposer):
    """
    Conditional composition: if tool A succeeds, run B; else run C.

    Example:
        >>> composer = ConditionalComposer(registry, executor)
        >>> composer.compose(
        ...     "smart_fetch",
        ...     primary="web_fetch",
        ...     on_success="data_parse_json",
        ...     on_failure="data_parse_html",
        ...     condition=lambda r: r.get("status_code") == 200,
        ... )
    """

    def compose(
        self,
        name: str,
        primary: str,
        on_success: Optional[str] = None,
        on_failure: Optional[str] = None,
        condition: Optional[Callable[[Any], bool]] = None,
        description: str = "",
        parameters: Optional[Dict[str, Dict[str, Any]]] = None,
        required_params: Optional[List[str]] = None,
    ) -> ToolSchema:
        """
        Create a conditional composition.

        Args:
            name: Name for the composed tool.
            primary: Primary tool to run first.
            on_success: Tool to run if primary succeeds (and condition is met).
            on_failure: Tool to run if primary fails.
            condition: Optional callable to evaluate primary result.
            description: Human-readable description.
            parameters: Input parameter schema.
            required_params: Required input parameters.

        Returns:
            ToolSchema for the composed tool.
        """
        tool_names = [primary]
        if on_success:
            tool_names.append(on_success)
        if on_failure:
            tool_names.append(on_failure)

        self.validate_composition(name, tool_names, CompositionType.CONDITIONAL)

        def conditional_func(**kwargs) -> Dict[str, Any]:
            step_results = []

            primary_result = self.executor.execute(primary, **kwargs)
            step_results.append(primary_result)

            if primary_result.success:
                if condition and not condition(primary_result.result):
                    return {
                        "success": True,
                        "branch": "condition_false",
                        "primary_result": primary_result.result,
                        "step_results": step_results,
                    }
                if on_success:
                    secondary_result = self.executor.execute(
                        on_success, input=primary_result.result, **kwargs
                    )
                    step_results.append(secondary_result)
                    return {
                        "success": secondary_result.success,
                        "branch": "success",
                        "primary_result": primary_result.result,
                        "secondary_result": secondary_result.result,
                        "step_results": step_results,
                    }
                return {
                    "success": True,
                    "branch": "success",
                    "primary_result": primary_result.result,
                    "step_results": step_results,
                }
            else:
                if on_failure:
                    fallback_result = self.executor.execute(
                        on_failure, error=primary_result.error, **kwargs
                    )
                    step_results.append(fallback_result)
                    return {
                        "success": fallback_result.success,
                        "branch": "failure",
                        "primary_error": primary_result.error,
                        "fallback_result": fallback_result.result,
                        "step_results": step_results,
                    }
                return {
                    "success": False,
                    "branch": "failure",
                    "primary_error": primary_result.error,
                    "step_results": step_results,
                }

        return self.register_composed_tool(
            name=name,
            func=conditional_func,
            composition_type=CompositionType.CONDITIONAL,
            tool_names=tool_names,
            description=description or f"Conditional: {primary} → (success: {on_success}, failure: {on_failure})",
            parameters=parameters or {"input": {"type": "dict", "description": "Input parameters"}},
            required_params=required_params or [],
        )


class LoopComposer(ToolComposer):
    """
    Loop composition: run tool(s) until a condition is met.

    Example:
        >>> composer = LoopComposer(registry, executor)
        >>> composer.compose(
        ...     "retry_until_ready",
        ...     ["check_status"],
        ...     condition=lambda r: r.get("status") == "ready",
        ...     max_iterations=10,
        ...     delay_between=1.0,
        ... )
    """

    def compose(
        self,
        name: str,
        tool_names: List[str],
        condition: Callable[[Any], bool],
        max_iterations: int = 10,
        delay_between: float = 0.0,
        description: str = "",
        parameters: Optional[Dict[str, Dict[str, Any]]] = None,
        required_params: Optional[List[str]] = None,
    ) -> ToolSchema:
        """
        Create a loop composition.

        Args:
            name: Name for the composed tool.
            tool_names: Tools to run in each iteration.
            condition: Callable that returns True to stop looping.
            max_iterations: Maximum number of iterations.
            delay_between: Seconds to wait between iterations.
            description: Human-readable description.
            parameters: Input parameter schema.
            required_params: Required input parameters.

        Returns:
            ToolSchema for the composed tool.
        """
        self.validate_composition(name, tool_names, CompositionType.LOOP)

        def loop_func(**kwargs) -> Dict[str, Any]:
            all_results = []
            iteration = 0
            last_result = None

            while iteration < max_iterations:
                iteration += 1
                iteration_results = []

                for tool_name in tool_names:
                    exec_result = self.executor.execute(tool_name, **kwargs)
                    iteration_results.append(exec_result)

                    if not exec_result.success:
                        return {
                            "success": False,
                            "error": f"Tool '{tool_name}' failed on iteration {iteration}",
                            "iterations": iteration,
                            "results": all_results,
                            "step_results": all_results + iteration_results,
                        }

                    last_result = exec_result.result

                all_results.extend(iteration_results)

                if condition(last_result):
                    return {
                        "success": True,
                        "iterations": iteration,
                        "final_result": last_result,
                        "results": all_results,
                        "step_results": all_results,
                    }

                if delay_between > 0 and iteration < max_iterations:
                    import time
                    time.sleep(delay_between)

            return {
                "success": False,
                "error": f"Max iterations ({max_iterations}) reached",
                "iterations": iteration,
                "final_result": last_result,
                "results": all_results,
                "step_results": all_results,
            }

        return self.register_composed_tool(
            name=name,
            func=loop_func,
            composition_type=CompositionType.LOOP,
            tool_names=tool_names,
            description=description or f"Loop: {' → '.join(tool_names)} (max {max_iterations} iterations)",
            parameters=parameters or {"input": {"type": "dict", "description": "Input parameters"}},
            required_params=required_params or [],
        )
