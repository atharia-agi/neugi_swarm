"""StateGraph: Core workflow graph definition and compilation.

Provides LangGraph-style state machine workflows with typed state,
node definitions, conditional edges, and sub-graph composition.
"""

from __future__ import annotations

import dataclasses
import inspect
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
from typing import (
    Any,
    Callable,
    Dict,
    List,
    Optional,
    Set,
    Tuple,
    Type,
    Union,
)


class EdgeType(Enum):
    """Type of edge in the workflow graph."""
    UNCONDITIONAL = "unconditional"
    CONDITIONAL = "conditional"


class NodeStatus(Enum):
    """Status of a node during execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass
class StateDefinition:
    """Typed state definition for workflow execution.

    Uses dataclass fields to define the shape of workflow state.
    Supports default values and type hints for validation.

    Example:
        @dataclass
        class MyState(StateDefinition):
            query: str = ""
            results: List[str] = field(default_factory=list)
            confidence: float = 0.0
    """

    def get_fields(self) -> Dict[str, Any]:
        """Get all state fields as a dictionary."""
        return {f.name: getattr(self, f.name) for f in dataclasses.fields(self)}

    def update(self, **kwargs: Any) -> StateDefinition:
        """Create a new state with updated fields.

        Returns a new instance with specified fields updated,
        preserving immutability of the original state.
        """
        updates = self.get_fields()
        updates.update(kwargs)
        return dataclasses.replace(self, **updates)

    def merge(self, other: StateDefinition) -> StateDefinition:
        """Merge another state into this one.

        Non-None values from other take precedence.
        """
        updates = {}
        for f in dataclasses.fields(other):
            value = getattr(other, f.name)
            if value is not None:
                updates[f.name] = value
        return self.update(**updates)


@dataclass
class NodeDefinition:
    """Definition of a workflow node.

    Attributes:
        name: Unique identifier for the node.
        handler: Callable that processes state and returns updated state.
        input_schema: Expected input state type (optional validation).
        output_schema: Expected output state type (optional validation).
        description: Human-readable description of the node's purpose.
        metadata: Arbitrary metadata for the node.
    """

    name: str
    handler: Callable[[StateDefinition], StateDefinition]
    input_schema: Optional[Type[StateDefinition]] = None
    output_schema: Optional[Type[StateDefinition]] = None
    description: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate node definition after initialization."""
        if not self.name:
            raise ValueError("Node name cannot be empty")
        if not callable(self.handler):
            raise ValueError(f"Node handler for '{self.name}' must be callable")


