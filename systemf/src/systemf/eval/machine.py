"""Abstract machine / evaluator for System F core language."""

from typing import Callable

from systemf.core.ast import (
    Abs,
    App,
    Case,
    Constructor,
    DataDeclaration,
    Declaration,
    Global,
    IntLit,
    Let,
    PrimOp,
    StringLit,
    TAbs,
    TApp,
    Term,
    TermDeclaration,
    ToolCall,
    Var,
)
from systemf.eval.value import (
    Environment,
    VClosure,
    VConstructor,
    VInt,
    VPrimOp,
    VPrimOpPartial,
    VString,
    VTypeClosure,
    Value,
)
from systemf.eval.pattern import PatternMatcher
from systemf.eval.tools import get_tool_registry


class Evaluator:
    """Call-by-value evaluator for System F core language."""

    def __init__(self, global_env: dict[str, Value] | None = None) -> None:
        self.pattern_matcher = PatternMatcher()
        self.global_env = global_env if global_env is not None else {}
        self.primitive_impls: dict[str, Callable[[Value, Value], Value]] = {
            "int_plus": self._int_plus,
            "int_minus": self._int_minus,
            "int_multiply": self._int_multiply,
            "int_divide": self._int_divide,
            "int_negate": self._int_negate,
            "int_eq": self._int_eq,
            "int_lt": self._int_lt,
            "int_gt": self._int_gt,
            "string_concat": self._string_concat,
            "string_length": self._string_length,
        }

    def _int_plus(self, x: Value, y: Value) -> Value:
        """Integer addition."""
        if not isinstance(x, VInt) or not isinstance(y, VInt):
            raise RuntimeError("int_plus expects Int arguments")
        return VInt(x.value + y.value)

    def _int_minus(self, x: Value, y: Value) -> Value:
        """Integer subtraction."""
        if not isinstance(x, VInt) or not isinstance(y, VInt):
            raise RuntimeError("int_minus expects Int arguments")
        return VInt(x.value - y.value)

    def _int_multiply(self, x: Value, y: Value) -> Value:
        """Integer multiplication."""
        if not isinstance(x, VInt) or not isinstance(y, VInt):
            raise RuntimeError("int_multiply expects Int arguments")
        return VInt(x.value * y.value)

    def _int_divide(self, x: Value, y: Value) -> Value:
        """Integer division."""
        if not isinstance(x, VInt) or not isinstance(y, VInt):
            raise RuntimeError("int_divide expects Int arguments")
        if y.value == 0:
            raise RuntimeError("Division by zero")
        return VInt(x.value // y.value)

    def _int_negate(self, x: Value, _y: Value) -> Value:
        """Integer negation (unary minus).

        Note: This is a unary operation (Int -> Int) but the primitive
        infrastructure expects binary operations. The second argument is ignored.
        """
        if not isinstance(x, VInt):
            raise RuntimeError("int_negate expects Int argument")
        return VInt(-x.value)

    def _int_eq(self, x: Value, y: Value) -> Value:
        """Integer equality."""
        from systemf.eval.value import VConstructor

        if not isinstance(x, VInt) or not isinstance(y, VInt):
            raise RuntimeError("int_eq expects Int arguments")
        return VConstructor("True" if x.value == y.value else "False", [])

    def _int_lt(self, x: Value, y: Value) -> Value:
        """Integer less than."""
        from systemf.eval.value import VConstructor

        if not isinstance(x, VInt) or not isinstance(y, VInt):
            raise RuntimeError("int_lt expects Int arguments")
        return VConstructor("True" if x.value < y.value else "False", [])

    def _int_gt(self, x: Value, y: Value) -> Value:
        """Integer greater than."""
        from systemf.eval.value import VConstructor

        if not isinstance(x, VInt) or not isinstance(y, VInt):
            raise RuntimeError("int_gt expects Int arguments")
        return VConstructor("True" if x.value > y.value else "False", [])

    def _string_concat(self, x: Value, y: Value) -> Value:
        """String concatenation."""
        if not isinstance(x, VString) or not isinstance(y, VString):
            raise RuntimeError("string_concat expects String arguments")
        return VString(x.value + y.value)

    def _string_length(self, x: Value, y: Value) -> Value:
        """String length.

        Note: This is a unary operation (String -> Int) but the primitive
        infrastructure expects binary operations. The second argument is ignored.
        """
        if not isinstance(x, VString):
            raise RuntimeError("string_length expects String argument")
        return VInt(len(x.value))

    def evaluate(self, term: Term, env: Environment | None = None) -> Value:
        """Evaluate term to a value.

        Uses call-by-value evaluation order.
        Types are erased (not evaluated).
        """
        if env is None:
            env = Environment.empty()

        match term:
            case Var(index):
                # Variable lookup
                return env.lookup(index)

            case Global(name):
                # Global variable lookup
                if name not in self.global_env:
                    raise RuntimeError(f"Undefined global: {name}")
                return self.global_env[name]

            case Abs(var_type, body):
                # Create closure capturing current environment
                return VClosure(env, body)

            case App(func, arg):
                # Evaluate function
                func_val = self.evaluate(func, env)
                # Evaluate argument (call-by-value)
                arg_val = self.evaluate(arg, env)
                # Apply
                return self.apply(func_val, arg_val)

            case TAbs(var, body):
                # Type abstraction - create closure
                return VTypeClosure(env, body)

            case TApp(func, type_arg):
                # Type application - just evaluate function
                # Type argument is erased
                func_val = self.evaluate(func, env)
                return self.type_apply(func_val)

            case Constructor(name, args):
                # Evaluate all arguments
                arg_vals = [self.evaluate(arg, env) for arg in args]
                return VConstructor(name, arg_vals)

            case Case(scrutinee, branches):
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

            case Let(name, value, body):
                # Evaluate value first (call-by-value)
                val = self.evaluate(value, env)
                # Extend environment
                new_env = env.extend(val)
                # Evaluate body
                return self.evaluate(body, new_env)

            case IntLit(value):
                # Integer literal evaluates to VInt
                return VInt(value)

            case StringLit(value):
                # String literal evaluates to VString
                return VString(value)

            case PrimOp(name):
                # Primitive operation creates a function that can be applied
                # Return a closure that wraps the primitive implementation
                return self._make_primop_closure(name)

            case ToolCall(tool_name, args):
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
            case VClosure(closure_env, body):
                # Extend closure environment with argument
                new_env = closure_env.extend(arg)
                # Evaluate body in extended environment
                return self.evaluate(body, new_env)
            case VPrimOp(name, impl):
                # Primitive operations are binary - first application creates partial
                return VPrimOpPartial(name, impl, arg)
            case VPrimOpPartial(name, impl, first_arg):
                # Second application - execute the primitive
                return impl(first_arg, arg)
            case _:
                raise RuntimeError(f"Cannot apply non-function: {func}")

    def type_apply(self, func: Value) -> Value:
        """Apply type abstraction (types are erased)."""
        match func:
            case VTypeClosure(closure_env, body):
                # Just evaluate the body
                # Type variable is not needed at runtime
                return self.evaluate(body, closure_env)
            case _:
                raise RuntimeError(f"Cannot type-apply non-type-abstraction: {func}")

    def _make_primop_closure(self, name: str) -> Value:
        """Create a closure for a primitive operation.

        Returns a curried function that takes two Int arguments.
        """
        from systemf.core.ast import Var, Abs, App

        if name not in self.primitive_impls:
            raise RuntimeError(f"Unknown primitive: {name}")

        impl = self.primitive_impls[name]

        # Create a closure that expects two arguments
        # We use a special representation that the apply method will recognize
        return VPrimOp(name, impl)

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
