"""Abstract machine / evaluator for System F core language."""

import os
import re
from typing import Callable

from systemf.core.ast import (
    Abs,
    App,
    Case,
    Constructor,
    DataDeclaration,
    Declaration,
    Global,
    Let,
    Lit,
    PrimOp,
    TAbs,
    TApp,
    Term,
    TermDeclaration,
    ToolCall,
    Var,
)
from systemf.core.module import LLMMetadata
from systemf.eval.value import (
    Environment,
    VClosure,
    VConstructor,
    VPrim,
    VPrimOp,
    VPrimOpPartial,
    VTypeClosure,
    Value,
)
from systemf.eval.pattern import PatternMatcher
from systemf.eval.tools import get_tool_registry
from systemf.eval.primitives import PRIMITIVE_IMPLEMENTATIONS


class Evaluator:
    """Call-by-value evaluator for System F core language."""

    def __init__(self, global_env: dict[str, Value] | None = None) -> None:
        self.pattern_matcher = PatternMatcher()
        self.global_env = global_env if global_env is not None else {}
        self.primitive_impls: dict[str, Callable[[Value, Value], Value]] = (
            PRIMITIVE_IMPLEMENTATIONS.copy()
        )
        # Registry for LLM function closures: name -> (metadata, closure)
        self.llm_closures: dict[str, tuple[LLMMetadata, Callable[[Value], Value]]] = {}

    def register_llm_closure(self, name: str, metadata: LLMMetadata) -> None:
        """Register an LLM function closure.

        Args:
            name: The function name (without $llm. prefix)
            metadata: LLMMetadata with prompt info and fallback
        """

        # Create closure that captures metadata
        def llm_closure(arg: Value) -> Value:
            return self._execute_llm_call(metadata, arg)

        self.llm_closures[name] = (metadata, llm_closure)

    def _execute_llm_call(self, metadata: LLMMetadata, arg: Value) -> Value:
        """Execute LLM call with given metadata and argument.

        Args:
            metadata: LLM function metadata
            arg: The argument value to process

        Returns:
            Value from LLM or fallback
        """
        try:
            # Craft prompt from metadata
            prompt = self._craft_prompt(metadata, arg)

            # Call LLM API
            response = self._call_llm_api(metadata, prompt)

            # Parse response based on return type
            return self._parse_llm_response(metadata, response)
        except Exception as e:
            # Fallback: return the argument unchanged
            # This implements the "fallback to lambda body" behavior
            # where the lambda body is the identity function
            return arg

    def _craft_prompt(self, metadata: LLMMetadata, arg: Value) -> str:
        """Craft LLM prompt from metadata and argument."""
        lines = []

        # Add function docstring
        if metadata.function_docstring:
            lines.append(metadata.function_docstring)
            lines.append("")

        # Add parameter info (use indices since arg names not available per design spec)
        if len(metadata.arg_types) > 0:
            lines.append("Parameters:")
            for i, _ in enumerate(metadata.arg_types):
                doc = metadata.arg_docstrings[i] if i < len(metadata.arg_docstrings) else None
                if doc:
                    lines.append(f"  arg{i}: {doc}")
                else:
                    lines.append(f"  arg{i}")
            lines.append("")

        # Add the input value
        lines.append("Input:")
        lines.append(self._value_to_string(arg))

        return "\n".join(lines)

    def _value_to_string(self, value: Value) -> str:
        """Convert a Value to string representation."""
        match value:
            case VPrim("Int", n):
                return str(n)
            case VPrim("String", s):
                return s
            case VConstructor(name, args):
                if not args:
                    return name
                args_str = " ".join(self._value_to_string(a) for a in args)
                return f"({name} {args_str})"
            case _:
                return str(value)

    def _call_llm_api(self, metadata: LLMMetadata, prompt: str) -> str:
        """Call LLM API (OpenAI or Anthropic).

        Args:
            metadata: Contains pragma_params for model and temperature settings
            prompt: The crafted prompt

        Returns:
            LLM response text
        """
        # Parse model and temperature from pragma_params
        pragma = metadata.pragma_params or ""
        model_match = re.search(r"model=([^\s,]+)", pragma)
        model = model_match.group(1) if model_match else "gpt-4"
        temp_match = re.search(r"temperature=([^\s,]+)", pragma)
        temperature = float(temp_match.group(1)) if temp_match else 0.7

        # Try OpenAI first if model looks like an OpenAI model
        if model.startswith("gpt-") or model.startswith("o"):
            return self._call_openai(model, temperature, prompt)
        # Try Anthropic for Claude models
        elif model.startswith("claude-"):
            return self._call_anthropic(model, temperature, prompt)
        else:
            # Default to OpenAI for unknown models
            return self._call_openai(model, temperature, prompt)

    def _call_openai(self, model: str, temperature: float, prompt: str) -> str:
        """Call OpenAI API - NOT IMPLEMENTED.

        This is a stub for future implementation. For now, always raises.
        """
        raise RuntimeError("LLM API calls not yet implemented")

    def _call_anthropic(self, model: str, temperature: float, prompt: str) -> str:
        """Call Anthropic API - NOT IMPLEMENTED.

        This is a stub for future implementation. For now, always raises.
        """
        raise RuntimeError("LLM API calls not yet implemented")

    def _parse_llm_response(self, metadata: LLMMetadata, response: str) -> Value:
        """Parse LLM response into a Value.

        For now, assumes String return type. Future: parse based on type annotation.
        """
        # Strip whitespace and return as VPrim String
        return VPrim("String", response.strip())

    def evaluate(self, term: Term, env: Environment | None = None) -> Value:
        """Evaluate term to a value.

        Uses call-by-value evaluation order.
        Types are erased (not evaluated).
        """
        if env is None:
            env = Environment.empty()

        match term:
            case Var(index=index):
                # Variable lookup
                return env.lookup(index)

            case Global(name=name):
                # Global variable lookup
                if name not in self.global_env:
                    raise RuntimeError(f"Undefined global: {name}")
                return self.global_env[name]

            case Abs(var_type=var_type, body=body):
                # Create closure capturing current environment
                return VClosure(env, body)

            case App(func=func, arg=arg):
                # Evaluate function and argument
                func_val = self.evaluate(func, env)
                arg_val = self.evaluate(arg, env)
                return self.apply(func_val, arg_val)

            case TAbs(var=var, body=body):
                # Type abstraction - create closure
                return VTypeClosure(env, body)

            case TApp(func=func, type_arg=type_arg):
                # Type application - just evaluate function
                # Type argument is erased
                func_val = self.evaluate(func, env)
                return self.type_apply(func_val)

            case Constructor(name=name, args=args):
                # Evaluate all arguments
                arg_vals = [self.evaluate(arg, env) for arg in args]
                return VConstructor(name, arg_vals)

            case Case(scrutinee=scrutinee, branches=branches):
                # Evaluate scrutinee
                scrut_val = self.evaluate(scrutinee, env)
                # Select matching branch
                branch, bindings = self.pattern_matcher.select_branch(scrut_val, branches)
                # Extend environment with pattern bindings
                # Bindings are in pattern order; we add in reverse so first binding is at index 0
                new_env = env
                for binding in reversed(bindings):
                    new_env = new_env.extend(binding)
                # Evaluate branch body
                return self.evaluate(branch.body, new_env)

            case Let(name=name, value=value, body=body):
                # Evaluate value first (call-by-value)
                val = self.evaluate(value, env)
                # Extend environment
                new_env = env.extend(val)
                # Evaluate body
                return self.evaluate(body, new_env)

            case Lit(prim_type=prim_type, value=value):
                # Literal evaluates to VPrim
                return VPrim(prim_type, value)

            case PrimOp(name=name):
                # Primitive operation creates a function that can be applied
                # Return a closure that wraps the primitive implementation
                return self._make_primop_closure(name)

            case ToolCall(tool_name=tool_name, args=args):
                # Evaluate all arguments (call-by-value)
                arg_vals = [self.evaluate(arg, env) for arg in args]
                # Execute tool through registry
                registry = get_tool_registry()
                return registry.execute(tool_name, arg_vals)

            case _:
                raise RuntimeError(f"Unknown term type: {type(term)}")

    def apply(self, func: Value, arg: Value) -> Value:
        """Apply function value to argument."""
        match func:
            case VClosure(env=closure_env, body=body):
                # Extend closure environment with argument
                new_env = closure_env.extend(arg)
                # Evaluate body in extended environment
                return self.evaluate(body, new_env)
            case VPrimOp(name=name, impl=impl):
                # Check if this is an LLM primitive (unary)
                if name.startswith("llm."):
                    # LLM primitives are unary - execute immediately
                    return impl(arg, arg)  # Pass arg as both args for compatibility
                # Regular primitive operations are binary - first application creates partial
                return VPrimOpPartial(name, impl, arg)
            case VPrimOpPartial(name=name, impl=impl, first_arg=first_arg):
                # Second application - execute the primitive
                return impl(first_arg, arg)
            case _:
                raise RuntimeError(f"Cannot apply non-function: {func}")

    def type_apply(self, func: Value) -> Value:
        """Apply type abstraction (types are erased)."""
        match func:
            case VTypeClosure(env=closure_env, body=body):
                # Just evaluate the body
                # Type variable is not needed at runtime
                return self.evaluate(body, closure_env)
            case _:
                raise RuntimeError(f"Cannot type-apply non-type-abstraction: {func}")

    def _make_primop_closure(self, name: str) -> Value:
        """Create a closure for a primitive operation.

        Returns a curried function that takes two Int arguments.
        Handles both regular primitives and LLM primitives ($llm.*).
        """
        # Check if this is an LLM primitive
        if name.startswith("llm."):
            llm_name = name[4:]  # Strip "llm." prefix
            if llm_name in self.llm_closures:
                metadata, closure = self.llm_closures[llm_name]
                # Return a special wrapper that applies the LLM closure
                return self._make_llm_wrapper(llm_name, closure)
            raise RuntimeError(f"Unknown LLM primitive: {llm_name}")

        # PrimOp stores name without $prim. prefix, registry uses full names
        full_name = f"$prim.{name}"
        if full_name not in self.primitive_impls:
            raise RuntimeError(f"Unknown primitive: {name}")

        impl = self.primitive_impls[full_name]

        # Create a closure that expects two arguments
        # We use a special representation that the apply method will recognize
        return VPrimOp(name, impl)

    def _make_llm_wrapper(self, name: str, closure: Callable[[Value], Value]) -> Value:
        """Create a wrapper for an LLM closure.

        The LLM closure takes one argument and returns a Value.
        Since LLM functions are unary, we return a VClosure that evaluates immediately.
        """
        # Create a simple wrapper closure that calls the LLM closure
        # This avoids the binary primitive infrastructure

        # Create a simple term that when evaluated will call the closure
        # We use a special marker to identify this as an LLM call
        class LLMCallTerm(Term):
            """Special term type for LLM calls."""

            def __init__(self, closure_fn: Callable[[Value], Value], arg: Value):
                self.closure_fn = closure_fn
                self.arg = arg

            def __str__(self) -> str:
                return f"<llm-call {name}>"

        # Return a VPrimOp that takes one argument
        def llm_impl(_: Value, arg: Value) -> Value:
            """Implementation that calls LLM closure and handles fallback."""
            try:
                return closure(arg)
            except Exception:
                # Fallback to identity
                return arg

        return VPrimOp(f"llm.{name}", llm_impl)

    def evaluate_program(self, decls: list[Declaration]) -> dict[str, Value]:
        """Evaluate a sequence of declarations.

        Returns mapping from declaration names to their values.
        """
        results = {}
        for decl in decls:
            match decl:
                case DataDeclaration(name, params, constructors):
                    # Data declarations don't produce values at runtime
                    # But we might want to register them
                    pass
                case TermDeclaration(name, type_annotation, body):
                    # Add placeholder to global_env BEFORE evaluation
                    # This allows recursive definitions to work
                    self.global_env[name] = VConstructor("<recursive>", [])
                    value = self.evaluate(body)
                    self.global_env[name] = value
                    results[name] = value
        return results
