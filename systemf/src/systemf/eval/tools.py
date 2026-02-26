"""Tool registry for System F tool calls.

Provides infrastructure for registering and executing external tools
that can be called from System F programs.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Callable

from systemf.eval.value import VConstructor, Value, VToolResult


class Tool(ABC):
    """Abstract base class for tools that can be called from System F."""

    name: str
    description: str

    @abstractmethod
    def execute(self, args: list[Value]) -> Value:
        """Execute the tool with the given arguments.

        Args:
            args: List of argument values

        Returns:
            Tool result as a Value
        """
        ...


class ToolRegistry:
    """Registry for available tools.

    Manages tool registration and lookup by name.
    """

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._register_builtin_tools()

    def _register_builtin_tools(self) -> None:
        """Register built-in tools available by default."""
        # Register identity tool for testing
        self.register(IdentityTool())
        self.register(EchoTool())

    def register(self, tool: Tool) -> None:
        """Register a tool.

        Args:
            tool: Tool instance to register

        Raises:
            ValueError: If tool with same name already exists
        """
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already registered")
        self._tools[tool.name] = tool

    def lookup(self, name: str) -> Tool | None:
        """Look up a tool by name.

        Args:
            name: Tool name

        Returns:
            Tool instance or None if not found
        """
        return self._tools.get(name)

    def list_tools(self) -> list[str]:
        """List all registered tool names.

        Returns:
            List of tool names
        """
        return list(self._tools.keys())

    def execute(self, name: str, args: list[Value]) -> Value:
        """Execute a tool by name.

        Args:
            name: Tool name
            args: Tool arguments

        Returns:
            Tool result value

        Raises:
            ToolError: If tool not found or execution fails
        """
        tool = self.lookup(name)
        if tool is None:
            return VToolResult(tool_name=name, result=f"Tool '{name}' not found", success=False)

        try:
            return tool.execute(args)
        except Exception as e:
            return VToolResult(tool_name=name, result=str(e), success=False)


class ToolError(Exception):
    """Error during tool execution."""

    pass


# =============================================================================
# Built-in Tools
# =============================================================================


class IdentityTool(Tool):
    """Identity tool that returns its argument unchanged.

    Useful for testing tool call infrastructure.
    """

    name = "identity"
    description = "Returns the argument unchanged"

    def execute(self, args: list[Value]) -> Value:
        if len(args) != 1:
            return VToolResult(
                tool_name=self.name, result=f"Expected 1 argument, got {len(args)}", success=False
            )
        return VToolResult(tool_name=self.name, result=args[0], success=True)


class EchoTool(Tool):
    """Echo tool that returns a string representation of arguments.

    Useful for debugging and testing.
    """

    name = "echo"
    description = "Returns string representation of arguments"

    def execute(self, args: list[Value]) -> Value:
        # Convert arguments to string representation
        arg_strs = []
        for arg in args:
            match arg:
                case VConstructor(name, []):
                    arg_strs.append(name)
                case VConstructor(name, constr_args):
                    args_repr = " ".join(str(a) for a in constr_args)
                    arg_strs.append(f"({name} {args_repr})")
                case _:
                    arg_strs.append(str(arg))

        result = " ".join(arg_strs) if arg_strs else ""
        return VToolResult(tool_name=self.name, result=result, success=True)


class LLMCallTool(Tool):
    """LLM call tool for invoking LLM APIs.

    Placeholder for LLM FFI integration.
    """

    name = "llm_call"
    description = "Call LLM API with prompt"

    def __init__(self, model: str = "gpt-4", temperature: float = 0.7) -> None:
        self.model = model
        self.temperature = temperature

    def execute(self, args: list[Value]) -> Value:
        if len(args) != 1:
            return VToolResult(
                tool_name=self.name,
                result=f"Expected 1 argument (prompt), got {len(args)}",
                success=False,
            )

        # Placeholder: In real implementation, this would call LLM API
        prompt = str(args[0])
        return VToolResult(
            tool_name=self.name, result=f"[LLM response to: {prompt[:50]}...]", success=True
        )


# Global registry instance
_global_registry: ToolRegistry | None = None


def get_tool_registry() -> ToolRegistry:
    """Get the global tool registry.

    Returns:
        Global ToolRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = ToolRegistry()
    return _global_registry


def reset_tool_registry() -> None:
    """Reset the global tool registry (useful for testing)."""
    global _global_registry
    _global_registry = ToolRegistry()
