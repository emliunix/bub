"""Abstract machine / evaluator for System F core language."""

from systemf.core.ast import (
    Abs,
    App,
    Branch,
    Case,
    Constructor,
    DataDeclaration,
    Declaration,
    Let,
    Pattern,
    TAbs,
    TApp,
    Term,
    TermDeclaration,
    Var,
)
from systemf.core.types import Type
from systemf.eval.value import (
    Environment,
    VClosure,
    VConstructor,
    VNeutral,
    VTypeClosure,
    Value,
)
from systemf.eval.pattern import PatternMatcher


class Evaluator:
    """Call-by-value evaluator for System F core language."""

    def __init__(self) -> None:
        self.pattern_matcher = PatternMatcher()

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
                    value = self.evaluate(body)
                    results[name] = value
        return results
