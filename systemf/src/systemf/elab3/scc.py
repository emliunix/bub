"""
SCC components analysis

Given a list of bindings, each binding potentially uses other bindings.
Define a graph of bindings, each node is a binding, and the edges are the "uses" relationship.

After SCC analysis, we take the topological sort output to construct nested let bindings
where each one is either a single binding or a group of mutually recursive bindings.
"""
from dataclasses import dataclass
from typing import Any, Generic, TypeVar

# Step 2: GRAPH CONSTRUCTION
# ----------------------------------------------------------------------------
# Build dependency graph: node depends on the bindings that define its uses

T = TypeVar('T')
K = TypeVar('K')


@dataclass
class Node(Generic[K, T]):
    key: int              # unique identifier (index)
    payload: T            # the binding
    edges: list[int]      # keys (indices) of dependencies


def find_node_by_key(nodes: list[Node], key: int) -> Node:
    """Find node by its key."""
    for node in nodes:
        if node.key == key:
            return node
    raise KeyError(f"Node with key {key} not found")


def build_graph(bindings: list[tuple[T, K, list[K]]]) -> list[Node[K, T]]:
    """
    Build dependency graph from bindings.
    
    Input: list of (payload, def_key, uses_keys)
    Output: Nodes with edges pointing to dependencies
    """
    # Map: def_key -> index (position in bindings list)
    def_map: dict[K, int] = {}
    for i, (payload, def_key, uses) in enumerate(bindings):
        def_map[def_key] = i
    
    # Build nodes with edges (uses -> definitions)
    nodes = []
    for i, (payload, def_key, uses) in enumerate(bindings):
        edges = [def_map[use] for use in uses if use in def_map]
        nodes.append(Node(key=i, payload=payload, edges=edges))
    
    return nodes

# Step 3: SCC ANALYSIS (Tarjan's or Kosaraju's algorithm)
# ----------------------------------------------------------------------------
# Find strongly connected components in dependency order

@dataclass
class SCC:
    nodes: list[Node]     # bindings in this component
    is_cyclic: bool       # True if mutual recursion or self-recursion

def find_sccs(nodes: list[Node]) -> list[SCC]:
    """
    Standard SCC algorithm (Tarjan's):
    - DFS with index and lowlink tracking
    - When lowlink == index, pop stack to form SCC
    - Returns SCCs in reverse topological order (dependencies first)
    """
    index_counter = [0]
    index_map: dict[int, int] = {}      # node key -> index
    lowlink_map: dict[int, int] = {}    # node key -> lowlink
    stack: list[int] = []
    on_stack: set[int] = set()
    sccs: list[SCC] = []

    def strongconnect(node: Node):
        index_map[node.key] = index_counter[0]
        lowlink_map[node.key] = index_counter[0]
        index_counter[0] += 1
        stack.append(node.key)
        on_stack.add(node.key)

        # Visit dependencies
        for edge_key in node.edges:
            if edge_key not in index_map:
                # Unvisited dependency - recurse
                neighbor = find_node_by_key(nodes, edge_key)
                strongconnect(neighbor)
                lowlink_map[node.key] = min(lowlink_map[node.key],
                                            lowlink_map[edge_key])
            elif edge_key in on_stack:
                # Back edge to current SCC
                lowlink_map[node.key] = min(lowlink_map[node.key],
                                            index_map[edge_key])

        # If root of SCC, pop stack
        if lowlink_map[node.key] == index_map[node.key]:
            scc_nodes = []
            while True:
                w = stack.pop()
                on_stack.remove(w)
                scc_nodes.append(find_node_by_key(nodes, w))
                if w == node.key:
                    break

            # Determine if cyclic (self-loop or multi-node)
            is_cyclic = (len(scc_nodes) > 1 or
                        any(n.key in n.edges for n in scc_nodes))
            sccs.append(SCC(nodes=scc_nodes, is_cyclic=is_cyclic))

    # Run on all unvisited nodes
    for node in nodes:
        if node.key not in index_map:
            strongconnect(node)

    # Return in topological order (dependencies first)
    return sccs


# Step 4: OUTPUT PROCESSING
# ----------------------------------------------------------------------------
# Convert SCCs to final groups with recursion flags

@dataclass
class BindingGroup:
    bindings: list[Any]   # the actual binding payloads
    is_recursive: bool    # True if cyclic (needs fixpoint iteration)

def process_output(sccs: list[SCC]) -> list[BindingGroup]:
    """
    Convert SCCs to binding groups.
    SCCs are already in dependency order (least dependent first).
    """
    groups = []
    for scc in sccs:
        payloads = [node.payload for node in scc.nodes]
        groups.append(BindingGroup(
            bindings=payloads,
            is_recursive=scc.is_cyclic
        ))
    return groups


# =============================================================================
# COMPLETE PIPELINE
# =============================================================================

def detect_recursive_groups(bindings: list[tuple[T, K, list[K]]]) -> list[BindingGroup]:
    """Full pipeline from bindings to ordered groups."""
    nodes = build_graph(bindings)      # Step 2
    sccs = find_sccs(nodes)             # Step 3
    return process_output(sccs)         # Step 4
