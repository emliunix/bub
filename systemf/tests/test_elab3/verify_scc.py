#!/usr/bin/env python3
"""Manual verification script for SCC algorithm (no pytest required)."""
import sys
sys.path.insert(0, '/home/liu/Documents/bub/systemf/src')

from systemf.elab3.scc import (
    build_graph,
    find_sccs,
    process_output,
    detect_recursive_groups,
    Node,
    SCC,
    BindingGroup,
)


def test(name, condition):
    """Simple test assertion."""
    if condition:
        print(f"✓ {name}")
        return True
    else:
        print(f"✗ {name}")
        return False


def run_tests():
    """Run all SCC tests manually."""
    passed = 0
    failed = 0
    
    # Test 1: Empty input
    if test("Empty input produces empty graph", 
            build_graph([]) == []):
        passed += 1
    else:
        failed += 1
    
    # Test 2: Single binding
    nodes = build_graph([("x = 1", "x", [])])
    if test("Single binding has no edges",
            len(nodes) == 1 and nodes[0].edges == []):
        passed += 1
    else:
        failed += 1
    
    # Test 3: Self-recursive
    nodes = build_graph([("fact", "fact", ["fact"])])
    sccs = find_sccs(nodes)
    if test("Self-recursive detected as cyclic",
            len(sccs) == 1 and sccs[0].is_cyclic):
        passed += 1
    else:
        failed += 1
    
    # Test 4: Mutual recursion
    bindings = [
        ("even", "even", ["odd"]),
        ("odd", "odd", ["even"]),
    ]
    nodes = build_graph(bindings)
    sccs = find_sccs(nodes)
    if test("Mutual recursion produces single SCC",
            len(sccs) == 1 and len(sccs[0].nodes) == 2):
        passed += 1
    else:
        failed += 1
    
    # Test 5: Topological ordering
    bindings = [
        ("z", "z", ["x"]),
        ("x", "x", []),
    ]
    groups = detect_recursive_groups(bindings)
    if test("Topological order: dependencies first",
            len(groups) == 2 and groups[0].bindings == ["x"]):
        passed += 1
    else:
        failed += 1
    
    # Test 6: Independent bindings
    bindings = [
        ("x", "x", []),
        ("y", "y", []),
    ]
    groups = detect_recursive_groups(bindings)
    if test("Independent bindings are separate",
            len(groups) == 2 and all(not g.is_recursive for g in groups)):
        passed += 1
    else:
        failed += 1
    
    # Summary
    print(f"\n{passed} passed, {failed} failed")
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
