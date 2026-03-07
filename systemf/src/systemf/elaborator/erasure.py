"""Coercion erasure for System FC.

This module implements zero-cost coercion erasure - removing coercions from
runtime code to ensure coercions are truly zero-cost abstractions.

In System FC, coercions are proofs of type equality that witness safe type
conversions. At runtime, these proofs have no computational content and can
be safely erased without affecting program behavior.

Key transformations:
- Cast(expr, coercion) → expr  (just return the expression)
- Axiom(name, args) → ???  (should not appear in runtime positions)
- All other terms: recursively erase coercions in subterms

Example:
    Before: (Zero ▷ ax_Nat) : Nat
    After:  Zero : Repr(Nat)

    The coercion is erased, leaving just the representation value.

This pass should be run after elaboration but before code generation or
interpretation, ensuring no coercion overhead at runtime.
"""

from __future__ import annotations

from systemf.core import ast as core
from systemf.core.types import Type


def erase_coercions(term: core.Term) -> core.Term:
    """Erase all coercions from a term.

    Recursively processes the term, removing Cast nodes and Axiom terms.
    This ensures zero-cost abstraction for type coercions.

    Args:
        term: The term with coercions to erase

    Returns:
        The term with all coercions erased

    Example:
        >>> from systemf.core.coercion import CoercionAxiom
        >>> from systemf.core.types import TypeConstructor
        >>> axiom = CoercionAxiom("ax_Nat", TypeConstructor("Nat", []), ...)
        >>> cast_term = core.Cast(None, core.Constructor(None, "Zero", []), axiom)
        >>> erased = erase_coercions(cast_term)
        >>> isinstance(erased, core.Constructor)
        True
    """
    match term:
        # Cast: just return the expression, drop the coercion
        case core.Cast(expr=expr):
            return erase_coercions(expr)

        # Axiom: these are proof terms, should not appear at runtime
        # If they do, we can't really execute them, so raise an error
        case core.Axiom():
            raise ValueError(
                f"Axiom term found at runtime position: {term}. "
                "Axioms should be wrapped in Cast and erased."
            )

        # Variables: no coercions to erase
        case core.Var():
            return term

        # Global variables: no coercions to erase
        case core.Global():
            return term

        # Lambda abstraction: erase coercions in the body
        case core.Abs(location, var_name, var_type, body):
            erased_body = erase_coercions(body)
            return core.Abs(location, var_name, var_type, erased_body)

        # Application: erase coercions in both function and argument
        case core.App(location, func, arg):
            erased_func = erase_coercions(func)
            erased_arg = erase_coercions(arg)
            return core.App(location, erased_func, erased_arg)

        # Type abstraction: erase coercions in the body
        case core.TAbs(location, var, body):
            erased_body = erase_coercions(body)
            return core.TAbs(location, var, erased_body)

        # Type application: erase coercions in the function
        case core.TApp(location, func, type_arg):
            erased_func = erase_coercions(func)
            return core.TApp(location, erased_func, type_arg)

        # Constructor: erase coercions in arguments
        case core.Constructor(location, name, args):
            erased_args = [erase_coercions(arg) for arg in args]
            return core.Constructor(location, name, erased_args)

        # Case expression: erase coercions in scrutinee and branches
        case core.Case(location, scrutinee, branches):
            erased_scrutinee = erase_coercions(scrutinee)
            erased_branches = [
                core.Branch(pattern=branch.pattern, body=erase_coercions(branch.body))
                for branch in branches
            ]
            return core.Case(location, erased_scrutinee, erased_branches)

        # Let binding: erase coercions in value and body
        case core.Let(location, name, value, body):
            erased_value = erase_coercions(value)
            erased_body = erase_coercions(body)
            return core.Let(location, name, erased_value, erased_body)

        # Literal: no coercions to erase
        case core.Lit():
            return term

        # Primitive operation: no coercions to erase
        case core.PrimOp():
            return term

        # Tool call: erase coercions in arguments
        case core.ToolCall(location, tool_name, args):
            erased_args = [erase_coercions(arg) for arg in args]
            return core.ToolCall(location, tool_name, erased_args)

        # Declaration-level terms
        case core.TermDeclaration(name, type_annotation, body, pragma, docstring, param_docstrings):
            erased_body = erase_coercions(body) if body else body
            return core.TermDeclaration(
                name=name,
                type_annotation=type_annotation,
                body=erased_body,
                pragma=pragma,
                docstring=docstring,
                param_docstrings=param_docstrings,
            )

        case core.DataDeclaration():
            # Data declarations don't contain runtime terms
            return term

        # Fallback for unknown term types
        case _:
            return term


def erase_module_coercions(module: core.Module) -> core.Module:
    """Erase coercions from all declarations in a module.

    Args:
        module: The module with coercions to erase

    Returns:
        The module with all coercions erased

    Example:
        >>> from systemf.core.module import Module
        >>> module = Module(name="test", declarations=[...], ...)
        >>> erased_module = erase_module_coercions(module)
    """
    erased_decls: list[core.Declaration] = []

    for decl in module.declarations:
        match decl:
            case core.TermDeclaration():
                erased_decl = erase_coercions(decl)
                erased_decls.append(erased_decl)
            case _:
                # Data declarations and other non-term declarations pass through
                erased_decls.append(decl)

    # Return new module with erased declarations
    return core.Module(
        name=module.name,
        declarations=erased_decls,
        constructor_types=module.constructor_types,
        global_types=module.global_types,
        primitive_types=module.primitive_types,
        docstrings=module.docstrings,
        llm_functions=module.llm_functions,
        errors=module.errors,
        warnings=module.warnings,
    )


def is_erased(term: core.Term) -> bool:
    """Check if a term has no coercions.

    Args:
        term: The term to check

    Returns:
        True if the term contains no Cast or Axiom nodes
    """
    match term:
        case core.Cast() | core.Axiom():
            return False
        case core.Var() | core.Global() | core.Lit() | core.PrimOp():
            return True
        case core.Abs(_, _, _, body):
            return is_erased(body)
        case core.App(_, func, arg):
            return is_erased(func) and is_erased(arg)
        case core.TAbs(_, _, body):
            return is_erased(body)
        case core.TApp(_, func, _):
            return is_erased(func)
        case core.Constructor(_, _, args):
            return all(is_erased(arg) for arg in args)
        case core.Case(_, scrutinee, branches):
            return is_erased(scrutinee) and all(is_erased(b.body) for b in branches)
        case core.Let(_, _, value, body):
            return is_erased(value) and is_erased(body)
        case core.ToolCall(_, _, args):
            return all(is_erased(arg) for arg in args)
        case core.TermDeclaration(_, _, body, _, _, _):
            return body is None or is_erased(body)
        case _:
            return True
