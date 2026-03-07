"""Tests for SCC analysis and mutual recursion handling.

Tests Tarjan's SCC algorithm implementation for detecting strongly
connected components in ADT dependency graphs.

Coverage:
- SCC detection for simple types
- SCC detection for self-recursive types
- SCC detection for mutually recursive types
- SCC component properties
- SCC ordering for elaboration phases
"""

import pytest

from systemf.elaborator.scc import (
    SCCNode,
    SCCComponent,
    SCCResult,
    SCCAnalyzer,
    analyze_type_dependencies,
    check_mutual_recursion,
)


# =============================================================================
# Test Fixtures
# =============================================================================


@pytest.fixture
def simple_nodes():
    """Simple non-recursive type nodes."""
    return [
        SCCNode(id="Int", data="int-data", dependencies=[]),
        SCCNode(id="Bool", data="bool-data", dependencies=[]),
        SCCNode(id="String", data="string-data", dependencies=[]),
    ]


@pytest.fixture
def self_recursive_node():
    """Self-recursive type node (Nat)."""
    return SCCNode(
        id="Nat",
        data="nat-data",
        dependencies=["Nat"],  # Nat depends on itself
    )


@pytest.fixture
def mutually_recursive_nodes():
    """Mutually recursive types (Even/Odd)."""
    return [
        SCCNode(
            id="Even",
            data="even-data",
            dependencies=["Odd"],  # Even depends on Odd
        ),
        SCCNode(
            id="Odd",
            data="odd-data",
            dependencies=["Even"],  # Odd depends on Even
        ),
    ]


@pytest.fixture
def tree_forest_nodes():
    """Mutually recursive Tree/Forest types."""
    return [
        SCCNode(
            id="Tree",
            data="tree-data",
            dependencies=["Forest"],
        ),
        SCCNode(
            id="Forest",
            data="forest-data",
            dependencies=["Tree", "Forest"],  # Forest depends on both
        ),
    ]


@pytest.fixture
def mixed_dependency_nodes():
    """Mixed: simple, self-recursive, and mutually recursive types."""
    return [
        SCCNode(id="Int", data="int-data", dependencies=[]),
        SCCNode(id="Nat", data="nat-data", dependencies=["Nat"]),
        SCCNode(id="Even", data="even-data", dependencies=["Odd"]),
        SCCNode(id="Odd", data="odd-data", dependencies=["Even"]),
    ]


# =============================================================================
# SCC Node Tests
# =============================================================================


class TestSCCNode:
    """Test SCC node construction and properties."""

    def test_node_construction(self):
        """Test basic node construction."""
        node = SCCNode(
            id="Nat",
            data={"name": "Nat"},
            dependencies=["Nat"],
        )

        assert node.id == "Nat"
        assert node.data == {"name": "Nat"}
        assert node.dependencies == ["Nat"]

    def test_node_no_dependencies(self):
        """Test node with no dependencies."""
        node = SCCNode(
            id="Int",
            data="int-data",
            dependencies=[],
        )

        assert node.dependencies == []

    def test_node_multiple_dependencies(self):
        """Test node with multiple dependencies."""
        node = SCCNode(
            id="Forest",
            data="forest-data",
            dependencies=["Tree", "Forest"],
        )

        assert len(node.dependencies) == 2
        assert "Tree" in node.dependencies
        assert "Forest" in node.dependencies


# =============================================================================
# SCC Component Tests
# =============================================================================


class TestSCCComponent:
    """Test SCC component construction and properties."""

    def test_single_node_component(self):
        """Test component with single non-recursive node."""
        node = SCCNode(id="Int", data="int", dependencies=[])
        component = SCCComponent(nodes=[node])

        assert component.get_node_ids() == ["Int"]
        assert not component.is_recursive
        assert not component.is_mutually_recursive

    def test_self_recursive_component(self):
        """Test component with self-recursive node."""
        node = SCCNode(id="Nat", data="nat", dependencies=["Nat"])
        component = SCCComponent(nodes=[node])

        assert component.get_node_ids() == ["Nat"]
        assert component.is_recursive
        assert not component.is_mutually_recursive

    def test_mutual_recursive_component(self):
        """Test component with mutually recursive nodes."""
        nodes = [
            SCCNode(id="Even", data="even", dependencies=["Odd"]),
            SCCNode(id="Odd", data="odd", dependencies=["Even"]),
        ]
        component = SCCComponent(nodes=nodes)

        ids = component.get_node_ids()
        assert len(ids) == 2
        assert "Even" in ids
        assert "Odd" in ids
        assert component.is_recursive
        assert component.is_mutually_recursive

    def test_multiple_mutual_component(self):
        """Test component with more than two mutually recursive nodes."""
        nodes = [
            SCCNode(id="A", data="a", dependencies=["B"]),
            SCCNode(id="B", data="b", dependencies=["C"]),
            SCCNode(id="C", data="c", dependencies=["A"]),
        ]
        component = SCCComponent(nodes=nodes)

        assert len(component.get_node_ids()) == 3
        assert component.is_mutually_recursive


