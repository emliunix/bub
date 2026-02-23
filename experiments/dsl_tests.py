#!/usr/bin/env python3
"""
Workflow DSL - Test Suite

Comprehensive test cases for parser implementations.
Each test case includes:
- Input DSL code
- Expected AST structure
- Description of what's being tested
"""

from dsl_ast import (
    Program,
    FunctionDef,
    LetBinding,
    ReturnStmt,
    ExprStmt,
    TypedParam,
    Type,
    Identifier,
    StringLiteral,
    IntegerLiteral,
    LLMCall,
    STR,
    INT,
    VOID,
)
from typing import NamedTuple, Optional


class TestCase(NamedTuple):
    name: str
    description: str
    input_code: str
    expected_ast: Program


# =============================================================================
# Test Cases
# =============================================================================

TEST_CASES = [
    # -------------------------------------------------------------------------
    # Basic Function Definitions
    # -------------------------------------------------------------------------
    TestCase(
        name="minimal_function",
        description="Minimal function with no params and no body",
        input_code="""
def empty():
    pass
""",
        expected_ast=Program(functions=[FunctionDef(name="empty", params=[], return_type=None, doc=None, body=[])]),
    ),
    TestCase(
        name="function_with_params",
        description="Function with typed parameters",
        input_code="""
def add(x :: int, y :: int) -> int:
    return x
""",
        expected_ast=Program(
            functions=[
                FunctionDef(
                    name="add",
                    params=[TypedParam(name="x", type_=INT), TypedParam(name="y", type_=INT)],
                    return_type=INT,
                    doc=None,
                    body=[ReturnStmt(value=Identifier(name="x"))],
                )
            ]
        ),
    ),
    TestCase(
        name="function_with_docstring",
        description="Function with documentation string",
        input_code='''
def greet(name :: str) -> str:
    """Return a greeting for the given name."""
    return name
''',
        expected_ast=Program(
            functions=[
                FunctionDef(
                    name="greet",
                    params=[TypedParam(name="name", type_=STR)],
                    return_type=STR,
                    doc="Return a greeting for the given name.",
                    body=[ReturnStmt(value=Identifier(name="name"))],
                )
            ]
        ),
    ),
    # -------------------------------------------------------------------------
    # Let Bindings
    # -------------------------------------------------------------------------
    TestCase(
        name="simple_let",
        description="Simple let binding with literal",
        input_code="""
def test():
    let x :: int = 42
    return x
""",
        expected_ast=Program(
            functions=[
                FunctionDef(
                    name="test",
                    params=[],
                    return_type=None,
                    doc=None,
                    body=[
                        LetBinding(name="x", type_=INT, value=IntegerLiteral(value=42)),
                        ReturnStmt(value=Identifier(name="x")),
                    ],
                )
            ]
        ),
    ),
    # -------------------------------------------------------------------------
    # LLM Calls
    # -------------------------------------------------------------------------
    TestCase(
        name="simple_llm_call",
        description="Simple LLM call without context",
        input_code="""
def summarize():
    let result :: str = llm "Summarize this"
    return result
""",
        expected_ast=Program(
            functions=[
                FunctionDef(
                    name="summarize",
                    params=[],
                    return_type=None,
                    doc=None,
                    body=[
                        LetBinding(name="result", type_=STR, value=LLMCall(prompt="Summarize this", context=None)),
                        ReturnStmt(value=Identifier(name="result")),
                    ],
                )
            ]
        ),
    ),
    TestCase(
        name="llm_call_with_context",
        description="LLM call with context using 'with' keyword",
        input_code="""
def analyze(code :: str):
    let issues :: str = llm "Find bugs" with code
    return issues
""",
        expected_ast=Program(
            functions=[
                FunctionDef(
                    name="analyze",
                    params=[TypedParam(name="code", type_=STR)],
                    return_type=None,
                    doc=None,
                    body=[
                        LetBinding(
                            name="issues", type_=STR, value=LLMCall(prompt="Find bugs", context=Identifier(name="code"))
                        ),
                        ReturnStmt(value=Identifier(name="issues")),
                    ],
                )
            ]
        ),
    ),
    # -------------------------------------------------------------------------
    # Full Example
    # -------------------------------------------------------------------------
    TestCase(
        name="full_example",
        description="Complete example with all features",
        input_code='''
def analyze_code(filename :: str) -> str:
    """Analyze source code for issues."""
    let content :: str = llm "Read and summarize the file"
    let issues :: str = llm "Find bugs" with content
    return issues
''',
        expected_ast=Program(
            functions=[
                FunctionDef(
                    name="analyze_code",
                    params=[TypedParam(name="filename", type_=STR)],
                    return_type=STR,
                    doc="Analyze source code for issues.",
                    body=[
                        LetBinding(
                            name="content", type_=STR, value=LLMCall(prompt="Read and summarize the file", context=None)
                        ),
                        LetBinding(
                            name="issues",
                            type_=STR,
                            value=LLMCall(prompt="Find bugs", context=Identifier(name="content")),
                        ),
                        ReturnStmt(value=Identifier(name="issues")),
                    ],
                )
            ]
        ),
    ),
]


# =============================================================================
# Invalid Test Cases (Should produce errors)
# =============================================================================

INVALID_TEST_CASES = [
    (
        "unmatched_indent",
        """
def test():
    let x = 1
   return x
""",
        "Inconsistent indentation",
    ),
    (
        "missing_colon",
        """
def test()
    return 1
""",
        "Missing colon after function signature",
    ),
    (
        "invalid_type",
        """
def test() -
    return 1
""",
        "Invalid type annotation syntax",
    ),
]


# =============================================================================
# Test Runner
# =============================================================================


def run_parser_tests(parser_class, parser_name: str):
    """Run all test cases against a parser implementation."""
    import sys

    print(f"\n{'=' * 70}")
    print(f"Testing {parser_name}")
    print(f"{'=' * 70}\n")

    parser = parser_class()
    passed = 0
    failed = 0

    for test in TEST_CASES:
        try:
            result = parser.parse(test.input_code)

            # Compare ASTs
            if result == test.expected_ast:
                print(f"✅ {test.name}: PASS")
                passed += 1
            else:
                print(f"❌ {test.name}: FAIL - AST mismatch")
                print(f"   Expected: {test.expected_ast}")
                print(f"   Got:      {result}")
                failed += 1

        except Exception as e:
            print(f"❌ {test.name}: FAIL - Exception")
            print(f"   Error: {e}")
            failed += 1

    print(f"\n{'=' * 70}")
    print(f"Results: {passed} passed, {failed} failed")
    print(f"{'=' * 70}\n")

    return failed == 0


if __name__ == "__main__":
    print("Workflow DSL Test Suite")
    print(f"Total test cases: {len(TEST_CASES)}")

    for test in TEST_CASES:
        print(f"\n{test.name}: {test.description}")
        print(f"Input:\n{test.input_code}")
        print(f"Expected AST:\n{test.expected_ast}")
