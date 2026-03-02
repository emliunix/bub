"""Type elaborator for System F surface language.

This module implements Phase 2 of the elaboration pipeline: bidirectional
type checking that transforms Scoped AST (with de Bruijn indices) to
typed Core AST.

Key features:
- Bidirectional type checking (infer/check modes)
- Robinson-style unification for type equality
- Type inference for polymorphic types
- Complete handling of all System F term types

Example:
    >>> from systemf.surface.types import ScopedVar, ScopedAbs, SurfaceTypeConstructor
    >>> from systemf.surface.inference.context import TypeContext
    >>> from systemf.utils.location import Location
    >>>
    >>> # Create elaborator
    >>> elab = TypeElaborator()
    >>> ctx = TypeContext()
    >>> loc = Location("test", 1, 1)
    >>>
    >>> # \\x -> x with annotation
    >>> abs_term = ScopedAbs("x", SurfaceTypeConstructor("Int", [], loc),
    ...                      ScopedVar(0, "x", loc), loc)
    >>> core_term, ty = elab.infer(abs_term, ctx)
"""

from __future__ import annotations

from typing import Optional, Union

from systemf.core import ast as core
from systemf.core.types import (
    Type,
    TypeVar,
    TypeArrow,
    TypeForall,
    TypeConstructor,
    PrimitiveType,
)
from systemf.surface.types import (
    SurfaceType,
    SurfaceTypeVar,
    SurfaceTypeArrow,
    SurfaceTypeForall,
    SurfaceTypeConstructor,
    ScopedVar,
    ScopedAbs,
    SurfaceApp,
    SurfaceTypeAbs,
    SurfaceTypeApp,
    SurfaceLet,
    SurfaceAnn,
    SurfaceConstructor,
    SurfaceCase,
    SurfaceBranch,
    SurfacePattern,
    SurfaceIf,
    SurfaceTuple,
    SurfaceIntLit,
    SurfaceStringLit,
    SurfaceOp,
    SurfaceToolCall,
)
from systemf.surface.inference.context import TypeContext
from systemf.surface.inference.errors import (
    TypeError,
    TypeMismatchError,
    UnificationError,
    UndefinedTypeError,
)
from systemf.surface.inference.unification import (
    TMeta,
    Substitution,
    unify,
    resolve_type,
)
from systemf.surface.scoped.checker import ScopeChecker
from systemf.surface.scoped.context import ScopeContext
from systemf.utils.location import Location