# =============================================================================
# SCC Analyzer Tests - Simple Types
# =============================================================================


class TestSCCAnalyzerSimple:
    """Test SCC analysis on simple non-recursive types."""

    def test_single_component(self, simple_nodes):
        """Test analysis creates one component per node for simple types."""
        analyzer = SCCAnalyzer(simple_nodes)
        result = analyzer.analyze()

        assert len(result.components) == 3

    def test_all_non_recursive(self, simple_nodes):
        """Test that all simple types are non-recursive."""
        analyzer = SCCAnalyzer(simple_nodes)
        result = analyzer.analyze()

        for comp in result.components:
            assert not comp.is_recursive
            assert not comp.is_mutually_recursive

    def test_get_non_recursive(self, simple_nodes):
        """Test filtering for non-recursive components."""
        analyzer = SCCAnalyzer(simple_nodes)
        result = analyzer.analyze()

        # Filter out recursive components to get non-recursive
        non_recursive = [c for c in result.components if not c.is_recursive]
        assert len(non_recursive) == 3

    def test_no_mutual_recursion(self, simple_nodes):
        """Test no mutual recursion in simple types."""
        analyzer = SCCAnalyzer(simple_nodes)
        result = analyzer.analyze()

        mutual = result.get_mutually_recursive_groups()
        assert len(mutual) == 0


# =============================================================================
# SCC Analyzer Tests - Self-Recursive Types
# =============================================================================


class TestSCCAnalyzerSelfRecursive:
    """Test SCC analysis on self-recursive types."""

    def test_self_recursive_single_component(self, self_recursive_node):
        """Test self-recursive type is in single component."""
        analyzer = SCCAnalyzer([self_recursive_node])
        result = analyzer.analyze()

        assert len(result.components) == 1
        assert result.components[0].get_node_ids() == ["Nat"]

    def test_self_recursive_flag(self, self_recursive_node):
        """Test self-recursive types are marked as recursive."""
        analyzer = SCCAnalyzer([self_recursive_node])
        result = analyzer.analyze()

        comp = result.components[0]
        assert comp.is_recursive
        assert not comp.is_mutually_recursive

    def test_get_recursive_components(self, self_recursive_node):
        """Test filtering for recursive components."""
        analyzer = SCCAnalyzer([self_recursive_node])
        result = analyzer.analyze()

        recursive = result.get_recursive_components()
        assert len(recursive) == 1
        assert recursive[0].get_node_ids() == ["Nat"]


# =============================================================================
# SCC Analyzer Tests - Mutual Recursion
# =============================================================================


class TestSCCAnalyzerMutualRecursion:
    """Test SCC analysis on mutually recursive types."""

    def test_mutual_recursive_single_component(self, mutually_recursive_nodes):
        """Test mutually recursive types are in single component."""
        analyzer = SCCAnalyzer(mutually_recursive_nodes)
        result = analyzer.analyze()

        assert len(result.components) == 1

    def test_mutual_recursive_flags(self, mutually_recursive_nodes):
        """Test mutual recursion flags are set correctly."""
        analyzer = SCCAnalyzer(mutually_recursive_nodes)
        result = analyzer.analyze()

        comp = result.components[0]
        assert comp.is_recursive
        assert comp.is_mutually_recursive

    def test_mutual_recursive_node_ids(self, mutually_recursive_nodes):
        """Test component contains all mutually recursive nodes."""
        analyzer = SCCAnalyzer(mutually_recursive_nodes)
        result = analyzer.analyze()

        ids = result.components[0].get_node_ids()
        assert len(ids) == 2
        assert "Even" in ids
        assert "Odd" in ids

    def test_tree_forest_mutual(self, tree_forest_nodes):
        """Test Tree/Forest mutual recursion."""
        analyzer = SCCAnalyzer(tree_forest_nodes)
        result = analyzer.analyze()

        assert len(result.components) == 1

        comp = result.components[0]
        assert comp.is_mutually_recursive

        ids = comp.get_node_ids()
        assert "Tree" in ids
        assert "Forest" in ids

    def test_get_mutual_groups(self, mutually_recursive_nodes):
        """Test filtering for mutual recursion groups."""
        analyzer = SCCAnalyzer(mutually_recursive_nodes)
        result = analyzer.analyze()

        groups = result.get_mutually_recursive_groups()
        assert len(groups) == 1
        assert len(groups[0].get_node_ids()) == 2


# =============================================================================
# SCC Analyzer Tests - Mixed Dependencies
# =============================================================================


