"""
Dynamic tool generator for NEUGI v2.

Generates tools from natural language descriptions, observed patterns,
and API specifications. Includes quality validation, testing, and documentation.
"""

import ast
import inspect
import json
import re
import time
import logging
import hashlib
from dataclasses import dataclass, field
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
)

from tools.tool_registry import (
    ToolCategory,
    ToolRegistry,
    ToolSchema,
    ToolNotFoundError,
)

logger = logging.getLogger(__name__)


@dataclass
class GeneratedTool:
    """Represents a dynamically generated tool."""

    name: str
    source: str
    description: str
    category: ToolCategory
    code: str
    parameters: Dict[str, Dict[str, Any]]
    required_params: List[str]
    func: Optional[Callable] = None
    quality_report: Optional["ToolQualityReport"] = None
    generated_at: float = field(default_factory=time.time)
    version: str = "1.0.0"

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "source": self.source,
            "description": self.description,
            "category": self.category.value,
            "code": self.code,
            "parameters": self.parameters,
            "required_params": self.required_params,
            "generated_at": self.generated_at,
            "version": self.version,
            "quality": self.quality_report.to_dict() if self.quality_report else None,
        }


@dataclass
class ToolQualityReport:
    """Quality assessment for a generated tool."""

    tool_name: str
    overall_score: float = 0.0
    syntax_valid: bool = False
    safety_score: float = 0.0
    test_coverage: float = 0.0
    documentation_score: float = 0.0
    issues: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    tests_passed: int = 0
    tests_failed: int = 0
    tests_total: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "tool_name": self.tool_name,
            "overall_score": self.overall_score,
            "syntax_valid": self.syntax_valid,
            "safety_score": self.safety_score,
            "test_coverage": self.test_coverage,
            "documentation_score": self.documentation_score,
            "issues": self.issues,
            "warnings": self.warnings,
            "tests_passed": self.tests_passed,
            "tests_failed": self.tests_failed,
            "tests_total": self.tests_total,
        }


class ToolQualityError(Exception):
    """Raised when a generated tool fails quality validation."""

    pass


class PatternObserver:
    """
    Observes tool usage patterns to suggest new tool generation.

    Tracks:
    - Frequently used tool combinations
    - Common parameter patterns
    - Repeated transformation chains
    """

    def __init__(self):
        self._usage_patterns: Dict[str, List[Dict[str, Any]]] = {}
        self._tool_sequences: List[List[str]] = []
        self._param_patterns: Dict[str, Dict[str, Any]] = {}
        self._suggestions: List[Dict[str, Any]] = []

    def record_usage(self, tool_name: str, params: Dict[str, Any], result: Any):
        """Record a tool usage for pattern analysis."""
        if tool_name not in self._usage_patterns:
            self._usage_patterns[tool_name] = []
        self._usage_patterns[tool_name].append(
            {
                "params": params,
                "timestamp": time.time(),
                "result_type": type(result).__name__,
            }
        )

    def record_sequence(self, tool_sequence: List[str]):
        """Record a sequence of tool calls."""
        self._tool_sequences.append(tool_sequence)
        self._analyze_sequences()

    def _analyze_sequences(self):
        """Analyze tool sequences for common patterns."""
        sequence_counts: Dict[str, int] = {}
        for seq in self._tool_sequences:
            key = " → ".join(seq)
            sequence_counts[key] = sequence_counts.get(key, 0) + 1

        self._suggestions = []
        for seq, count in sequence_counts.items():
            if count >= 3:
                tools = seq.split(" → ")
                self._suggestions.append(
                    {
                        "type": "sequential_composition",
                        "tools": tools,
                        "frequency": count,
                        "suggested_name": f"auto_{'_'.join(tools)}",
                    }
                )

    def get_suggestions(self) -> List[Dict[str, Any]]:
        """Get tool generation suggestions based on observed patterns."""
        return self._suggestions

    def get_common_params(self, tool_name: str) -> Dict[str, Any]:
        """Get most common parameters for a tool."""
        if tool_name not in self._usage_patterns:
            return {}
        usages = self._usage_patterns[tool_name]
        param_counts: Dict[str, Dict[str, int]] = {}
        for usage in usages:
            for param, value in usage["params"].items():
                if param not in param_counts:
                    param_counts[param] = {}
                value_str = str(value)
                param_counts[param][value_str] = (
                    param_counts[param].get(value_str, 0) + 1
                )
        common = {}
        for param, values in param_counts.items():
            most_common = max(values, key=values.get)
            common[param] = most_common
        return common