@dataclass
class EdgeDefinition:
    """Definition of an unconditional edge between nodes.

    Connects a source node to a target node for sequential execution.
    """

    source: str
    target: str
    condition: Optional[Callable[[StateDefinition], bool]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate edge definition."""
        if not self.source:
            raise ValueError("Edge source cannot be empty")
        if not self.target:
            raise ValueError("Edge target cannot be empty")


@dataclass
class ConditionalEdge:
    """Definition of a conditional edge with multiple branches.

    Routes execution to different nodes based on state evaluation.

    Attributes:
        source: Source node name.
        router: Callable that returns the target node name based on state.
        targets: Set of valid target node names.
        default: Default target if router returns None or invalid target.
    """

    source: str
    router: Callable[[StateDefinition], str]
    targets: Set[str]
    default: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate conditional edge."""
        if not self.source:
            raise ValueError("Conditional edge source cannot be empty")
        if not callable(self.router):
            raise ValueError("Router function must be callable")
        if not self.targets:
            raise ValueError("Conditional edge must have at least one target")


@dataclass
class GraphCompilationResult:
    """Result of graph compilation.

    Contains the compiled graph structure ready for execution.
    """

    nodes: Dict[str, NodeDefinition]
    edges: Dict[str, List[EdgeDefinition]]
    conditional_edges: Dict[str, ConditionalEdge]
    entry_points: List[str]
    exit_points: List[str]
    execution_order: List[List[str]]  # Levels for parallel execution
    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class ExecutionContext:
    """Context passed during graph execution.

    Tracks the current state, execution path, and metadata.
    """

    state: StateDefinition
    current_node: Optional[str] = None
    path: List[str] = field(default_factory=list)
    depth: int = 0
    parent_context: Optional["ExecutionContext"] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def child_context(self, node_name: str) -> "ExecutionContext":
        """Create a child execution context for a sub-node."""
        return ExecutionContext(
            state=self.state,
            current_node=node_name,
            path=self.path + [node_name],
            depth=self.depth + 1,
            parent_context=self,
            metadata=dict(self.metadata),
        )


class StateGraph:
    """Main workflow graph builder and compiler.

    Provides a fluent API for defining workflow graphs with typed state,
    nodes, edges, and conditional routing. Supports sub-graph composition
    for building complex workflows from reusable components.

    Example:
        graph = StateGraph(MyState)
        graph.add_node("fetch", fetch_data)
        graph.add_node("process", process_data)
        graph.add_edge("fetch", "process")
        graph.set_entry_point("fetch")
        compiled = graph.compile()
    """

    def __init__(
        self,
        state_type: Type[StateDefinition],
        name: str = "workflow",
    ) -> None:
        """Initialize the state graph.

        Args:
            state_type: The dataclass type defining the workflow state.
            name: Human-readable name for the graph.
        """
        self.state_type = state_type
        self.name = name
        self._nodes: Dict[str, NodeDefinition] = {}
        self._edges: List[EdgeDefinition] = []
        self._conditional_edges: List[ConditionalEdge] = []
        self._entry_points: Set[str] = set()
        self._subgraphs: Dict[str, Tuple["StateGraph", str, str]] = {}
        self._compiled: Optional[GraphCompilationResult] = None

    def add_node(
        self,
        name: str,
        handler: Callable[[StateDefinition], StateDefinition],
        input_schema: Optional[Type[StateDefinition]] = None,
        output_schema: Optional[Type[StateDefinition]] = None,
        description: str = "",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "StateGraph":
        """Add a node to the graph.

        Args:
            name: Unique node identifier.
            handler: Function that takes state and returns updated state.
            input_schema: Optional input state type for validation.
            output_schema: Optional output state type for validation.
            description: Human-readable description.
            metadata: Optional metadata dictionary.

        Returns:
            Self for method chaining.

        Raises:
            ValueError: If node name already exists.
        """
        if name in self._nodes:
            raise ValueError(f"Node '{name}' already exists in graph '{self.name}'")

        node = NodeDefinition(
            name=name,
            handler=handler,
            input_schema=input_schema or self.state_type,
            output_schema=output_schema or self.state_type,
            description=description,
            metadata=metadata or {},
        )
        self._nodes[name] = node
        return self

    def add_edge(
        self,
        source: str,
        target: str,
        condition: Optional[Callable[[StateDefinition], bool]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "StateGraph":
        """Add an edge between two nodes.

        Args:
            source: Source node name.
            target: Target node name.
            condition: Optional condition function for conditional edges.
            metadata: Optional metadata dictionary.

        Returns:
            Self for method chaining.
        """
        if condition is not None:
            edge = EdgeDefinition(
                source=source,
                target=target,
                condition=condition,
                metadata=metadata or {},
            )
        else:
            edge = EdgeDefinition(
                source=source,
                target=target,
                metadata=metadata or {},
            )
        self._edges.append(edge)
        return self

    def add_conditional_edge(
        self,
        source: str,
        router: Callable[[StateDefinition], str],
        targets: Set[str],
        default: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> "StateGraph":
        """Add a conditional edge with multiple possible targets.

        Args:
            source: Source node name.
            router: Function that returns target node name based on state.
            targets: Set of valid target node names.
            default: Default target if router returns invalid result.
            metadata: Optional metadata dictionary.

        Returns:
            Self for method chaining.
        """
        conditional = ConditionalEdge(
            source=source,
            router=router,
            targets=targets,
            default=default,
            metadata=metadata or {},
        )
        self._conditional_edges.append(conditional)
        return self

    def set_entry_point(self, node_name: str) -> "StateGraph":
        """Set the entry point for graph execution.

        Args:
            node_name: Name of the node to start execution from.

        Returns:
            Self for method chaining.

        Raises:
            ValueError: If node does not exist.
        """
        if node_name not in self._nodes:
            raise ValueError(f"Node '{node_name}' not found in graph '{self.name}'")
        self._entry_points.add(node_name)
        return self

    def add_subgraph(
        self,
        subgraph: "StateGraph",
        entry_node: str,
        exit_node: str,
        name: Optional[str] = None,
    ) -> "StateGraph":
        """Add a subgraph to this graph for composition.

        Enables building complex workflows from reusable components.

        Args:
            subgraph: The subgraph to embed.
            entry_node: Node in parent graph that connects to subgraph entry.
            exit_node: Node in parent graph that connects from subgraph exit.
            name: Optional name for the subgraph reference.

        Returns:
            Self for method chaining.
        """
        subgraph_name = name or f"subgraph_{len(self._subgraphs)}"
        self._subgraphs[subgraph_name] = (subgraph, entry_node, exit_node)
        return self

    def compile(self) -> GraphCompilationResult:
        """Compile the graph into an executable structure.

        Performs validation, cycle detection, topological sorting,
        and computes execution levels for parallel execution.

        Returns:
            GraphCompilationResult with compiled graph structure.

        Raises:
            ValueError: If graph is invalid (cycles, disconnected nodes, etc.)
        """
        errors: List[str] = []
        warnings: List[str] = []

        # Validate nodes exist for all edges
        self._validate_edges(errors)

        # Validate entry points
        self._validate_entry_points(errors)

        # Detect cycles
        has_cycle = self._detect_cycles()
        if has_cycle:
            errors.append("Graph contains cycles which are not allowed")

        # Compute execution order via topological sort
        execution_order: List[List[str]] = []
        if not errors:
            execution_order = self._topological_sort()

        # Find exit points (nodes with no outgoing edges)
        exit_points = self._find_exit_points()

        # Build edge lookup
        edge_lookup = self._build_edge_lookup()
        conditional_lookup = self._build_conditional_lookup()

        result = GraphCompilationResult(
            nodes=dict(self._nodes),
            edges=edge_lookup,
            conditional_edges=conditional_lookup,
            entry_points=list(self._entry_points),
            exit_points=exit_points,
            execution_order=execution_order,
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
        )

        self._compiled = result
        return result

    def _validate_edges(self, errors: List[str]) -> None:
        """Validate that all edge references exist as nodes."""
        all_nodes = set(self._nodes.keys())

        for edge in self._edges:
            if edge.source not in all_nodes:
                errors.append(f"Edge source '{edge.source}' not found")
            if edge.target not in all_nodes:
                errors.append(f"Edge target '{edge.target}' not found")

        for cond_edge in self._conditional_edges:
            if cond_edge.source not in all_nodes:
                errors.append(f"Conditional edge source '{cond_edge.source}' not found")
            for target in cond_edge.targets:
                if target not in all_nodes:
                    errors.append(f"Conditional edge target '{target}' not found")
            if cond_edge.default and cond_edge.default not in all_nodes:
                errors.append(f"Conditional edge default '{cond_edge.default}' not found")

    def _validate_entry_points(self, errors: List[str]) -> None:
        """Validate entry points are set and valid."""
        if not self._entry_points:
            errors.append("No entry point set. Use set_entry_point() to define one")

    def _detect_cycles(self) -> bool:
        """Detect cycles in the graph using DFS.

        Returns:
            True if a cycle is detected, False otherwise.
        """
        WHITE, GRAY, BLACK = 0, 1, 2
        color: Dict[str, int] = {node: WHITE for node in self._nodes}

        def dfs(node: str) -> bool:
            color[node] = GRAY
            for edge in self._edges:
                if edge.source == node:
                    if color[edge.target] == GRAY:
                        return True
                    if color[edge.target] == WHITE and dfs(edge.target):
                        return True
            for cond_edge in self._conditional_edges:
                if cond_edge.source == node:
                    for target in cond_edge.targets:
                        if color[target] == GRAY:
                            return True
                        if color[target] == WHITE and dfs(target):
                            return True
            color[node] = BLACK
            return False

        for node in self._nodes:
            if color[node] == WHITE:
                if dfs(node):
                    return True
        return False

    def _topological_sort(self) -> List[List[str]]:
        """Perform topological sort and return execution levels.

        Nodes at the same level can be executed in parallel.

        Returns:
            List of lists, where each inner list contains nodes at that level.
        """
        in_degree: Dict[str, int] = {node: 0 for node in self._nodes}
        adjacency: Dict[str, List[str]] = {node: [] for node in self._nodes}

        for edge in self._edges:
            adjacency[edge.source].append(edge.target)
            in_degree[edge.target] += 1

        for cond_edge in self._conditional_edges:
            for target in cond_edge.targets:
                adjacency[cond_edge.source].append(target)
                in_degree[target] += 1

        # Start with entry points
        queue = deque()
        for entry in self._entry_points:
            queue.append(entry)

        levels: List[List[str]] = []
        visited: Set[str] = set()

        while queue:
            level_size = len(queue)
            current_level: List[str] = []

            for _ in range(level_size):
                node = queue.popleft()
                if node in visited:
                    continue
                visited.add(node)
                current_level.append(node)

                for neighbor in adjacency[node]:
                    in_degree[neighbor] -= 1
                    if in_degree[neighbor] == 0:
                        queue.append(neighbor)

            if current_level:
                levels.append(current_level)

        return levels

    def _find_exit_points(self) -> List[str]:
        """Find nodes with no outgoing edges (exit points).

        Returns:
            List of node names that are exit points.
        """
        has_outgoing: Set[str] = set()

        for edge in self._edges:
            has_outgoing.add(edge.source)

        for cond_edge in self._conditional_edges:
            has_outgoing.add(cond_edge.source)

        return [node for node in self._nodes if node not in has_outgoing]

    def _build_edge_lookup(self) -> Dict[str, List[EdgeDefinition]]:
        """Build a lookup of edges by source node.

        Returns:
            Dictionary mapping source node to list of outgoing edges.
        """
        lookup: Dict[str, List[EdgeDefinition]] = defaultdict(list)
        for edge in self._edges:
            lookup[edge.source].append(edge)
        return dict(lookup)

    def _build_conditional_lookup(self) -> Dict[str, ConditionalEdge]:
        """Build a lookup of conditional edges by source node.

        Returns:
            Dictionary mapping source node to its conditional edge.
        """
        lookup: Dict[str, ConditionalEdge] = {}
        for cond_edge in self._conditional_edges:
            lookup[cond_edge.source] = cond_edge
        return lookup

    def get_node(self, name: str) -> Optional[NodeDefinition]:
        """Get a node by name.

        Args:
            name: Node name to look up.

        Returns:
            NodeDefinition if found, None otherwise.
        """
        return self._nodes.get(name)

    def get_nodes(self) -> Dict[str, NodeDefinition]:
        """Get all nodes in the graph.

        Returns:
            Dictionary of node name to NodeDefinition.
        """
        return dict(self._nodes)

    def get_compiled(self) -> Optional[GraphCompilationResult]:
        """Get the compiled graph result.

        Returns:
            GraphCompilationResult if compiled, None otherwise.
        """
        return self._compiled

    def __repr__(self) -> str:
        """String representation of the graph."""
        return (
            f"StateGraph(name='{self.name}', "
            f"nodes={len(self._nodes)}, "
            f"edges={len(self._edges)}, "
            f"conditional_edges={len(self._conditional_edges)})"
        )
