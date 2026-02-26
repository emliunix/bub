"""Tests for tool call parsing and execution.

Tests tool call syntax: @tool_name arg1 arg2 ...
"""

import pytest

from systemf.core.ast import ToolCall as CoreToolCall
from systemf.eval.machine import Evaluator
from systemf.eval.tools import (
    EchoTool,
    IdentityTool,
    LLMCallTool,
    Tool,
    ToolRegistry,
    get_tool_registry,
    reset_tool_registry,
)
from systemf.eval.value import VConstructor, VToolResult
from systemf.surface.ast import (
    SurfaceToolCall,
    SurfaceVar,
)
from systemf.surface.elaborator import elaborate_term
from systemf.surface.lexer import Lexer
from systemf.surface.parser import parse_term


class TestToolCallParsing:
    """Tests for tool call parsing."""

    def test_parse_simple_tool_call(self):
        """Parse simple tool call without arguments."""
        term = parse_term("@identity")
        assert isinstance(term, SurfaceToolCall)
        assert term.tool_name == "identity"
        assert term.args == []

    def test_parse_tool_call_with_single_arg(self):
        """Parse tool call with single argument."""
        term = parse_term("@identity 42")
        assert isinstance(term, SurfaceToolCall)
        assert term.tool_name == "identity"
        assert len(term.args) == 1
        assert isinstance(term.args[0], SurfaceConstructor)
        assert term.args[0].name == "42"

    def test_parse_tool_call_with_multiple_args(self):
        """Parse tool call with multiple arguments."""
        # Use parenthesized arguments to prevent constructor application
        term = parse_term("@echo (Hello) (World)")
        assert isinstance(term, SurfaceToolCall)
        assert term.tool_name == "echo"
        assert len(term.args) == 2

    def test_parse_tool_call_in_expression(self):
        """Parse tool call as part of larger expression."""
        term = parse_term(r"\x -> @identity x")
        assert isinstance(term, SurfaceAbs)
        assert isinstance(term.body, SurfaceToolCall)
        assert term.body.tool_name == "identity"
        assert len(term.body.args) == 1
        assert isinstance(term.body.args[0], SurfaceVar)
        assert term.body.args[0].name == "x"

    def test_parse_tool_call_in_let(self):
        """Parse tool call in let binding."""
        source = """let result = @identity 42
  result"""
        term = parse_term(source)
        assert isinstance(term, SurfaceLet)
        assert isinstance(term.value, SurfaceToolCall)
        assert term.value.tool_name == "identity"

    def test_parse_tool_call_in_application(self):
        """Parse tool call as function argument."""
        # Wrap tool call in parentheses to avoid type application ambiguity
        term = parse_term(r"(\f -> f) (@identity)")
        assert isinstance(term, SurfaceApp)
        assert isinstance(term.arg, SurfaceToolCall)
        assert term.arg.tool_name == "identity"

    def test_parse_nested_tool_calls(self):
        """Parse nested tool calls."""
        term = parse_term("@identity @echo Hello")
        assert isinstance(term, SurfaceToolCall)
        assert term.tool_name == "identity"
        assert len(term.args) == 1
        assert isinstance(term.args[0], SurfaceToolCall)
        assert term.args[0].tool_name == "echo"


class TestToolCallElaboration:
    """Tests for tool call elaboration to core."""

    def test_elaborate_simple_tool_call(self):
        """Elaborate simple tool call."""
        surface_term = parse_term("@identity")
        core_term = elaborate_term(surface_term)

        assert isinstance(core_term, CoreToolCall)
        assert core_term.tool_name == "identity"
        assert core_term.args == []

    def test_elaborate_tool_call_with_args(self):
        """Elaborate tool call with arguments."""
        surface_term = parse_term("@identity 42")
        core_term = elaborate_term(surface_term)

        assert isinstance(core_term, CoreToolCall)
        assert core_term.tool_name == "identity"
        assert len(core_term.args) == 1
        assert isinstance(core_term.args[0], core.Constructor)

    def test_elaborate_tool_call_with_variable(self):
        """Elaborate tool call with variable argument."""
        surface_term = parse_term(r"@identity x")
        core_term = elaborate_term(surface_term, context=["x"])

        assert isinstance(core_term, CoreToolCall)
        assert core_term.tool_name == "identity"
        assert len(core_term.args) == 1
        assert isinstance(core_term.args[0], core.Var)


class TestToolRegistry:
    """Tests for tool registry functionality."""

    def setup_method(self):
        """Reset registry before each test."""
        reset_tool_registry()

    def test_registry_has_builtin_tools(self):
        """Registry should have built-in tools."""
        registry = get_tool_registry()
        tools = registry.list_tools()
        assert "identity" in tools
        assert "echo" in tools

    def test_lookup_existing_tool(self):
        """Lookup should return existing tool."""
        registry = get_tool_registry()
        tool = registry.lookup("identity")
        assert isinstance(tool, IdentityTool)

    def test_lookup_nonexistent_tool(self):
        """Lookup should return None for nonexistent tool."""
        registry = get_tool_registry()
        tool = registry.lookup("nonexistent")
        assert tool is None

    def test_register_new_tool(self):
        """Register a new custom tool."""
        registry = get_tool_registry()

        class CustomTool(Tool):
            name = "custom"
            description = "A custom tool"

            def execute(self, args):
                return VToolResult(tool_name="custom", result="done", success=True)

        registry.register(CustomTool())
        assert "custom" in registry.list_tools()

    def test_register_duplicate_tool_fails(self):
        """Registering duplicate tool should raise error."""
        registry = get_tool_registry()

        with pytest.raises(ValueError, match="already registered"):
            registry.register(IdentityTool())


