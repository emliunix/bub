"""SCC (Strongly Connected Components) analysis for System FC.

This module implements Tarjan's algorithm to detect strongly connected components
in type dependency graphs. SCC analysis is used to:

1. Detect mutually recursive type declarations
2. Group mutually recursive types for ordering during elaboration
3. Enable proper handling of recursive ADT definitions

Tarjan's Algorithm Overview:
- Single-pass DFS that assigns each node an index and a low-link value
- Nodes with the same low-link belong to the same SCC
- Runs in O(V + E) time complexity
- Produces SCCs in reverse topological order

Example:
    data Nat = Zero | Succ Nat
    data List a = Nil | Cons a (List a)

In this example, Nat and List are independent (no mutual recursion).
But if we had:

    data Even = Zero | SuccE Odd
    data Odd = SuccO Even

Even and Odd form an SCC (mutually recursive).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TypeVar, Generic, Optional


T = TypeVar("T")


@dataclass
class SCCNode(Generic[T]):
    """A node in the dependency graph for SCC analysis.

    Represents a type declaration with its dependencies (edges to other types).

    Attributes:
        id: Unique identifier for the node (typically type name)
        data: The actual type declaration data
        dependencies: List of node IDs this type depends on (edges)
    """

    id: str
    data: T
    dependencies: list[str] = field(default_factory=list)


@dataclass
class SCCComponent(Generic[T]):
    """A strongly connected component containing mutually recursive types.

    In the context of type declarations:
    - Single-node components are non-recursive or self-recursive types
    - Multi-node components contain mutually recursive types

    Attributes:
        nodes: List of nodes in this component
        is_recursive: True if component has cycles (mutual or self recursion)
    """

    nodes: list[SCCNode[T]]

    @property
    def is_recursive(self) -> bool:
        """Returns True if this component contains recursive types."""
        # Multi-node components are always mutually recursive
        if len(self.nodes) > 1:
            return True
        # Single node: check for self-loop
        if len(self.nodes) == 1:
            node = self.nodes[0]
            return node.id in node.dependencies
        return False

    @property
    def is_mutually_recursive(self) -> bool:
        """Returns True if this component contains mutually recursive types."""
        return len(self.nodes) > 1

    def get_node_ids(self) -> list[str]:
        """Get IDs of all nodes in this component."""
        return [node.id for node in self.nodes]


@dataclass
class SCCResult(Generic[T]):
    """Result of SCC analysis containing all components in dependency order.

    Components are ordered such that:
    - Components with no dependencies come first
    - Components that depend on others come later
    - This is the reverse topological order of the condensation graph

    Attributes:
        components: List of SCCs in dependency order
    """

    components: list[SCCComponent[T]]

    def get_mutually_recursive_groups(self) -> list[SCCComponent[T]]:
        """Return only components that are mutually recursive."""
        return [comp for comp in self.components if comp.is_mutually_recursive]

    def get_recursive_components(self) -> list[SCCComponent[T]]:
        """Return all recursive components (mutual or self-recursive)."""
        return [comp for comp in self.components if comp.is_recursive]

    def get_ordered_nodes(self) -> list[SCCNode[T]]:
        """Get all nodes in dependency order (flattened components)."""
        result = []
        for comp in self.components:
            result.extend(comp.nodes)
        return result


class SCCAnalyzer(Generic[T]):
    """Tarjan's algorithm implementation for SCC detection.

    Usage:
        # Create nodes for type declarations
        nodes = [
            SCCNode("Nat", nat_decl, ["Nat"]),  # Self-recursive
            SCCNode("Even", even_decl, ["Odd"]),  # Mutually recursive
            SCCNode("Odd", odd_decl, ["Even"]),   # Mutually recursive
        ]

        # Run analysis
        analyzer = SCCAnalyzer(nodes)
        result = analyzer.analyze()

        # Process results
        for comp in result.components:
            if comp.is_mutually_recursive:
                print(f"Mutually recursive: {comp.get_node_ids()}")
    """

    def __init__(self, nodes: list[SCCNode[T]]):
        """Initialize analyzer with dependency graph nodes.

        Args:
            nodes: List of SCCNode objects representing type declarations
        """
        self.nodes = nodes
        self._node_map: dict[str, SCCNode[T]] = {node.id: node for node in nodes}

        # Tarjan's algorithm state
        self._index = 0
        self._index_map: dict[str, int] = {}  # node_id -> index
        self._lowlink_map: dict[str, int] = {}  # node_id -> lowlink
        self._on_stack: set[str] = set()
        self._stack: list[str] = []
        self._components: list[SCCComponent[T]] = []

    def analyze(self) -> SCCResult[T]:
        """Run Tarjan's algorithm and return SCCs in dependency order.

        Returns:
            SCCResult containing all components ordered by dependency
            (least dependent first, most dependent last)
        """
        # Reset state
        self._index = 0
        self._index_map.clear()
        self._lowlink_map.clear()
        self._on_stack.clear()
        self._stack.clear()
        self._components.clear()

        # Run Tarjan's algorithm on all unvisited nodes
        for node in self.nodes:
            if node.id not in self._index_map:
                self._strongconnect(node)

        return SCCResult(components=self._components)

    def _strongconnect(self, node: SCCNode[T]) -> None:
        """Recursive DFS for Tarjan's algorithm.

        This is the core of Tarjan's algorithm. It assigns indices and
        lowlink values, then identifies SCCs when lowlink == index.
        """
        node_id = node.id

        # Set the depth index for this node to the smallest unused index
        self._index_map[node_id] = self._index
        self._lowlink_map[node_id] = self._index
        self._index += 1
        self._stack.append(node_id)
        self._on_stack.add(node_id)

        # Consider successors of this node
        for dep_id in node.dependencies:
            if dep_id not in self._node_map:
                # Skip missing dependencies (will be caught elsewhere)
                continue

            if dep_id not in self._index_map:
                # Successor has not yet been visited; recurse on it
                self._strongconnect(self._node_map[dep_id])
                self._lowlink_map[node_id] = min(
                    self._lowlink_map[node_id], self._lowlink_map[dep_id]
                )
            elif dep_id in self._on_stack:
                # Successor is in stack and hence in the current SCC
                self._lowlink_map[node_id] = min(
                    self._lowlink_map[node_id], self._index_map[dep_id]
                )

        # If node is a root node, pop the stack and generate an SCC
        if self._lowlink_map[node_id] == self._index_map[node_id]:
            # Start a new strongly connected component
            scc_nodes: list[SCCNode[T]] = []
            while True:
                w = self._stack.pop()
                self._on_stack.remove(w)
                scc_nodes.append(self._node_map[w])
                if w == node_id:
                    break

            self._components.append(SCCComponent(nodes=scc_nodes))


class SCCError(Exception):
    """Error during SCC analysis."""

    pass


def analyze_type_dependencies(type_declarations: list[tuple[str, T, list[str]]]) -> SCCResult[T]:
    """Convenience function to analyze type declarations for mutual recursion.

    Args:
        type_declarations: List of (type_name, type_data, dependencies) tuples

    Returns:
        SCCResult with components ordered by dependency

    Example:
        decls = [
            ("Nat", nat_type, ["Nat"]),      # Self-recursive
            ("Even", even_type, ["Odd"]),    # Depends on Odd
            ("Odd", odd_type, ["Even"]),     # Depends on Even
        ]
        result = analyze_type_dependencies(decls)

        # result.components will be:
        # [Component([Nat]), Component([Even, Odd])]
        # Note: Nat comes first (no mutual recursion), then Even/Odd together
    """
    nodes = [
        SCCNode(id=name, data=data, dependencies=deps) for name, data, deps in type_declarations
    ]

    analyzer = SCCAnalyzer(nodes)
    return analyzer.analyze()


def check_mutual_recursion(
    type_name: str, type_declarations: list[tuple[str, T, list[str]]]
) -> Optional[SCCComponent[T]]:
    """Check if a specific type is part of a mutually recursive group.

    Args:
        type_name: Name of the type to check
        type_declarations: List of all type declarations

    Returns:
        The SCC component containing the type if it's mutually recursive,
        None otherwise
    """
    result = analyze_type_dependencies(type_declarations)

    for comp in result.components:
        if type_name in comp.get_node_ids():
            return comp if comp.is_mutually_recursive else None

    return None
