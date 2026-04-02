"""Unit tests for SCC (Strongly Connected Components) algorithm.

Tests Tarjan's algorithm implementation for detecting recursive binding groups.
"""
import pytest
from systemf.elab3.scc import (
    build_graph,
    find_sccs,
    process_output,
    detect_recursive_groups,
    Node,
    SCC,
    BindingGroup,
)


class TestBuildGraph:
    """Tests for graph construction from bindings."""

    def test_build_graph_empty(self):
        """Empty input produces empty graph."""
        bindings = []
        nodes = build_graph(bindings)
        assert nodes == []

    def test_build_graph_single_binding(self):
        """Single binding with no uses."""
        bindings = [("x = 1", "x", [])]
        nodes = build_graph(bindings)
        
        assert len(nodes) == 1
        assert nodes[0].key == 0
        assert nodes[0].payload == "x = 1"
        assert nodes[0].edges == []

    def test_build_graph_independent_bindings(self):
        """Multiple bindings with no dependencies."""
        bindings = [
            ("x = 1", "x", []),
            ("y = 2", "y", []),
            ("z = 3", "z", []),
        ]
        nodes = build_graph(bindings)
        
        assert len(nodes) == 3
        assert all(node.edges == [] for node in nodes)

    def test_build_graph_dependency_chain(self):
        """Bindings forming a dependency chain."""
        bindings = [
            ("z = x + y", "z", ["x", "y"]),
            ("y = 2", "y", []),
            ("x = 1", "x", []),
        ]
        nodes = build_graph(bindings)
        
        # z (index 0) depends on x (index 2) and y (index 1)
        assert nodes[0].edges == [2, 1]
        # y (index 1) has no dependencies
        assert nodes[1].edges == []
        # x (index 2) has no dependencies
        assert nodes[2].edges == []

    def test_build_graph_external_use(self):
        """Uses not defined in bindings are ignored."""
        bindings = [
            ("x = y + z", "x", ["y", "z"]),
        ]
        nodes = build_graph(bindings)
        
        # z not defined, only y creates edge
        # But y is also not defined in bindings list
        assert nodes[0].edges == []


class TestFindSCCs:
    """Tests for SCC detection algorithm."""

    def test_find_sccs_empty(self):
        """Empty graph produces no SCCs."""
        nodes = []
        sccs = find_sccs(nodes)
        assert sccs == []

    def test_find_sccs_single_node(self):
        """Single node, no edges."""
        nodes = [Node(key=0, payload="x", edges=[])]
        sccs = find_sccs(nodes)
        
        assert len(sccs) == 1
        assert len(sccs[0].nodes) == 1
        assert sccs[0].is_cyclic is False

    def test_find_sccs_self_recursive(self):
        """Single node with self-loop."""
        nodes = [Node(key=0, payload="fact", edges=[0])]
        sccs = find_sccs(nodes)
        
        assert len(sccs) == 1
        assert len(sccs[0].nodes) == 1
        assert sccs[0].is_cyclic is True  # Self-loop = recursive

    def test_find_sccs_two_independent(self):
        """Two independent nodes."""
        nodes = [
            Node(key=0, payload="x", edges=[]),
            Node(key=1, payload="y", edges=[]),
        ]
        sccs = find_sccs(nodes)
        
        assert len(sccs) == 2
        assert all(len(scc.nodes) == 1 for scc in sccs)
        assert all(not scc.is_cyclic for scc in sccs)

    def test_find_sccs_mutual_recursion_two_way(self):
        """Two mutually recursive bindings."""
        # even depends on odd, odd depends on even
        nodes = [
            Node(key=0, payload="even", edges=[1]),
            Node(key=1, payload="odd", edges=[0]),
        ]
        sccs = find_sccs(nodes)
        
        assert len(sccs) == 1
        assert len(sccs[0].nodes) == 2
        assert sccs[0].is_cyclic is True

    def test_find_sccs_mutual_recursion_three_way(self):
        """Three mutually recursive bindings."""
        # a -> b -> c -> a
        nodes = [
            Node(key=0, payload="a", edges=[1]),
            Node(key=1, payload="b", edges=[2]),
            Node(key=2, payload="c", edges=[0]),
        ]
        sccs = find_sccs(nodes)
        
        assert len(sccs) == 1
        assert len(sccs[0].nodes) == 3
        assert sccs[0].is_cyclic is True

    def test_find_sccs_topological_order(self):
        """SCCs are in topological order (dependencies first)."""
        # z depends on y, y depends on x
        nodes = [
            Node(key=0, payload="z", edges=[1]),
            Node(key=1, payload="y", edges=[2]),
            Node(key=2, payload="x", edges=[]),
        ]
        sccs = find_sccs(nodes)
        
        # Should be: x, then y, then z
        assert len(sccs) == 3
        assert sccs[0].nodes[0].payload == "x"
        assert sccs[1].nodes[0].payload == "y"
        assert sccs[2].nodes[0].payload == "z"

    def test_find_sccs_mixed_scenario(self):
        """Mix of independent and recursive groups."""
        # x and y are mutually recursive
        # z depends on x
        # w is independent
        nodes = [
            Node(key=0, payload="x", edges=[1]),
            Node(key=1, payload="y", edges=[0]),
            Node(key=2, payload="z", edges=[0]),
            Node(key=3, payload="w", edges=[]),
        ]
        sccs = find_sccs(nodes)
        
        # Should have 3 SCCs: (x,y), w, z
        assert len(sccs) == 3
        
        # Find the cyclic one (x,y)
        cyclic_sccs = [scc for scc in sccs if scc.is_cyclic]
        assert len(cyclic_sccs) == 1
        assert len(cyclic_sccs[0].nodes) == 2