class TestToolExecution:
    """Tests for tool execution."""

    def setup_method(self):
        """Reset registry and evaluator before each test."""
        reset_tool_registry()
        self.evaluator = Evaluator()

    def test_identity_tool_with_constructor(self):
        """Identity tool returns argument unchanged."""
        from systemf.core.ast import Constructor
        from systemf.eval.value import VConstructor

        registry = get_tool_registry()
        arg = VConstructor("Answer", [VConstructor("42", [])])
        result = registry.execute("identity", [arg])

        assert isinstance(result, VToolResult)
        assert result.success is True
        assert result.tool_name == "identity"
        assert result.result == arg

    def test_echo_tool_no_args(self):
        """Echo tool with no arguments returns empty string."""
        registry = get_tool_registry()
        result = registry.execute("echo", [])

        assert isinstance(result, VToolResult)
        assert result.success is True
        assert result.result == ""

    def test_echo_tool_with_args(self):
        """Echo tool concatenates arguments."""
        from systemf.eval.value import VConstructor

        registry = get_tool_registry()
        args = [VConstructor("Hello", []), VConstructor("World", [])]
        result = registry.execute("echo", args)

        assert isinstance(result, VToolResult)
        assert result.success is True
        assert "Hello" in result.result
        assert "World" in result.result

    def test_execute_nonexistent_tool(self):
        """Executing nonexistent tool returns error."""
        registry = get_tool_registry()
        result = registry.execute("nonexistent", [])

        assert isinstance(result, VToolResult)
        assert result.success is False
        assert "not found" in str(result.result)


class TestToolCallEvaluation:
    """Tests for evaluating tool calls in the interpreter."""

    def setup_method(self):
        """Reset registry and evaluator before each test."""
        reset_tool_registry()
        self.evaluator = Evaluator()

    def test_evaluate_simple_tool_call(self):
        """Evaluate simple tool call."""
        from systemf.core.ast import Constructor, ToolCall

        term = ToolCall("identity", [Constructor("42", [])])
        result = self.evaluator.evaluate(term)

        assert isinstance(result, VToolResult)
        assert result.success is True

    def test_evaluate_tool_call_with_args(self):
        """Evaluate tool call with evaluated arguments."""
        from systemf.core.ast import Constructor, ToolCall

        term = ToolCall("echo", [Constructor("Hello", []), Constructor("World", [])])
        result = self.evaluator.evaluate(term)

        assert isinstance(result, VToolResult)
        assert result.success is True
        assert "Hello" in result.result
        assert "World" in result.result


class TestLLMCallTool:
    """Tests for LLM call tool."""

    def setup_method(self):
        """Reset registry before each test."""
        reset_tool_registry()

    def test_llm_call_tool_placeholder(self):
        """LLM call tool returns placeholder response."""
        registry = get_tool_registry()

        # Register LLM tool manually
        registry.register(LLMCallTool(model="gpt-4", temperature=0.5))

        from systemf.eval.value import VConstructor

        result = registry.execute("llm_call", [VConstructor("Hello LLM", [])])

        assert isinstance(result, VToolResult)
        assert result.success is True
        assert "LLM response" in result.result

    def test_llm_call_tool_wrong_args(self):
        """LLM call tool fails with wrong number of arguments."""
        registry = get_tool_registry()
        registry.register(LLMCallTool())

        result = registry.execute("llm_call", [])

        assert isinstance(result, VToolResult)
        assert result.success is False
        assert "Expected 1 argument" in result.result


class TestToolCallIntegration:
    """Integration tests for full tool call pipeline."""

    def setup_method(self):
        """Reset registry before each test."""
        reset_tool_registry()

    def test_full_pipeline_simple(self):
        """Full pipeline: parse -> elaborate -> evaluate."""
        # Parse
        surface_term = parse_term("@identity 42")

        # Elaborate
        core_term = elaborate_term(surface_term)

        # Evaluate
        evaluator = Evaluator()
        result = evaluator.evaluate(core_term)

        assert isinstance(result, VToolResult)
        assert result.success is True

    def test_tool_call_in_let_pipeline(self):
        """Tool call in let binding pipeline."""
        from systemf.surface.parser import parse_program
        from systemf.surface.elaborator import elaborate

        source = """result = @identity 42"""
        decls = parse_program(source)
        core_decls, _ = elaborate(decls)

        evaluator = Evaluator()
        results = evaluator.evaluate_program(core_decls)

        assert "result" in results
        assert isinstance(results["result"], VToolResult)
        assert results["result"].success is True


# Import needed for tests
from systemf.core import ast as core
from systemf.surface.ast import (
    SurfaceAbs,
    SurfaceApp,
    SurfaceConstructor,
    SurfaceLet,
)