class TestSCCAnalyzerMixed:
    """Test SCC analysis on mixed dependency graphs."""

    def test_mixed_component_count(self, mixed_dependency_nodes):
        """Test correct number of components for mixed types."""
        analyzer = SCCAnalyzer(mixed_dependency_nodes)
        result = analyzer.analyze()

        # Int (simple), Nat (self-recursive), Even/Odd (mutual) = 3 components
        assert len(result.components) == 3

    def test_mixed_recursive_count(self, mixed_dependency_nodes):
        """Test correct count of recursive components."""
        analyzer = SCCAnalyzer(mixed_dependency_nodes)
        result = analyzer.analyze()

        recursive = result.get_recursive_components()
        # Nat (self-recursive) + Even/Odd group = 2 recursive components
        assert len(recursive) == 2

    def test_mixed_non_recursive_count(self, mixed_dependency_nodes):
        """Test correct count of non-recursive components."""
        analyzer = SCCAnalyzer(mixed_dependency_nodes)
        result = analyzer.analyze()

        # Filter out recursive components to get non-recursive
        non_recursive = [c for c in result.components if not c.is_recursive]
        # Just Int
        assert len(non_recursive) == 1
        assert non_recursive[0].get_node_ids() == ["Int"]

    def test_mixed_mutual_groups(self, mixed_dependency_nodes):
        """Test correct mutual recursion groups."""
        analyzer = SCCAnalyzer(mixed_dependency_nodes)
        result = analyzer.analyze()

        groups = result.get_mutually_recursive_groups()
        # Just Even/Odd
        assert len(groups) == 1
        assert len(groups[0].get_node_ids()) == 2


# =============================================================================
# Convenience Function Tests
# =============================================================================


class TestConvenienceFunctions:
    """Test convenience functions for SCC analysis."""

    def test_analyze_type_dependencies(self):
        """Test analyze_type_dependencies convenience function."""
        decls = [
            ("Nat", "nat-data", ["Nat"]),  # Self-recursive
            ("Bool", "bool-data", []),  # Simple
        ]

        result = analyze_type_dependencies(decls)

        assert len(result.components) == 2

    def test_check_mutual_recursion_true(self):
        """Test check_mutual_recursion detects mutual recursion."""
        decls = [
            ("Even", "even-data", ["Odd"]),
            ("Odd", "odd-data", ["Even"]),
        ]

        comp = check_mutual_recursion("Even", decls)

        assert comp is not None
        assert "Even" in comp.get_node_ids()
        assert "Odd" in comp.get_node_ids()

    def test_check_mutual_recursion_false(self):
        """Test check_mutual_recursion returns None for non-mutual."""
        decls = [
            ("Nat", "nat-data", ["Nat"]),  # Self-recursive
            ("Int", "int-data", []),  # Simple
        ]

        comp = check_mutual_recursion("Nat", decls)

        assert comp is None

    def test_check_mutual_recursion_not_found(self):
        """Test check_mutual_recursion for unknown type."""
        decls = [("Nat", "nat-data", ["Nat"])]

        comp = check_mutual_recursion("Unknown", decls)

        assert comp is None


# =============================================================================
# Edge Case Tests
# =============================================================================


class TestSCCEdgeCases:
    """Test edge cases in SCC analysis."""

    def test_empty_node_list(self):
        """Test analysis with empty node list."""
        analyzer = SCCAnalyzer([])
        result = analyzer.analyze()

        assert len(result.components) == 0

    def test_single_node_no_deps(self):
        """Test single node with no dependencies."""
        node = SCCNode(id="Unit", data="unit", dependencies=[])
        analyzer = SCCAnalyzer([node])
        result = analyzer.analyze()

        assert len(result.components) == 1
        assert not result.components[0].is_recursive

    def test_circular_dependency_three_nodes(self):
        """Test circular dependency A -> B -> C -> A."""
        nodes = [
            SCCNode(id="A", data="a", dependencies=["B"]),
            SCCNode(id="B", data="b", dependencies=["C"]),
            SCCNode(id="C", data="c", dependencies=["A"]),
        ]

        analyzer = SCCAnalyzer(nodes)
        result = analyzer.analyze()

        assert len(result.components) == 1
        assert len(result.components[0].get_node_ids()) == 3
        assert result.components[0].is_mutually_recursive

    def test_diamond_dependency(self):
        """Test diamond dependency pattern."""
        #   A
        #  / \
        # B   C
        #  \ /
        #   D
        nodes = [
            SCCNode(id="A", data="a", dependencies=["B", "C"]),
            SCCNode(id="B", data="b", dependencies=["D"]),
            SCCNode(id="C", data="c", dependencies=["D"]),
            SCCNode(id="D", data="d", dependencies=[]),
        ]

        analyzer = SCCAnalyzer(nodes)
        result = analyzer.analyze()

        # All non-recursive, so 4 components
        assert len(result.components) == 4
        assert all(not comp.is_recursive for comp in result.components)

    def test_unknown_dependency(self):
        """Test node with dependency not in node list."""
        node = SCCNode(id="MyType", data="my", dependencies=["UnknownType"])
        analyzer = SCCAnalyzer([node])
        result = analyzer.analyze()

        # Should still work, treating unknown as external
        assert len(result.components) == 1