class TestProcessOutput:
    """Tests for output processing."""

    def test_process_output_single_non_recursive(self):
        """Single non-recursive SCC."""
        sccs = [SCC(nodes=[Node(key=0, payload="x", edges=[])], is_cyclic=False)]
        groups = process_output(sccs)
        
        assert len(groups) == 1
        assert groups[0].bindings == ["x"]
        assert groups[0].is_recursive is False

    def test_process_output_recursive(self):
        """Recursive SCC with multiple bindings."""
        sccs = [
            SCC(
                nodes=[
                    Node(key=0, payload="even", edges=[1]),
                    Node(key=1, payload="odd", edges=[0]),
                ],
                is_cyclic=True,
            )
        ]
        groups = process_output(sccs)
        
        assert len(groups) == 1
        assert groups[0].bindings == ["even", "odd"]
        assert groups[0].is_recursive is True


class TestDetectRecursiveGroups:
    """End-to-end tests for the complete pipeline."""

    def test_empty_bindings(self):
        """Empty input."""
        bindings = []
        groups = detect_recursive_groups(bindings)
        assert groups == []

    def test_independent_bindings(self):
        """No recursion, just independent bindings."""
        bindings = [
            ("x = 1", "x", []),
            ("y = 2", "y", []),
        ]
        groups = detect_recursive_groups(bindings)
        
        assert len(groups) == 2
        assert all(not g.is_recursive for g in groups)

    def test_self_recursive(self):
        """Single self-recursive function."""
        bindings = [
            ("factorial n = if n==0 then 1 else n*factorial(n-1)", "factorial", ["factorial"]),
        ]
        groups = detect_recursive_groups(bindings)
        
        assert len(groups) == 1
        assert groups[0].is_recursive is True
        assert len(groups[0].bindings) == 1

    def test_mutual_recursion(self):
        """Mutually recursive even/odd functions."""
        bindings = [
            ("even n = if n==0 then True else odd(n-1)", "even", ["odd"]),
            ("odd n = if n==0 then False else even(n-1)", "odd", ["even"]),
        ]
        groups = detect_recursive_groups(bindings)
        
        assert len(groups) == 1
        assert groups[0].is_recursive is True
        assert len(groups[0].bindings) == 2

    def test_complex_scenario(self):
        """Complex mix: independent, recursive, dependencies."""
        # w: independent
        # x,y: mutually recursive
        # z: depends on x
        bindings = [
            ("z = x + 1", "z", ["x"]),
            ("y = x + 1", "y", ["x"]),  # y depends on x
            ("x = y + 1", "x", ["y"]),  # x depends on y (mutual with y)
            ("w = 42", "w", []),
        ]
        groups = detect_recursive_groups(bindings)
        
        # w (non-recursive)
        # x,y (mutually recursive)
        # z (depends on x)
        assert len(groups) == 3
        
        # Find groups by size
        recursive_groups = [g for g in groups if g.is_recursive]
        assert len(recursive_groups) == 1
        assert len(recursive_groups[0].bindings) == 2  # x and y
        
        non_recursive = [g for g in groups if not g.is_recursive]
        assert len(non_recursive) == 2  # w and z

    def test_topological_ordering(self):
        """Verify topological ordering is correct."""
        # Build a chain: a -> b -> c -> d (d depends on all)
        bindings = [
            ("d = a + b + c", "d", ["a", "b", "c"]),
            ("c = a + b", "c", ["a", "b"]),
            ("b = a", "b", ["a"]),
            ("a = 1", "a", []),
        ]
        groups = detect_recursive_groups(bindings)
        
        # All should be non-recursive and in dependency order
        assert len(groups) == 4
        assert all(not g.is_recursive for g in groups)
        
        # Extract payloads in order
        payloads = [g.bindings[0] for g in groups]
        # Should be: a, b, c, d (dependencies before dependents)
        assert payloads[0] == "a = 1"
        assert payloads[-1] == "d = a + b + c"