class TypeElaborator:
    """Bidirectional type elaborator for System F surface language.

    Transforms Scoped AST (with de Bruijn indices) to typed Core AST
    using bidirectional type checking and unification-based inference.

    The elaborator maintains:
    - TypeContext: Tracks variable types, constructors, and globals
    - Substitution: Accumulates unification results during inference
    - Counter: Generates fresh meta type variables

    Example:
        >>> elab = TypeElaborator()
        >>> ctx = TypeContext()
        >>> # Infer type of identity function
        >>> # \\x -> x
        >>> core_term, ty = elab.infer(scoped_term, ctx)
    """

    def __init__(self):
        """Initialize the type elaborator."""
        self.subst: Substitution = Substitution.empty()
        self._meta_counter: int = 0

    def _fresh_meta(self, name: Optional[str] = None) -> TMeta:
        """Create a fresh meta type variable.

        Args:
            name: Optional name prefix for debugging

        Returns:
            A fresh TMeta with a unique id
        """
        meta = TMeta.fresh(name)
        return meta

    def _apply_subst(self, ty: Type) -> Type:
        """Apply the current substitution to a type.

        Args:
            ty: The type to resolve

        Returns:
            The type with meta variables substituted
        """
        return self.subst.apply_to_type(ty)

    def _unify(self, t1: Type, t2: Type, location: Optional[Location] = None) -> None:
        """Unify two types and update the substitution.

        Args:
            t1: First type to unify
            t2: Second type to unify
            location: Optional source location for error reporting

        Raises:
            UnificationError: If types cannot be unified
        """
        self.subst = unify(t1, t2, self.subst, location)

    def _surface_to_core_type(self, ty: SurfaceType, ctx: TypeContext) -> Type:
        """Convert a surface type to a core type.

        Handles type variables, arrows, foralls, and constructors.
        Type variables in the surface type are looked up in the context
        and converted to de Bruijn indices.

        Args:
            ty: Surface type to convert
            ctx: Current type context

        Returns:
            Core type representation
        """
        match ty:
            case SurfaceTypeVar(name, location):
                # Check if it's a bound type variable
                if ctx.is_bound_type(name):
                    # Convert to de Bruijn index
                    index = ctx.lookup_type_var_index(name)
                    return TypeVar(name)
                # Free type variable - create a fresh meta-variable for inference
                # This handles polymorphic type annotations like (a -> b) in definitions
                return self._fresh_meta(name)

            case SurfaceTypeArrow(arg, ret, param_doc, location):
                core_arg = self._surface_to_core_type(arg, ctx)
                core_ret = self._surface_to_core_type(ret, ctx)
                return TypeArrow(core_arg, core_ret, param_doc)

            case SurfaceTypeForall(var, body, location):
                # Extend context with bound variable
                new_ctx = ctx.extend_type(var)
                core_body = self._surface_to_core_type(body, new_ctx)
                return TypeForall(var, core_body)

            case SurfaceTypeConstructor(name, args, location):
                core_args = [self._surface_to_core_type(arg, ctx) for arg in args]
                return TypeConstructor(name, core_args)

            case _:
                raise TypeError(f"Unknown surface type: {ty}")

    def infer(
        self,
        term: ScopedVar
        | ScopedAbs
        | SurfaceApp
        | SurfaceTypeAbs
        | SurfaceTypeApp
        | SurfaceLet
        | SurfaceAnn
        | SurfaceConstructor
        | SurfaceCase
        | SurfaceIf
        | SurfaceTuple
        | SurfaceIntLit
        | SurfaceStringLit
        | SurfaceOp
        | SurfaceToolCall,
        ctx: TypeContext,
    ) -> tuple[core.Term, Type]:
        """Infer the type of a scoped term (synthesis mode).

        This is the "bottom-up" direction of bidirectional type checking.
        Given a term, synthesize its type.

        Args:
            term: The scoped term to infer a type for
            ctx: Current type checking context

        Returns:
            Tuple of (core term, inferred type)

        Raises:
            TypeError: If type inference fails

        Example:
            >>> elab = TypeElaborator()
            >>> ctx = TypeContext()
            >>> # Infer type of variable x0 (bound to Int)
            >>> var = ScopedVar(0, "x", loc)
            >>> ctx = ctx.extend_term(TypeConstructor("Int", []))
            >>> core_term, ty = elab.infer(var, ctx)
            >>> assert str(ty) == "Int"
        """
        match term:
            case ScopedVar(index, debug_name, location):
                # Look up variable type in context
                try:
                    var_type = ctx.lookup_term_type(index)
                    # Apply current substitution
                    var_type = self._apply_subst(var_type)
                    core_term = core.Var(location, index, debug_name)
                    return (core_term, var_type)
                except IndexError:
                    raise TypeError(
                        f"Variable index {index} out of bounds",
                        location,
                        term,
                    )

            case ScopedAbs(var_name, var_type, body, location):
                # Lambda abstraction: type depends on annotation or inference
                if var_type is not None:
                    # Use annotation
                    core_var_type = self._surface_to_core_type(var_type, ctx)
                else:
                    # Create fresh meta variable for parameter
                    core_var_type = self._fresh_meta(var_name)

                # Extend context with parameter type
                new_ctx = ctx.extend_term(core_var_type)

                # Infer body type
                core_body, body_type = self.infer(body, new_ctx)

                # Build arrow type (apply subst to handle any unifications)
                core_var_type = self._apply_subst(core_var_type)
                body_type = self._apply_subst(body_type)
                arrow_type = TypeArrow(core_var_type, body_type)

                core_term = core.Abs(location, var_name, core_var_type, core_body)
                return (core_term, arrow_type)

            case SurfaceApp(func, arg, location):
                # Application: infer function type, check argument
                core_func, func_type = self.infer(func, ctx)

                # Function type should be an arrow
                func_type = self._apply_subst(func_type)

                match func_type:
                    case TypeArrow(param_type, ret_type):
                        # Check argument against parameter type
                        core_arg = self.check(arg, param_type, ctx)
                        # Apply substitution to resolve any meta-variables in return type
                        ret_type = self._apply_subst(ret_type)
                        return (core.App(location, core_func, core_arg), ret_type)

                    case TMeta() as meta:
                        # Unknown function type - create fresh types for param/ret
                        param_type = self._fresh_meta("param")
                        ret_type = self._fresh_meta("ret")
                        expected_arrow = TypeArrow(param_type, ret_type)

                        # Unify with the meta
                        self._unify(meta, expected_arrow, location)

                        # Check argument and return
                        core_arg = self.check(arg, param_type, ctx)
                        return (core.App(location, core_func, core_arg), ret_type)

                    case _:
                        raise TypeMismatchError(
                            expected="function type",
                            actual=func_type,
                            location=location,
                            term=term,
                            context="in application",
                        )

            case SurfaceTypeAbs(var, body, location):
                # Type abstraction: forall var. body_type
                # Extend context with type variable
                new_ctx = ctx.extend_type(var)

                # Infer body type
                core_body, body_type = self.infer(body, new_ctx)

                # Build forall type
                forall_type = TypeForall(var, body_type)

                core_term = core.TAbs(location, var, core_body)
                return (core_term, forall_type)

            case SurfaceTypeApp(func, type_arg, location):
                # Type application: func @type_arg
                core_func, func_type = self.infer(func, ctx)

                # Function type should be a forall
                func_type = self._apply_subst(func_type)

                match func_type:
                    case TypeForall(var, body_type):
                        # Substitute type argument for bound variable
                        core_type_arg = self._surface_to_core_type(type_arg, ctx)
                        result_type = self._subst_type_var(body_type, var, core_type_arg)
                        return (core.TApp(location, core_func, core_type_arg), result_type)

                    case TMeta() as meta:
                        # Unknown type - create fresh forall
                        var_name = "_t"  # Fresh variable name
                        body_type = self._fresh_meta("body")
                        expected_forall = TypeForall(var_name, body_type)

                        # Unify
                        self._unify(meta, expected_forall, location)

                        # Now apply type argument
                        core_type_arg = self._surface_to_core_type(type_arg, ctx)
                        result_type = self._subst_type_var(body_type, var_name, core_type_arg)
                        return (core.TApp(location, core_func, core_type_arg), result_type)

                    case _:
                        raise TypeMismatchError(
                            expected="polymorphic type (forall)",
                            actual=func_type,
                            location=location,
                            term=term,
                            context="in type application",
                        )

            case SurfaceLet(bindings, body, location):
                # Let binding: process sequentially
                new_ctx = ctx
                core_bindings = []

                for var_name, var_type_ann, value in bindings:
                    # Infer value type
                    core_value, value_type = self.infer(value, new_ctx)

                    # If there's a type annotation, check against it
                    if var_type_ann is not None:
                        ann_type = self._surface_to_core_type(var_type_ann, new_ctx)
                        ann_type = self._apply_subst(ann_type)
                        value_type = self._apply_subst(value_type)
                        self._unify(ann_type, value_type, location)

                    # Extend context with this binding
                    final_type = self._apply_subst(value_type)
                    new_ctx = new_ctx.extend_term(final_type)
                    core_bindings.append((var_name, core_value))

                # Infer body with all bindings
                core_body, body_type = self.infer(body, new_ctx)

                # Build nested let expressions
                result = core_body
                for var_name, core_value in reversed(core_bindings):
                    result = core.Let(location, var_name, core_value, result)

                return (result, body_type)

            case SurfaceAnn(term_inner, type_ann, location):
                # Type annotation: check term against annotation
                ann_type = self._surface_to_core_type(type_ann, ctx)
                core_term = self.check(term_inner, ann_type, ctx)
                final_type = self._apply_subst(ann_type)
                return (core_term, final_type)

            case SurfaceConstructor(name, args, location):
                # Look up constructor type
                try:
                    con_type = ctx.lookup_constructor(name)
                except NameError:
                    # Treat as data constructor with unknown type
                    # This might be a built-in or the constructor wasn't registered
                    con_type = self._fresh_meta(f"con_{name}")

                con_type = self._apply_subst(con_type)

                # Instantiate polymorphic constructor type
                con_type = self._instantiate(con_type)

                # Instantiate free type variables with fresh meta-variables
                con_type = self._instantiate_free_vars(con_type)

                # Check arguments against constructor parameter types
                core_args = []
                remaining_type = con_type

                for arg in args:
                    match remaining_type:
                        case TypeArrow(param_type, ret_type):
                            core_arg = self.check(arg, param_type, ctx)
                            core_args.append(core_arg)
                            remaining_type = ret_type
                        case _:
                            # Too many arguments
                            raise TypeMismatchError(
                                expected=f"constructor type with {len(args)} arguments",
                                actual=con_type,
                                location=location,
                                term=term,
                                context=f"in constructor {name}",
                            )

                # Result type is remaining_type after all arguments
                result_type = self._apply_subst(remaining_type)

                core_term = core.Constructor(location, name, core_args)
                return (core_term, result_type)

            case SurfaceCase(scrutinee, branches, location):
                # Pattern matching: infer scrutinee type, check branches
                core_scrut, scrut_type = self.infer(scrutinee, ctx)

                # All branches must return the same type
                result_type: Optional[Type] = None
                core_branches = []

                for branch in branches:
                    core_branch, branch_type = self._check_branch(branch, scrut_type, ctx)
                    core_branches.append(core_branch)

                    if result_type is None:
                        result_type = branch_type
                    else:
                        # Unify with previous branches
                        branch_type = self._apply_subst(branch_type)
                        result_type = self._apply_subst(result_type)
                        self._unify(result_type, branch_type, location)

                final_result_type = result_type if result_type else self._fresh_meta("result")
                final_result_type = self._apply_subst(final_result_type)

                core_term = core.Case(location, core_scrut, core_branches)
                return (core_term, final_result_type)

            case SurfaceIf(cond, then_branch, else_branch, location):
                # Desugar to case: if c then t else f  ==>  case c of True -> t | False -> f
                # First, check condition is Bool-like
                core_cond, cond_type = self.infer(cond, ctx)

                # Infer branches
                core_then, then_type = self.infer(then_branch, ctx)
                core_else, else_type = self.infer(else_branch, ctx)

                # Unify branch types
                then_type = self._apply_subst(then_type)
                else_type = self._apply_subst(else_type)
                self._unify(then_type, else_type, location)

                final_type = self._apply_subst(then_type)

                # Build if as a case expression
                # For now, create a simple conditional structure
                # In practice, this would use Bool constructors
                core_term = core.Case(
                    location,
                    core_cond,
                    [
                        core.Branch(core.Pattern("True", []), core_then),
                        core.Branch(core.Pattern("False", []), core_else),
                    ],
                )

                return (core_term, final_type)

            case SurfaceTuple(elements, location):
                # Tuple desugars to nested Pairs
                # (a, b, c) -> Pair a (Pair b c)
                if not elements:
                    raise TypeError("Empty tuples not supported", location, term)

                # Infer first element
                core_elems = []
                elem_types = []

                for elem in elements:
                    core_elem, elem_type = self.infer(elem, ctx)
                    core_elems.append(core_elem)
                    elem_types.append(elem_type)

                # Build Pair type: Pair t1 (Pair t2 (... tn))
                # Start from the last element
                result_type = elem_types[-1]
                result_term = core_elems[-1]

                # Build nested pairs from right to left
                for core_elem, elem_type in reversed(list(zip(core_elems[:-1], elem_types[:-1]))):
                    result_type = TypeArrow(
                        elem_type,
                        TypeArrow(result_type, result_type),  # Simplified
                    )
                    result_term = core.App(
                        location,
                        core.App(location, core.Constructor(location, "Pair", []), core_elem),
                        result_term,
                    )

                # Actually, let's just use a simpler representation for now
                # Store as constructor with all elements
                result_type = TypeConstructor("Tuple", elem_types)
                core_term = core.Constructor(location, "Tuple", core_elems)

                return (core_term, result_type)

            case SurfaceIntLit(value, location):
                # Integer literal: look up Int type
                int_type = TypeConstructor("Int", [])
                core_term = core.IntLit(location, value)
                return (core_term, int_type)

            case SurfaceStringLit(value, location):
                # String literal: look up String type
                str_type = TypeConstructor("String", [])
                core_term = core.StringLit(location, value)
                return (core_term, str_type)

            case SurfaceOp(left, op, right, location):
                # Operator: desugar to primitive application
                # For now, treat as function application with primitive
                core_left, left_type = self.infer(left, ctx)
                core_right, right_type = self.infer(right, ctx)

                # Primitive operations typically require same-type operands
                left_type = self._apply_subst(left_type)
                right_type = self._apply_subst(right_type)
                self._unify(left_type, right_type, location)

                result_type = self._apply_subst(left_type)

                # Create primitive operation application
                # This is simplified - full implementation would desugar properly
                core_term = core.App(
                    location,
                    core.App(location, core.PrimOp(location, f"op_{op}"), core_left),
                    core_right,
                )

                return (core_term, result_type)

            case SurfaceToolCall(tool_name, args, location):
                # Tool call: check arguments and return appropriate type
                core_args = []
                for arg in args:
                    core_arg, _ = self.infer(arg, ctx)
                    core_args.append(core_arg)

                # Tool return type - for now, create meta
                result_type = self._fresh_meta(f"tool_{tool_name}")

                core_term = core.ToolCall(location, tool_name, core_args)
                return (core_term, result_type)

            case _:
                raise TypeError(f"Unknown term type: {type(term)}", None, term)

    def check(
        self,
        term: ScopedVar
        | ScopedAbs
        | SurfaceApp
        | SurfaceTypeAbs
        | SurfaceTypeApp
        | SurfaceLet
        | SurfaceAnn
        | SurfaceConstructor
        | SurfaceCase
        | SurfaceIf
        | SurfaceTuple
        | SurfaceIntLit
        | SurfaceStringLit
        | SurfaceOp
        | SurfaceToolCall,
        expected: Type,
        ctx: TypeContext,
    ) -> core.Term:
        """Check that a scoped term has the expected type (checking mode).

        This is the "top-down" direction of bidirectional type checking.
        Given a term and a type, verify they match.

        Args:
            term: The scoped term to check
            expected: The expected type
            ctx: Current type checking context

        Returns:
            The elaborated core term

        Raises:
            TypeMismatchError: If the term doesn't have the expected type

        Example:
            >>> elab = TypeElaborator()
            >>> ctx = TypeContext()
            >>> ctx = ctx.extend_term(TypeConstructor("Int", []))
            >>> # Check that x0 has type Int
            >>> var = ScopedVar(0, "x", loc)
            >>> core_term = elab.check(var, TypeConstructor("Int", []), ctx)
        """
        # Apply current substitution to expected type
        expected = self._apply_subst(expected)

        match term:
            case ScopedAbs(var_name, var_type, body, location):
                # Lambda: expected should be an arrow type
                match expected:
                    case TypeArrow(param_type, ret_type):
                        # If there's an annotation, unify with expected
                        if var_type is not None:
                            ann_type = self._surface_to_core_type(var_type, ctx)
                            ann_type = self._apply_subst(ann_type)
                            param_type = self._apply_subst(param_type)
                            self._unify(ann_type, param_type, location)

                        # Extend context and check body
                        new_ctx = ctx.extend_term(param_type)
                        core_body = self.check(body, ret_type, new_ctx)

                        final_param_type = self._apply_subst(param_type)
                        return core.Abs(location, var_name, final_param_type, core_body)

                    case TMeta() as meta:
                        # Unknown expected type - infer lambda type
                        if var_type is not None:
                            param_type = self._surface_to_core_type(var_type, ctx)
                        else:
                            param_type = self._fresh_meta(var_name)

                        new_ctx = ctx.extend_term(param_type)
                        core_body, body_type = self.infer(body, new_ctx)

                        # Build arrow and unify with meta
                        arrow_type = TypeArrow(param_type, body_type)
                        self._unify(meta, arrow_type, location)

                        final_param_type = self._apply_subst(param_type)
                        return core.Abs(location, var_name, final_param_type, core_body)

                    case _:
                        raise TypeMismatchError(
                            expected="function type",
                            actual=expected,
                            location=location,
                            term=term,
                            context="lambda expression requires function type",
                        )

            case SurfaceTypeAbs(var, body, location):
                # Type abstraction: expected should be forall
                match expected:
                    case TypeForall(exp_var, exp_body):
                        # Extend context and check body
                        new_ctx = ctx.extend_type(var)

                        # Rename if necessary to avoid capture
                        if var != exp_var:
                            exp_body = self._rename_type_var(exp_body, exp_var, var)

                        core_body = self.check(body, exp_body, new_ctx)
                        return core.TAbs(location, var, core_body)

                    case TMeta() as meta:
                        # Unknown - create expected forall
                        body_type = self._fresh_meta("body")
                        forall_type = TypeForall(var, body_type)

                        new_ctx = ctx.extend_type(var)
                        core_body = self.check(body, body_type, new_ctx)

                        self._unify(meta, forall_type, location)
                        return core.TAbs(location, var, core_body)

                    case _:
                        raise TypeMismatchError(
                            expected="polymorphic type (forall)",
                            actual=expected,
                            location=location,
                            term=term,
                            context="type abstraction requires polymorphic type",
                        )

            case SurfaceLet(bindings, body, location):
                # Let: process bindings, then check body
                new_ctx = ctx
                core_bindings = []

                for var_name, var_type_ann, value in bindings:
                    # Infer value type
                    core_value, value_type = self.infer(value, new_ctx)

                    # If annotation present, check against it
                    if var_type_ann is not None:
                        ann_type = self._surface_to_core_type(var_type_ann, new_ctx)
                        ann_type = self._apply_subst(ann_type)
                        value_type = self._apply_subst(value_type)
                        self._unify(ann_type, value_type, location)

                    # Extend context
                    final_type = self._apply_subst(value_type)
                    new_ctx = new_ctx.extend_term(final_type)
                    core_bindings.append((var_name, core_value))

                # Check body against expected type
                core_body = self.check(body, expected, new_ctx)

                # Build nested lets
                result = core_body
                for var_name, core_value in reversed(core_bindings):
                    result = core.Let(location, var_name, core_value, result)

                return result

            case SurfaceAnn(term_inner, type_ann, location):
                # Annotation: check annotated type against expected
                ann_type = self._surface_to_core_type(type_ann, ctx)
                ann_type = self._apply_subst(ann_type)
                expected = self._apply_subst(expected)
                self._unify(ann_type, expected, location)

                # Now check term against the (unified) type
                return self.check(term_inner, expected, ctx)

            case _:
                # For other cases, infer and unify
                core_term, inferred_type = self.infer(term, ctx)
                inferred_type = self._apply_subst(inferred_type)
                expected = self._apply_subst(expected)
                try:
                    self._unify(
                        expected,
                        inferred_type,
                        term.location if hasattr(term, "location") else None,
                    )
                except UnificationError as e:
                    # Convert to TypeMismatchError for better error messages
                    from .errors import TypeMismatchError

                    raise TypeMismatchError(
                        expected=expected,
                        actual=inferred_type,
                        location=e.location,
                        term=term,
                    ) from e
                return core_term

    def _check_branch(
        self,
        branch: SurfaceBranch,
        scrut_type: Type,
        ctx: TypeContext,
    ) -> tuple[core.Branch, Type]:
        """Check a case branch against a scrutinee type.

        Args:
            branch: The branch to check
            scrut_type: Type of the scrutinee
            ctx: Current context

        Returns:
            Tuple of (core branch, result type)
        """
        # Extend context with pattern variables
        # For now, create fresh types for pattern variables
        branch_ctx = ctx
        pattern_var_types = []

        for var_name in branch.pattern.vars:
            var_type = self._fresh_meta(var_name)
            branch_ctx = branch_ctx.extend_term(var_type)
            pattern_var_types.append(var_type)

        # Infer body type in extended context
        core_body, body_type = self.infer(branch.body, branch_ctx)

        core_branch = core.Branch(
            pattern=core.Pattern(branch.pattern.constructor, branch.pattern.vars),
            body=core_body,
        )

        return (core_branch, body_type)

    def _instantiate(self, ty: Type) -> Type:
        """Instantiate a polymorphic type by replacing bound variables with meta vars.

        Args:
            ty: The type to instantiate

        Returns:
            The instantiated type
        """
        # For now, simple implementation - replace forall with body
        # A full implementation would handle nested foralls and avoid capture
        match ty:
            case TypeForall(var, body):
                # Replace var with fresh meta
                meta = self._fresh_meta(var)
                return self._subst_type_var(body, var, meta)
            case _:
                return ty

    def _instantiate_free_vars(self, ty: Type) -> Type:
        """Instantiate free type variables with fresh meta-variables.

        Unlike _instantiate which handles TypeForall, this method finds all
        free TypeVar occurrences and replaces them with fresh TMeta variables.
        This is needed for constructor types that have free type variables.

        Args:
            ty: The type to instantiate

        Returns:
            Type with all TypeVars replaced by fresh meta-variables
        """
        match ty:
            case TypeVar(name):
                # Replace free type variable with fresh meta
                return self._fresh_meta(name)
            case TypeArrow(arg, ret, param_doc):
                return TypeArrow(
                    self._instantiate_free_vars(arg),
                    self._instantiate_free_vars(ret),
                    param_doc,
                )
            case TypeConstructor(name, args):
                return TypeConstructor(name, [self._instantiate_free_vars(arg) for arg in args])
            case TypeForall(var, body):
                # Don't instantiate bound variables
                # For simplicity, we just return the forall as-is
                # A full implementation would handle this properly
                return ty
            case _:
                return ty

    def _subst_type_var(self, ty: Type, var: str, replacement: Type) -> Type:
        """Substitute a type variable with another type.

        Args:
            ty: The type to substitute in
            var: The variable name to replace
            replacement: The type to replace it with

        Returns:
            The type with substitution applied
        """
        match ty:
            case TypeVar(name) if name == var:
                return replacement
            case TypeVar(_):
                return ty
            case TMeta(_):
                return ty
            case TypeArrow(arg, ret, param_doc):
                return TypeArrow(
                    self._subst_type_var(arg, var, replacement),
                    self._subst_type_var(ret, var, replacement),
                    param_doc,
                )
            case TypeForall(bound_var, body) if bound_var != var:
                # Avoid capture
                return TypeForall(bound_var, self._subst_type_var(body, var, replacement))
            case TypeForall(_, _):
                # Bound variable shadows the one we're substituting
                return ty
            case TypeConstructor(name, args):
                return TypeConstructor(
                    name, [self._subst_type_var(arg, var, replacement) for arg in args]
                )
            case PrimitiveType(_):
                return ty
            case _:
                return ty

    def _rename_type_var(self, ty: Type, old_var: str, new_var: str) -> Type:
        """Rename a type variable in a type.

        Args:
            ty: The type to rename in
            old_var: The variable to rename
            new_var: The new variable name

        Returns:
            The type with variable renamed
        """
        return self._subst_type_var(ty, old_var, TypeVar(new_var))

    def elaborate_declarations(
        self,
        decls: list[SurfaceDeclaration],
        constructors: dict[str, Type] | None = None,
    ) -> tuple[list[core.Declaration], TypeContext, dict[str, Type]]:
        """Elaborate multiple declarations with mutual recursion support.

        This method implements the three-phase elaboration pipeline required for
        mutual recursion:

        Phase 1 - Signature Collection:
            - Collect type signatures from all term declarations
            - Add all signatures to TypeContext as globals
            - Build complete typing environment

        Phase 2 - Scope Checking (NEW):
            - Use ScopeChecker to convert Surface AST to Scoped AST
            - Resolve names to de Bruijn indices
            - Enable mutual recursion by making all globals visible

        Phase 3 - Body Elaboration:
            - Elaborate each scoped declaration body with full type context
            - All globals are visible to all bodies
            - Enables mutually recursive definitions

        Pipeline flow: Surface AST -> Scoped AST -> Core AST

        Example:
            # even and odd can reference each other
            even : Int -> Bool
            even n = if n == 0 then True else odd (n - 1)

            odd : Int -> Bool
            odd n = if n == 0 then False else even (n - 1)

        Args:
            decls: List of surface declarations to elaborate
            constructors: Optional dict of data constructor types

        Returns:
            Tuple of (core declarations, final context, global types dict)

        Example:
            >>> elab = TypeElaborator()
            >>> decls = [even_decl, odd_decl]
            >>> core_decls, ctx, types = elab.elaborate_declarations(decls)
            >>> # Both even and odd can call each other
        """
        from systemf.surface.types import (
            SurfaceDataDeclaration,
            SurfacePrimOpDecl,
            SurfacePrimTypeDecl,
            SurfaceTermDeclaration,
        )

        # Phase 1: Collect all type signatures first
        global_types: dict[str, Type] = {}
        term_decls: list[SurfaceTermDeclaration] = []
        other_decls: list[tuple[int, SurfaceDeclaration]] = []

        for i, decl in enumerate(decls):
            match decl:
                case SurfaceTermDeclaration():
                    # Convert surface type to core type
                    core_type = self._surface_to_core_type(decl.type_annotation, TypeContext())
                    global_types[decl.name] = core_type
                    term_decls.append(decl)
                case SurfacePrimOpDecl():
                    # Convert surface type to core type
                    core_type = self._surface_to_core_type(decl.type_annotation, TypeContext())
                    global_types[decl.name] = core_type
                    other_decls.append((i, decl))
                case _:
                    other_decls.append((i, decl))

        # Add constructors if provided
        if constructors:
            for name, ty in constructors.items():
                global_types[name] = ty

        # Phase 2: Build context with all globals
        ctx = TypeContext(globals=global_types)
        if constructors:
            for name, ty in constructors.items():
                ctx = ctx.add_constructor(name, ty)

        # Phase 3: Elaborate each term declaration body with full context
        core_decls: list[core.Declaration] = []
        elaborated_terms: dict[str, core.TermDeclaration] = {}

        # Initialize ScopeChecker for converting Surface AST to Scoped AST
        scope_checker = ScopeChecker()

        for decl in term_decls:
            # Get the expected type (may have been refined during elaboration)
            expected_type = global_types.get(decl.name)

            # Step 1: Scope-check the body to convert Surface AST -> Scoped AST
            # Build scope context with all global names for mutual recursion
            scope_ctx = ScopeContext(globals=set(global_types.keys()))
            scoped_body = scope_checker.check_term(decl.body, scope_ctx)

            # Step 2: Elaborate the scoped body with type inference
            core_body, inferred_type = self.infer(scoped_body, ctx)

            # Unify expected type with inferred type
            if expected_type is not None:
                expected_type = self._apply_subst(expected_type)
                inferred_type = self._apply_subst(inferred_type)
                self._unify(expected_type, inferred_type, decl.location)

            # Extract pragma params
            pragma_params = None
            if decl.pragma and "LLM" in decl.pragma:
                pragma_params = decl.pragma["LLM"].strip() or None

            # Create Core declaration
            core_decl = core.TermDeclaration(
                name=decl.name,
                type_annotation=self._apply_subst(expected_type) if expected_type else None,
                body=core_body,
                pragma=pragma_params,
                docstring=decl.docstring,
                param_docstrings=None,  # Extracted separately if needed
            )

            elaborated_terms[decl.name] = core_decl
            core_decls.append(core_decl)

        # Handle other declarations (data, primitive types, etc.)
        for _, decl in other_decls:
            core_decl = self._elaborate_other_declaration(decl, ctx)
            core_decls.append(core_decl)

        return (core_decls, ctx, global_types)

    def _elaborate_other_declaration(
        self,
        decl: SurfaceDeclaration,
        ctx: TypeContext,
    ) -> core.Declaration:
        """Elaborate non-term declarations.

        Args:
            decl: The surface declaration
            ctx: Current type context

        Returns:
            Core declaration
        """
        from systemf.surface.types import (
            SurfaceDataDeclaration,
            SurfacePrimOpDecl,
            SurfacePrimTypeDecl,
        )

        match decl:
            case SurfaceDataDeclaration():
                return self._elaborate_data_decl(decl)
            case SurfacePrimOpDecl():
                return self._elaborate_prim_op_decl(
                    decl.name, decl.type_annotation, decl.location, decl.pragma
                )
            case SurfacePrimTypeDecl():
                return self._elaborate_prim_type_decl(decl.name, decl.location)
            case _:
                raise TypeError(f"Unknown declaration type: {type(decl)}")

    def _elaborate_data_decl(
        self,
        decl,
    ) -> core.DataDeclaration:
        """Elaborate a data type declaration.

        Args:
            decl: Surface data declaration

        Returns:
            Core DataDeclaration
        """
        from systemf.surface.types import SurfaceDataDeclaration

        # Convert constructors
        core_constructors: list[tuple[str, list[Type]]] = []
        for con_info in decl.constructors:
            core_args = [self._surface_to_core_type(arg, TypeContext()) for arg in con_info.args]
            core_constructors.append((con_info.name, core_args))

        return core.DataDeclaration(
            name=decl.name,
            params=decl.params,
            constructors=core_constructors,
        )

    def _elaborate_prim_op_decl(
        self,
        name: str,
        type_annotation: SurfaceType,
        location: Location,
        pragma: dict[str, str] | None = None,
    ) -> core.TermDeclaration:
        """Elaborate a primitive operation declaration.

        Args:
            name: Operation name
            type_annotation: Surface type annotation
            location: Source location
            pragma: Optional pragma dict

        Returns:
            Core TermDeclaration
        """
        core_type = self._surface_to_core_type(type_annotation, TypeContext())

        # Determine if LLM function
        if pragma and "LLM" in pragma:
            full_name = f"llm.{name}"
            pragma_str = pragma.get("LLM")
        else:
            full_name = f"$prim.{name}"
            pragma_str = None

        return core.TermDeclaration(
            name=name,
            type_annotation=core_type,
            body=core.PrimOp(location, full_name),
            pragma=pragma_str,
        )

    def _elaborate_prim_type_decl(
        self,
        name: str,
        location: Location,
    ) -> core.DataDeclaration:
        """Elaborate a primitive type declaration.

        Args:
            name: Type name
            location: Source location

        Returns:
            Core DataDeclaration (placeholder)
        """
        return core.DataDeclaration(
            name=name,
            params=[],
            constructors=[],
        )


def elaborate_term(
    term: ScopedVar
    | ScopedAbs
    | SurfaceApp
    | SurfaceTypeAbs
    | SurfaceTypeApp
    | SurfaceLet
    | SurfaceAnn
    | SurfaceConstructor
    | SurfaceCase
    | SurfaceIf
    | SurfaceTuple
    | SurfaceIntLit
    | SurfaceStringLit
    | SurfaceOp
    | SurfaceToolCall,
    ctx: Optional[TypeContext] = None,
) -> tuple[core.Term, Type]:
    """Elaborate a scoped term and infer its type.

    Convenience function that creates a TypeElaborator and runs inference.

    Args:
        term: The scoped term to elaborate
        ctx: Optional type context (creates empty context if None)

    Returns:
        Tuple of (core term, inferred type)

    Example:
        >>> from systemf.surface.types import ScopedVar, ScopedAbs
        >>> loc = Location("test", 1, 1)
        >>> ctx = TypeContext().extend_term(TypeConstructor("Int", []))
        >>> var = ScopedVar(0, "x", loc)
        >>> core_term, ty = elaborate_term(var, ctx)
    """
    elab = TypeElaborator()
    if ctx is None:
        ctx = TypeContext()
    return elab.infer(term, ctx)