class APISpecParser:
    """
    Parses API specifications (OpenAPI/Swagger) to generate tools.

    Supports:
    - OpenAPI 3.0
    - Swagger 2.0
    - Simplified JSON specs
    """

    def parse_openapi(self, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse an OpenAPI 3.0 specification.

        Args:
            spec: OpenAPI spec dictionary.

        Returns:
            List of tool definitions.
        """
        tools = []
        paths = spec.get("paths", {})

        for path, methods in paths.items():
            for method, operation in methods.items():
                if method not in ("get", "post", "put", "delete", "patch"):
                    continue

                tool = self._operation_to_tool(path, method, operation, spec)
                tools.append(tool)

        return tools

    def parse_swagger(self, spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Parse a Swagger 2.0 specification.

        Args:
            spec: Swagger spec dictionary.

        Returns:
            List of tool definitions.
        """
        tools = []
        paths = spec.get("paths", {})

        for path, methods in paths.items():
            for method, operation in methods.items():
                if method not in ("get", "post", "put", "delete", "patch"):
                    continue

                tool = self._operation_to_tool(path, method, operation, spec)
                tools.append(tool)

        return tools

    def _operation_to_tool(
        self,
        path: str,
        method: str,
        operation: Dict[str, Any],
        spec: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Convert an API operation to a tool definition."""
        operation_id = operation.get("operationId", "")
        summary = operation.get("summary", "")
        description = operation.get("description", summary)

        tool_name = operation_id or f"{method}_{path.strip('/').replace('/', '_').replace('{', '').replace('}', '')}"
        tool_name = re.sub(r"[^a-zA-Z0-9_]", "_", tool_name).lower()

        parameters = {}
        required_params = []

        for param in operation.get("parameters", []):
            param_name = param.get("name", "")
            param_schema = param.get("schema", {})
            param_type = param_schema.get("type", "str")

            if param.get("required", False):
                required_params.append(param_name)

            parameters[param_name] = {
                "type": param_type,
                "description": param.get("description", ""),
                "in": param.get("in", "query"),
            }

        return {
            "name": tool_name,
            "description": description or f"{method.upper()} {path}",
            "category": ToolCategory.WEB,
            "parameters": parameters,
            "required_params": required_params,
            "method": method.upper(),
            "path": path,
            "tags": operation.get("tags", []),
        }


class ToolGenerator:
    """
    Dynamic tool generator for NEUGI v2.

    Generates tools from:
    - Natural language descriptions
    - Observed usage patterns
    - API specifications (OpenAPI/Swagger)

    Includes quality validation, auto-testing, and documentation.

    Example:
        >>> generator = ToolGenerator(registry)
        >>> tool = generator.generate_from_description(
        ...     "A tool that converts Celsius to Fahrenheit",
        ...     category=ToolCategory.DATA,
        ... )
        >>> registry.register_tool(tool.name, tool.func, tool.category, ...)
    """

    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.pattern_observer = PatternObserver()
        self.api_parser = APISpecParser()
        self._generated_tools: Dict[str, GeneratedTool] = {}
        self._safe_builtins = {
            "len", "str", "int", "float", "bool", "list", "dict", "set", "tuple",
            "range", "enumerate", "zip", "map", "filter", "sorted", "reversed",
            "sum", "min", "max", "abs", "round", "pow", "divmod",
            "isinstance", "issubclass", "hasattr", "getattr", "setattr",
            "type", "id", "hash", "repr", "format",
            "True", "False", "None",
        }
        self._safe_modules = {"json", "math", "datetime", "re", "string", "urllib.parse"}
        self._dangerous_patterns = [
            r"\bexec\s*\(",
            r"\beval\s*\(",
            r"\b__import__\s*\(",
            r"\bos\.",
            r"\bsys\.",
            r"\bsubprocess\.",
            r"\bopen\s*\(",
            r"\bimport\s+os\b",
            r"\bimport\s+sys\b",
            r"\bimport\s+subprocess\b",
        ]

    def generate_from_description(
        self,
        description: str,
        category: ToolCategory = ToolCategory.SYSTEM,
        name: Optional[str] = None,
    ) -> GeneratedTool:
        """
        Generate a tool from a natural language description.

        Args:
            description: Natural language description of the tool.
            category: Tool category.
            name: Optional tool name (auto-generated if not provided).

        Returns:
            GeneratedTool with code and metadata.
        """
        if not name:
            name = self._generate_name(description)

        params, required, code = self._parse_description(description, name)

        tool = GeneratedTool(
            name=name,
            source="natural_language",
            description=description,
            category=category,
            code=code,
            parameters=params,
            required_params=required,
        )

        tool.func = self._compile_tool(tool)
        tool.quality_report = self._validate_quality(tool)

        self._generated_tools[name] = tool
        return tool

    def generate_from_pattern(
        self,
        tool_sequence: List[str],
        name: Optional[str] = None,
    ) -> Optional[GeneratedTool]:
        """
        Generate a tool from observed usage patterns.

        Args:
            tool_sequence: Sequence of tool names that are often called together.
            name: Optional tool name.

        Returns:
            GeneratedTool or None if generation fails.
        """
        if not name:
            name = f"composed_{'_'.join(tool_sequence)}"

        tool_defs = []
        for tool_name in tool_sequence:
            try:
                schema = self.registry.get_schema(tool_name)
                tool_defs.append(
                    {
                        "name": tool_name,
                        "params": schema.parameters,
                        "required": schema.required_params,
                    }
                )
            except ToolNotFoundError:
                logger.warning(f"Tool '{tool_name}' not found for pattern generation")
                return None

        code = self._generate_pattern_code(name, tool_sequence, tool_defs)
        params = {"input": {"type": "dict", "description": "Input parameters"}}

        tool = GeneratedTool(
            name=name,
            source="pattern",
            description=f"Auto-generated from pattern: {' → '.join(tool_sequence)}",
            category=ToolCategory.COMPOSED,
            code=code,
            parameters=params,
            required_params=["input"],
        )

        tool.func = self._compile_tool(tool)
        tool.quality_report = self._validate_quality(tool)

        self._generated_tools[name] = tool
        return tool

    def generate_from_openapi(
        self,
        spec: Dict[str, Any],
        base_url: str = "",
        prefix: str = "api",
    ) -> List[GeneratedTool]:
        """
        Generate tools from an OpenAPI specification.

        Args:
            spec: OpenAPI spec dictionary.
            base_url: Base URL for API calls.
            prefix: Prefix for generated tool names.

        Returns:
            List of GeneratedTool objects.
        """
        tool_defs = self.api_parser.parse_openapi(spec)
        tools = []

        for tool_def in tool_defs:
            name = f"{prefix}_{tool_def['name']}"
            code = self._generate_api_tool_code(tool_def, base_url)

            tool = GeneratedTool(
                name=name,
                source="openapi",
                description=tool_def["description"],
                category=tool_def.get("category", ToolCategory.WEB),
                code=code,
                parameters=tool_def["parameters"],
                required_params=tool_def["required_params"],
            )

            tool.func = self._compile_tool(tool)
            tool.quality_report = self._validate_quality(tool)

            self._generated_tools[name] = tool
            tools.append(tool)

        return tools

    def generate_from_swagger(
        self,
        spec: Dict[str, Any],
        base_url: str = "",
        prefix: str = "api",
    ) -> List[GeneratedTool]:
        """
        Generate tools from a Swagger specification.

        Args:
            spec: Swagger spec dictionary.
            base_url: Base URL for API calls.
            prefix: Prefix for generated tool names.

        Returns:
            List of GeneratedTool objects.
        """
        tool_defs = self.api_parser.parse_swagger(spec)
        tools = []

        for tool_def in tool_defs:
            name = f"{prefix}_{tool_def['name']}"
            code = self._generate_api_tool_code(tool_def, base_url)

            tool = GeneratedTool(
                name=name,
                source="swagger",
                description=tool_def["description"],
                category=tool_def.get("category", ToolCategory.WEB),
                code=code,
                parameters=tool_def["parameters"],
                required_params=tool_def["required_params"],
            )

            tool.func = self._compile_tool(tool)
            tool.quality_report = self._validate_quality(tool)

            self._generated_tools[name] = tool
            tools.append(tool)

        return tools

    def generate_documentation(self, tool: GeneratedTool) -> str:
        """
        Generate documentation for a tool.

        Args:
            tool: The tool to document.

        Returns:
            Markdown documentation string.
        """
        lines = []
        lines.append(f"# {tool.name}")
        lines.append("")
        lines.append(f"**Description:** {tool.description}")
        lines.append(f"**Category:** {tool.category.value}")
        lines.append(f"**Source:** {tool.source}")
        lines.append(f"**Version:** {tool.version}")
        lines.append("")

        if tool.parameters:
            lines.append("## Parameters")
            lines.append("")
            for param_name, param_info in tool.parameters.items():
                required = param_name in tool.required_params
                req_str = " (required)" if required else " (optional)"
                param_type = param_info.get("type", "Any")
                param_desc = param_info.get("description", "")
                lines.append(f"- `{param_name}` ({param_type}){req_str}: {param_desc}")
            lines.append("")

        lines.append("## Code")
        lines.append("")
        lines.append("```python")
        lines.append(tool.code)
        lines.append("```")
        lines.append("")

        if tool.quality_report:
            lines.append("## Quality Report")
            lines.append("")
            lines.append(f"- **Overall Score:** {tool.quality_report.overall_score:.1f}/100")
            lines.append(f"- **Syntax Valid:** {tool.quality_report.syntax_valid}")
            lines.append(f"- **Safety Score:** {tool.quality_report.safety_score:.1f}/100")
            lines.append(f"- **Test Coverage:** {tool.quality_report.test_coverage:.1f}%")
            if tool.quality_report.issues:
                lines.append("")
                lines.append("### Issues")
                for issue in tool.quality_report.issues:
                    lines.append(f"- {issue}")
            if tool.quality_report.warnings:
                lines.append("")
                lines.append("### Warnings")
                for warning in tool.quality_report.warnings:
                    lines.append(f"- {warning}")

        return "\n".join(lines)

    def auto_test_tool(self, tool: GeneratedTool) -> Dict[str, Any]:
        """
        Auto-generate and run test cases for a tool.

        Args:
            tool: The tool to test.

        Returns:
            Test results dictionary.
        """
        results = {
            "passed": 0,
            "failed": 0,
            "errors": [],
            "test_cases": [],
        }

        if not tool.func:
            results["errors"].append("Tool has no compiled function")
            return results

        test_cases = self._generate_test_cases(tool)

        for test_case in test_cases:
            try:
                result = tool.func(**test_case["input"])
                passed = test_case.get("validator", lambda r: True)(result)
                if passed:
                    results["passed"] += 1
                else:
                    results["failed"] += 1
                    results["errors"].append(
                        f"Test '{test_case.get('name', 'unknown')}' failed validation"
                    )
                results["test_cases"].append(
                    {
                        "name": test_case.get("name", "unknown"),
                        "passed": passed,
                        "input": test_case["input"],
                        "output": result,
                    }
                )
            except Exception as e:
                results["failed"] += 1
                results["errors"].append(
                    f"Test '{test_case.get('name', 'unknown')}' raised: {str(e)}"
                )
                results["test_cases"].append(
                    {
                        "name": test_case.get("name", "unknown"),
                        "passed": False,
                        "error": str(e),
                    }
                )

        results["total"] = results["passed"] + results["failed"]
        results["coverage"] = (
            results["passed"] / results["total"] * 100 if results["total"] > 0 else 0
        )

        return results

    def _generate_name(self, description: str) -> str:
        """Generate a tool name from a description."""
        words = description.lower().split()
        meaningful = [
            w
            for w in words
            if w not in ("a", "an", "the", "that", "this", "to", "for", "of", "and", "or")
        ][:4]
        return "_".join(meaningful) if meaningful else f"tool_{hash(description) % 10000}"

    def _parse_description(
        self, description: str, name: str
    ) -> Tuple[Dict[str, Dict[str, Any]], List[str], str]:
        """Parse a description to extract parameters and generate code."""
        params = {}
        required = []

        param_pattern = r"(\w+):\s*(str|int|float|bool|list|dict)"
        matches = re.findall(param_pattern, description)
        for param_name, param_type in matches:
            params[param_name] = {"type": param_type, "description": f"{param_name} parameter"}
            required.append(param_name)

        if not params:
            params = {"input": {"type": "str", "description": "Input value"}}
            required = ["input"]

        code = self._generate_simple_code(name, description, params)
        return params, required, code

    def _generate_simple_code(
        self, name: str, description: str, params: Dict[str, Dict[str, Any]]
    ) -> str:
        """Generate simple tool code from description."""
        param_list = ", ".join(f"{p}" for p in params.keys())
        code = f"def {name}({param_list}):\n"
        code += f'    """{description}"""\n'

        if "celsius" in description.lower() and "fahrenheit" in description.lower():
            code += "    return (input * 9/5) + 32\n"
        elif "uppercase" in description.lower() or "upper" in description.lower():
            code += "    return input.upper()\n"
        elif "lowercase" in description.lower() or "lower" in description.lower():
            code += "    return input.lower()\n"
        elif "reverse" in description.lower():
            code += "    return input[::-1]\n"
        elif "length" in description.lower() or "count" in description.lower():
            code += "    return len(input)\n"
        elif "hash" in description.lower():
            code += "    import hashlib\n"
            code += "    return hashlib.sha256(input.encode()).hexdigest()\n"
        elif "json" in description.lower():
            code += "    import json\n"
            code += "    return json.dumps(input)\n"
        else:
            code += "    return input\n"

        return code

    def _generate_pattern_code(
        self, name: str, tool_sequence: List[str], tool_defs: List[Dict[str, Any]]
    ) -> str:
        """Generate code for a pattern-based tool."""
        code = f"def {name}(input=None):\n"
        code += f'    """Auto-generated composition: {" → ".join(tool_sequence)}"""\n'
        code += "    result = input\n"
        for tool_name in tool_sequence:
            code += f"    result = execute_tool('{tool_name}', input=result)\n"
        code += "    return result\n"
        return code

    def _generate_api_tool_code(
        self, tool_def: Dict[str, Any], base_url: str
    ) -> str:
        """Generate code for an API-based tool."""
        name = tool_def["name"]
        method = tool_def["method"]
        path = tool_def["path"]
        params = tool_def["parameters"]

        param_list = ", ".join(f"{p}" for p in params.keys())
        code = f"def {name}({param_list}):\n"
        code += f'    """{tool_def["description"]}"""\n'
        code += f"    import requests\n"
        code += f"    url = f'{base_url}{path}'\n"

        path_params = [p for p, info in params.items() if info.get("in") == "path"]
        query_params = [p for p, info in params.items() if info.get("in") in ("query", None)]

        for pp in path_params:
            code += f"    url = url.replace('{{{{{pp}}}}}', str({pp}))\n"

        if query_params:
            code += f"    params = {{\n"
            for qp in query_params:
                code += f"        '{qp}': {qp},\n"
            code += f"    }}\n"
            code += f"    response = requests.{method.lower()}(url, params=params)\n"
        else:
            code += f"    response = requests.{method.lower()}(url)\n"

        code += f"    response.raise_for_status()\n"
        code += f"    return response.json()\n"

        return code

    def _compile_tool(self, tool: GeneratedTool) -> Callable:
        """Compile tool code into a callable function."""
        try:
            namespace = {}
            exec(tool.code, {"__builtins__": {k: __builtins__[k] for k in self._safe_builtins if k in __builtins__}}, namespace)
            func = namespace.get(tool.name)
            if func is None:
                raise ToolQualityError(f"Could not compile tool '{tool.name}'")
            return func
        except Exception as e:
            raise ToolQualityError(f"Compilation failed for '{tool.name}': {str(e)}")

    def _validate_quality(self, tool: GeneratedTool) -> ToolQualityReport:
        """Validate the quality of a generated tool."""
        report = ToolQualityReport(tool_name=tool.name)

        report.syntax_valid = self._check_syntax(tool.code)
        report.safety_score = self._check_safety(tool.code)
        report.documentation_score = self._check_documentation(tool)

        test_results = self.auto_test_tool(tool)
        report.tests_passed = test_results["passed"]
        report.tests_failed = test_results["failed"]
        report.tests_total = test_results["total"]
        report.test_coverage = test_results.get("coverage", 0)

        report.issues = test_results.get("errors", [])

        weights = {
            "syntax": 0.2,
            "safety": 0.3,
            "tests": 0.3,
            "docs": 0.2,
        }

        report.overall_score = (
            (100 if report.syntax_valid else 0) * weights["syntax"]
            + report.safety_score * weights["safety"]
            + report.test_coverage * weights["tests"]
            + report.documentation_score * weights["docs"]
        )

        return report

    def _check_syntax(self, code: str) -> bool:
        """Check if code has valid Python syntax."""
        try:
            ast.parse(code)
            return True
        except SyntaxError:
            return False

    def _check_safety(self, code: str) -> float:
        """Check code safety. Returns 0-100 score."""
        score = 100.0
        for pattern in self._dangerous_patterns:
            if re.search(pattern, code):
                score -= 25.0
        return max(0.0, score)

    def _check_documentation(self, tool: GeneratedTool) -> float:
        """Check documentation quality. Returns 0-100 score."""
        score = 0.0
        if tool.description:
            score += 40.0
        if tool.parameters:
            score += 30.0
        if '"""' in tool.code or "'''" in tool.code:
            score += 30.0
        return score

    def _generate_test_cases(self, tool: GeneratedTool) -> List[Dict[str, Any]]:
        """Generate test cases for a tool."""
        test_cases = []

        for param_name, param_info in tool.parameters.items():
            param_type = param_info.get("type", "str")

            if param_type == "str":
                test_cases.append(
                    {
                        "name": f"{tool.name}_{param_name}_string",
                        "input": {param_name: "test_value"},
                        "validator": lambda r: r is not None,
                    }
                )
                test_cases.append(
                    {
                        "name": f"{tool.name}_{param_name}_empty",
                        "input": {param_name: ""},
                        "validator": lambda r: r is not None,
                    }
                )
            elif param_type == "int":
                test_cases.append(
                    {
                        "name": f"{tool.name}_{param_name}_positive",
                        "input": {param_name: 42},
                        "validator": lambda r: r is not None,
                    }
                )
                test_cases.append(
                    {
                        "name": f"{tool.name}_{param_name}_zero",
                        "input": {param_name: 0},
                        "validator": lambda r: r is not None,
                    }
                )
            elif param_type == "float":
                test_cases.append(
                    {
                        "name": f"{tool.name}_{param_name}_decimal",
                        "input": {param_name: 3.14},
                        "validator": lambda r: r is not None,
                    }
                )
            elif param_type == "bool":
                test_cases.append(
                    {
                        "name": f"{tool.name}_{param_name}_true",
                        "input": {param_name: True},
                        "validator": lambda r: r is not None,
                    }
                )
            elif param_type == "list":
                test_cases.append(
                    {
                        "name": f"{tool.name}_{param_name}_list",
                        "input": {param_name: [1, 2, 3]},
                        "validator": lambda r: r is not None,
                    }
                )
            elif param_type == "dict":
                test_cases.append(
                    {
                        "name": f"{tool.name}_{param_name}_dict",
                        "input": {param_name: {"key": "value"}},
                        "validator": lambda r: r is not None,
                    }
                )

        return test_cases

    def get_generated_tool(self, name: str) -> Optional[GeneratedTool]:
        """Get a generated tool by name."""
        return self._generated_tools.get(name)

    def list_generated_tools(self) -> List[GeneratedTool]:
        """List all generated tools."""
        return list(self._generated_tools.values())

    def get_suggestions(self) -> List[Dict[str, Any]]:
        """Get tool generation suggestions from pattern observer."""
        return self.pattern_observer.get_suggestions()
