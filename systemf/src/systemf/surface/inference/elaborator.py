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
    >>> abs_term = ScopedAbs("x", SurfaceTypeConstructor(name="Int", args=[], location=loc),
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
    GlobalVar,
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
    SurfaceLit,
    SurfaceOp,
    SurfaceToolCall,
    SurfaceDeclaration,
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
from systemf.elaborator.scc import SCCAnalyzer, SCCNode, analyze_type_dependencies
from systemf.elaborator.coercion_axioms import (
    CoercionAxiomGenerator,
    generate_axioms_for_declarations,
    ADTAxiom,
)


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
            case SurfaceTypeVar(location=_, name=name):
                # Check if it's a type variable (lowercase or underscore) vs constructor (uppercase)
                if name[0].islower() or name == "_":
                    # It's a type variable
                    if ctx.is_bound_type(name):
                        # Convert to de Bruijn index
                        index = ctx.lookup_type_var_index(name)
                        return TypeVar(name)
                    # Free type variable - create a fresh meta-variable for inference
                    # This handles polymorphic type annotations like (a -> b) in definitions
                    return self._fresh_meta(name)
                else:
                    # It's a type constructor (Int, Bool, etc.)
                    return TypeConstructor(name, [])

            case SurfaceTypeArrow(location=_, arg=arg, ret=ret, param_doc=param_doc):
                core_arg = self._surface_to_core_type(arg, ctx)
                core_ret = self._surface_to_core_type(ret, ctx)
                return TypeArrow(core_arg, core_ret, param_doc)

            case SurfaceTypeForall(location=_, var=var, body=body):
                # Extend context with bound variable
                new_ctx = ctx.extend_type(var)
                core_body = self._surface_to_core_type(body, new_ctx)
                return TypeForall(var, core_body)

            case SurfaceTypeConstructor(location=_, name=name, args=args):
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
        | SurfaceLit
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
            case ScopedVar(location=location, index=index, debug_name=debug_name):
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

            case GlobalVar(location=location, name=name):
                # Try looking up as a data constructor first
                try:
                    con_type = ctx.lookup_constructor(name)
                    # Constructor with no args - return Constructor node with empty args
                    con_type = self._instantiate(con_type)
                    con_type = self._instantiate_free_vars(con_type)
                    con_type = self._apply_subst(con_type)
                    core_term = core.Constructor(location, name, [])
                    return (core_term, con_type)
                except NameError:
                    pass

                # Not a constructor, try global variable lookup
                try:
                    var_type = ctx.lookup_global(name)
                    # Apply current substitution
                    var_type = self._apply_subst(var_type)
                    # Create Global node for global variables
                    core_term = core.Global(location, name)
                    return (core_term, var_type)
                except NameError:
                    raise TypeError(
                        f"Undefined variable '{name}'",
                        location,
                        term,
                    )

            case ScopedAbs(location=location, var_name=var_name, var_type=var_type, body=body):
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

            case SurfaceApp(location=location, func=func, arg=arg):
                # Application: infer function type, check argument
                core_func, func_type = self.infer(func, ctx)

                # Function type should be an arrow
                func_type = self._apply_subst(func_type)

                # Handle implicit instantiation for polymorphic functions
                # If func has type ∀a. ..., instantiate it with fresh meta-variables
                match func_type:
                    case TypeForall(_, _):
                        func_type = self._instantiate(func_type)
                        func_type = self._apply_subst(func_type)

                match func_type:
                    case TypeArrow(param_type, ret_type):
                        # Check argument against parameter type
                        core_arg = self.check(arg, param_type, ctx)
                        # Apply substitution to resolve any meta-variables in return type
                        ret_type = self._apply_subst(ret_type)

                        # If the function is a data constructor, accumulate the argument
                        # instead of creating a separate App node
                        match core_func:
                            case core.Constructor(name=name, args=args):
                                return (
                                    core.Constructor(location, name, args + [core_arg]),
                                    ret_type,
                                )
                            case _:
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

            case SurfaceTypeAbs(location=location, var=var, body=body):
                # Type abstraction: forall var. body_type
                # Extend context with type variable
                new_ctx = ctx.extend_type(var)

                # Infer body type
                core_body, body_type = self.infer(body, new_ctx)

                # Build forall type
                forall_type = TypeForall(var, body_type)

                core_term = core.TAbs(location, var, core_body)
                return (core_term, forall_type)

            case SurfaceTypeApp(location=location, func=func, type_arg=type_arg):
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

            case SurfaceLet(location=location, bindings=bindings, body=body):
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

            case SurfaceAnn(location=location, term=term_inner, type=type_ann):
                # Type annotation: check term against annotation
                ann_type = self._surface_to_core_type(type_ann, ctx)
                core_term = self.check(term_inner, ann_type, ctx)
                final_type = self._apply_subst(ann_type)
                return (core_term, final_type)

            case SurfaceConstructor(location=location, name=name, args=args):
                # Look up constructor type
                try:
                    con_type = ctx.lookup_constructor(name)
                except NameError:
                    # Treat as data constructor with unknown type
                    # This might be a built-in or the constructor wasn't registered
                    con_type = self._fresh_meta(f"con_{name}")

                # Instantiate polymorphic constructor type (handles nested foralls)
                con_type = self._instantiate(con_type)

                # Instantiate free type variables with fresh meta-variables
                con_type = self._instantiate_free_vars(con_type)

                # Apply substitution to resolve any meta-variables
                con_type = self._apply_subst(con_type)

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

                # Check for coercion axiom to convert from representation to abstract type
                # This handles ADT representation coercions in System FC
                core_term, result_type = self._maybe_add_coercion(
                    core_term, result_type, location, ctx
                )

                return (core_term, result_type)

            case SurfaceCase(location=location, scrutinee=scrutinee, branches=branches):
                # Pattern matching: infer scrutinee type, check branches
                core_scrut, scrut_type = self.infer(scrutinee, ctx)

                # Check for inverse coercion - if scrutinee type is abstract ADT,
                # we need to convert it to representation type for pattern matching
                scrut_type = self._apply_subst(scrut_type)
                core_scrut, scrut_type = self._maybe_add_inverse_coercion(
                    core_scrut, scrut_type, location, ctx
                )

                # Collect all branch results first
                branch_results: list[tuple[core.Branch, Type]] = []
                for branch in branches:
                    core_branch, branch_type = self._check_branch(branch, scrut_type, ctx)
                    branch_results.append((core_branch, branch_type))

                # All branches must return the same type
                # Apply current substitution to all branch types first
                for i in range(len(branch_results)):
                    branch_results[i] = (
                        branch_results[i][0],
                        self._apply_subst(branch_results[i][1]),
                    )

                # Now unify all branches to find common type
                if len(branch_results) > 0:
                    result_type = branch_results[0][1]
                    for i in range(1, len(branch_results)):
                        self._unify(result_type, branch_results[i][1], location)
                        result_type = self._apply_subst(result_type)
                else:
                    result_type = self._fresh_meta("result")

                final_result_type = self._apply_subst(result_type)
                core_branches = [br for br, _ in branch_results]

                core_term = core.Case(location, core_scrut, core_branches)
                return (core_term, final_result_type)

            case SurfaceIf(
                location=location, cond=cond, then_branch=then_branch, else_branch=else_branch
            ):
                # Desugar to case: if c then t else f  ==>  case c of True -> t | False -> f
                # First, check condition is Bool-like
                core_cond, cond_type = self.infer(cond, ctx)

                # Infer branches
                core_then, then_type = self.infer(then_branch, ctx)
                core_else, else_type = self.infer(else_branch, ctx)

                # Paper Section 7.1: Multi-branch constructs
                # Use two-way subsumption for polymorphic branches (Choice 3)
                # This ensures branches are equivalent under subsumption relation
                then_type = self._apply_subst(then_type)
                else_type = self._apply_subst(else_type)

                # Two-way subsumption: check that types are equivalent
                # ⊢^dsk ρ₁ ≤ ρ₂ and ⊢^dsk ρ₂ ≤ ρ₁
                try:
                    self._subs_check(then_type, else_type, location)
                    self._subs_check(else_type, then_type, location)
                except TypeMismatchError:
                    # Fall back to unification for simple cases
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

            case SurfaceTuple(location=location, elements=elements):
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

            case SurfaceLit(prim_type=prim_type, value=value, location=location):
                # Literal: look up type based on prim_type
                lit_type = TypeConstructor(prim_type, [])
                core_term = core.Lit(source_loc=location, prim_type=prim_type, value=value)
                return (core_term, lit_type)

            case SurfaceOp(location=location, left=left, op=op, right=right):
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

            case SurfaceToolCall(location=location, tool_name=tool_name, args=args):
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
        | SurfaceLit
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
            case ScopedAbs(location=location, var_name=var_name, var_type=var_type, body=body):
                # Lambda: expected should be an arrow type (or forall that instantiates to arrow)
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

                    case TypeForall(_, _) as forall_type:
                        # Lambda against forall: instantiate and check
                        # Example: checking `λx → x` against `∀a. a → a`
                        # Instantiate to get `a → a` (with fresh meta), then check lambda
                        instantiated = self._instantiate(forall_type)
                        instantiated = self._apply_subst(instantiated)

                        # Now check the lambda against the instantiated type
                        # This will match the TypeArrow case above
                        return self.check(term, instantiated, ctx)

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

            case SurfaceTypeAbs(location=location, var=var, body=body):
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

            case SurfaceLet(location=location, bindings=bindings, body=body):
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

            case SurfaceAnn(location=location, term=term_inner, type=type_ann):
                # Annotation: check annotated type against expected
                ann_type = self._surface_to_core_type(type_ann, ctx)
                ann_type = self._apply_subst(ann_type)
                expected = self._apply_subst(expected)
                self._unify(ann_type, expected, location)

                # Now check term against the (unified) type
                return self.check(term_inner, expected, ctx)

            case SurfaceCase(location=location, scrutinee=scrutinee, branches=branches):
                # Case expression: infer scrutinee, check branches against expected result
                core_scrut, scrut_type = self.infer(scrutinee, ctx)

                # Check all branches against the expected result type
                core_branches = []
                for branch in branches:
                    core_branch = self._check_branch_check_mode(branch, scrut_type, expected, ctx)
                    core_branches.append(core_branch)

                return core.Case(location, core_scrut, core_branches)

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
        expected_result: Type | None = None,
    ) -> tuple[core.Branch, Type]:
        """Check a case branch against a scrutinee type.

        Args:
            branch: The branch to check
            scrut_type: Type of the scrutinee
            ctx: Current context
            expected_result: Expected result type for the branch body (bidirectional checking)

        Returns:
            Tuple of (core branch, result type)
        """
        # Look up constructor and validate pattern
        constr_name = branch.pattern.constructor
        arg_types: list[Type] = []

        if constr_name in ctx.constructors:
            constr_type = ctx.constructors[constr_name]
            # Instantiate polymorphic constructor type
            constr_type = self._instantiate(constr_type)
            constr_type = self._apply_subst(constr_type)

            # Extract argument types and result type from constructor
            # Constructor type is: arg1 -> arg2 -> ... -> ResultType
            current = constr_type
            while isinstance(current, TypeArrow):
                arg_types.append(current.arg)
                current = current.ret
            result_type = current

            # Unify constructor result with scrutinee type
            self._unify(result_type, scrut_type, branch.location)

        # Bind pattern variables with correct types
        branch_ctx = ctx
        for i, var_name in enumerate(branch.pattern.vars):
            if i < len(arg_types):
                var_type = arg_types[i]
            else:
                # Unknown constructor or too many pattern variables
                var_type = self._fresh_meta(var_name)
            var_type = self._apply_subst(var_type)
            branch_ctx = branch_ctx.extend_term(var_type)

        # Check or infer body type based on bidirectional typing
        # According to Pierce & Turner, case branches should CHECK against expected type
        if expected_result is not None:
            core_body = self.check(branch.body, expected_result, branch_ctx)
            body_type = expected_result
        else:
            core_body, body_type = self.infer(branch.body, branch_ctx)

        core_branch = core.Branch(
            pattern=core.Pattern(branch.pattern.constructor, branch.pattern.vars),
            body=core_body,
        )

        return (core_branch, body_type)

    def _check_branch_check_mode(
        self,
        branch: SurfaceBranch,
        scrut_type: Type,
        expected_result: Type,
        ctx: TypeContext,
    ) -> core.Branch:
        """Check a case branch against scrutinee and expected result types.

        This is used in checking mode (bidirectional type checking) where we
        know the expected result type and check branches against it.

        Args:
            branch: The branch to check
            scrut_type: Type of the scrutinee
            expected_result: Expected result type for the branch body
            ctx: Current context

        Returns:
            The elaborated core branch
        """
        # Look up constructor and validate pattern
        constr_name = branch.pattern.constructor
        arg_types: list[Type] = []

        if constr_name in ctx.constructors:
            constr_type = ctx.constructors[constr_name]
            # Instantiate polymorphic constructor type
            constr_type = self._instantiate(constr_type)
            constr_type = self._apply_subst(constr_type)

            # Extract argument types and result type from constructor
            # Constructor type is: arg1 -> arg2 -> ... -> ResultType
            current = constr_type
            while isinstance(current, TypeArrow):
                arg_types.append(current.arg)
                current = current.ret
            result_type = current

            # Unify constructor result with scrutinee type
            self._unify(result_type, scrut_type, branch.location)

        # Bind pattern variables with correct types
        branch_ctx = ctx
        for i, var_name in enumerate(branch.pattern.vars):
            if i < len(arg_types):
                var_type = arg_types[i]
            else:
                # Unknown constructor or too many pattern variables
                var_type = self._fresh_meta(var_name)
            var_type = self._apply_subst(var_type)
            branch_ctx = branch_ctx.extend_term(var_type)

        # Check body against expected result type (bidirectional checking)
        core_body = self.check(branch.body, expected_result, branch_ctx)

        return core.Branch(
            pattern=core.Pattern(branch.pattern.constructor, branch.pattern.vars),
            body=core_body,
        )

    def _instantiate(self, ty: Type) -> Type:
        """Instantiate a polymorphic type by replacing bound variables with meta vars.

        Args:
            ty: The type to instantiate

        Returns:
            The instantiated type
        """
        # Handle nested foralls recursively by continuing to instantiate
        # after substituting the outer forall variable
        match ty:
            case TypeForall(var, body):
                # Replace var with fresh meta
                meta = self._fresh_meta(var)
                # Recursively instantiate nested foralls
                return self._instantiate(self._subst_type_var(body, var, meta))
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

    def _subs_check(self, sigma1: Type, sigma2: Type, location: Optional[Location] = None) -> None:
        """Check that sigma1 is at least as polymorphic as sigma2 (subsumption).

        Implements the DEEP-SKOL rule from Putting2007 paper (Section 4.6, Figure 8):

            pr(σ₂) = ∀ā.ρ    ā ∉ ftv(σ₁)    ⊢^dsk* σ₁ ≤ ρ
            ----------------------------------------------
            ⊢^dsk σ₁ ≤ σ₂

        This is used for checking that one type is "more polymorphic than" another,
        which is essential for:
        - Function argument checking (contravariant in argument position)
        - Multi-branch construct typing (if/case with polymorphic branches)

        Args:
            sigma1: The type that should be more polymorphic (actual)
            sigma2: The type that should be less polymorphic (expected)
            location: Source location for error reporting

        Raises:
            TypeMismatchError: If sigma1 is not at least as polymorphic as sigma2
        """
        # Skolemize sigma2 (replace ∀ with fresh skolem constants)
        skol_tvs, rho2 = self._skolemise(sigma2)

        # Check sigma1 ≤ rho2 (sigma1 is at least as polymorphic as skolemized sigma2)
        self._subs_check_rho(sigma1, rho2, location)

        # Check that skolem constants didn't escape (aren't free in sigma1 or sigma2)
        if skol_tvs:
            # For now, simplified check - in full implementation would check
            # that skol_tvs don't appear in the final types
            pass

    def _subs_check_rho(self, sigma: Type, rho: Type, location: Optional[Location] = None) -> None:
        """Check that sigma is at least as polymorphic as rho (rho is skolemized).

        Implements SPEC, FUN, and MONO rules from Putting2007 paper.

        Args:
            sigma: The polymorphic type
            rho: The rho type (no top-level forall)
            location: Source location for error reporting
        """
        match sigma:
            case TypeForall(_, _):
                # SPEC rule: Instantiate outer foralls and continue
                rho1 = self._instantiate(sigma)
                self._subs_check_rho(rho1, rho, location)

            case TypeArrow(arg1, ret1, _) if isinstance(rho, TypeArrow):
                # FUN rule: Function subsumption is contravariant in argument
                # σ₁ → σ₂ ≤ σ₃ → σ₄  iff  σ₃ ≤ σ₁ and σ₂ ≤ σ₄
                arg2, ret2 = rho.arg, rho.ret

                # Check arg2 ≤ arg1 (contravariant!)
                self._subs_check(arg2, arg1, location)

                # Check ret1 ≤ ret2 (covariant)
                self._subs_check_rho(ret1, ret2, location)

            case TypeArrow(_, _, _):
                # sigma is arrow but rho is not - try to unify
                self._unify(sigma, rho, location)

            case _:
                # MONO rule: Unify monomorphic types
                self._unify(sigma, rho, location)

    def _skolemise(self, ty: Type) -> tuple[list[str], Type]:
        """Weak prenex conversion: pr(σ) = ∀ā.ρ.

        From Putting2007 paper Section 4.5:
        - PRPOLY: pr(∀ā.σ) = ∀āb̄.ρ where pr(σ) = ∀b̄.ρ
        - PRFUN:  pr(σ₁→σ₂) = ∀ā.(σ₁→ρ₂) where pr(σ₂) = ∀ā.ρ₂, ā ∉ fv(σ₁)
        - PRMONO: pr(τ) = τ

        Returns skolem constants and the rho body.

        Args:
            ty: The type to skolemize

        Returns:
            Tuple of (skolem variable names, rho type)
        """
        skolems: list[str] = []
        current = ty

        while True:
            match current:
                case TypeForall(var, body):
                    # Create skolem constant for this bound variable
                    skolem_name = f"_skol_{var}_{len(skolems)}"
                    skolems.append(skolem_name)
                    # Substitute skolem for bound variable
                    current = self._subst_type_var(body, var, TypeVar(skolem_name))

                case TypeArrow(arg, ret, doc):
                    # Check if return type has foralls that can be hoisted
                    match ret:
                        case TypeForall(ret_var, ret_body):
                            # PRFUN: hoist foralls from return type
                            # pr(σ₁→∀ā.σ₂) = ∀ā.(σ₁→σ₂) if ā ∉ fv(σ₁)
                            skolem_name = f"_skol_{ret_var}_{len(skolems)}"
                            skolems.append(skolem_name)
                            new_ret = self._subst_type_var(ret_body, ret_var, TypeVar(skolem_name))
                            current = TypeArrow(arg, new_ret, doc)
                            # Continue processing in case there are more foralls
                            continue
                        case _:
                            break
                case _:
                    break

        return skolems, current

    def _maybe_add_coercion(
        self,
        term: core.Term,
        result_type: Type,
        location: Optional[Location],
        ctx: TypeContext,
    ) -> tuple[core.Term, Type]:
        """Add coercion cast to constructor if ADT axiom exists.

        In System FC, data constructors produce values in representation types
        (Repr(T)), but the expected type is the abstract type (T). This method
        checks if there's a coercion axiom for the result type and wraps the
        constructor in a Cast if needed.

        Args:
            term: The elaborated constructor term
            result_type: The type produced by the constructor
            location: Source location for error reporting
            ctx: Current type context with coercion axioms

        Returns:
            Tuple of (possibly cast-wrapped term, final type)
        """
        # Check if result_type is a type constructor that has a coercion axiom
        match result_type:
            case TypeConstructor(name=type_name):
                axiom_name = f"ax_{type_name}"
                if ctx.is_coercion_axiom(axiom_name):
                    # Found a coercion axiom - wrap in Cast
                    from systemf.core.coercion import CoercionSym

                    axiom = ctx.lookup_coercion_axiom(axiom_name)
                    # Constructor produces Repr(T), but expected type is T.
                    # ax_Nat : Nat ~ Repr(Nat), so Sym(ax_Nat) : Repr(Nat) ~ Nat
                    # We need to cast from Repr(Nat) to Nat, so use Sym(axiom).
                    cast_term = core.Cast(location, term, CoercionSym(axiom))
                    return (cast_term, result_type)
            case _:
                pass

        # No coercion needed
        return (term, result_type)

    def _maybe_add_inverse_coercion(
        self,
        term: core.Term,
        scrut_type: Type,
        location: Optional[Location],
        ctx: TypeContext,
    ) -> tuple[core.Term, Type]:
        """Add inverse coercion cast when destructuring ADT values.

        In System FC, pattern matching on ADT values requires converting from
        abstract type (T) to representation type (Repr(T)) first. This method
        checks if the scrutinee type has a coercion axiom and wraps the scrutinee
        in a Cast with the inverse (symmetric) coercion.

        For example:
            - scrutinee has type Nat (abstract)
            - We need to convert to Repr(Nat) for pattern matching
            - Use Cast(scrutinee, Sym(ax_Nat)) : Repr(Nat)

        Args:
            term: The elaborated scrutinee term
            scrut_type: The type of the scrutinee (expected to be abstract ADT)
            location: Source location for error reporting
            ctx: Current type context with coercion axioms

        Returns:
            Tuple of (possibly cast-wrapped term, representation type)
        """
        from systemf.core.coercion import CoercionSym

        # Check if scrut_type is a type constructor that has a coercion axiom
        match scrut_type:
            case TypeConstructor(name=type_name):
                axiom_name = f"ax_{type_name}"
                if ctx.is_coercion_axiom(axiom_name):
                    # Found a coercion axiom - use direct axiom for pattern matching
                    axiom = ctx.lookup_coercion_axiom(axiom_name)
                    # Pattern matching: scrutinee has type Nat (abstract), cast to Repr(Nat).
                    # ax_Nat : Nat ~ Repr(Nat), so use axiom directly (not Sym).
                    # axiom takes us from Nat to Repr(Nat) exactly as needed.
                    cast_term = core.Cast(location, term, axiom)
                    # Return the representation type
                    repr_type = axiom.right
                    return (cast_term, repr_type)
            case _:
                pass

        # No coercion needed
        return (term, scrut_type)

    def elaborate_declarations(
        self,
        decls: list[SurfaceDeclaration],
        constructors: dict[str, Type] | None = None,
        global_types: dict[str, Type] | None = None,
        global_terms: set[str] | None = None,
    ) -> tuple[list[core.Declaration], TypeContext, dict[str, Type], dict[str, Type]]:
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
        # Start with existing global context from REPL (accumulated style)
        global_types: dict[str, Type] = dict(global_types) if global_types else {}
        existing_terms: set[str] = set(global_terms) if global_terms else set()

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

        # Phase 2: Elaborate data declarations FIRST to get constructor types
        # This must happen before term declarations so constructors are available
        # Create initial context with globals AND input constructors
        ctx = TypeContext(globals=global_types, constructors=constructors or {})

        core_decls: list[core.Declaration] = []
        all_constructor_types: dict[str, Type] = {}

        for _, decl in other_decls:
            core_decl, con_types = self._elaborate_other_declaration(decl, ctx)
            core_decls.append(core_decl)
            # Collect constructor types from data declarations
            all_constructor_types.update(con_types)
            # Add constructors to global_types and context
            for name, ty in con_types.items():
                global_types[name] = ty
                ctx = ctx.add_constructor(name, ty)

        # Phase 3: Add input constructors to context as well
        if constructors:
            for name, ty in constructors.items():
                ctx = ctx.add_constructor(name, ty)

        # Phase 3.5: Generate coercion axioms for ADTs
        # Run SCC analysis and generate coercion axioms for data declarations
        ctx = self._generate_coercion_axioms(other_decls, ctx)

        # Phase 4: Elaborate each term declaration body with full context
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

            # Step 2: Elaborate the scoped body
            # Use bidirectional checking: if we have expected type, check against it
            # Otherwise infer the type
            if expected_type is not None:
                core_body = self.check(scoped_body, expected_type, ctx)
                inferred_type = expected_type
            else:
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

        return (core_decls, ctx, global_types, all_constructor_types)

    def _elaborate_other_declaration(
        self,
        decl: SurfaceDeclaration,
        ctx: TypeContext,
    ) -> tuple[core.Declaration, dict[str, Type]]:
        """Elaborate non-term declarations.

        Args:
            decl: The surface declaration
            ctx: Current type context

        Returns:
            Tuple of (Core declaration, constructor types dict)
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
                core_decl = self._elaborate_prim_op_decl(
                    decl.name, decl.type_annotation, decl.location, decl.pragma
                )
                return (core_decl, {})
            case SurfacePrimTypeDecl():
                core_decl = self._elaborate_prim_type_decl(decl.name, decl.location)
                return (core_decl, {})
            case _:
                raise TypeError(f"Unknown declaration type: {type(decl)}")

    def _elaborate_data_decl(
        self,
        decl,
    ) -> tuple[core.DataDeclaration, dict[str, Type]]:
        """Elaborate a data type declaration.

        Args:
            decl: Surface data declaration

        Returns:
            Tuple of (Core DataDeclaration, constructor types dict)
        """
        from systemf.surface.types import SurfaceDataDeclaration
        from systemf.core.types import TypeForall, TypeArrow, TypeVar, TypeConstructor

        # Build the result type constructor
        # For "data Maybe a = ...", this is "Maybe a"
        result_type = TypeConstructor(decl.name, [TypeVar(p) for p in decl.params])

        # Create a context with type parameters bound
        # This ensures type variables in constructor args are properly resolved
        type_ctx = TypeContext()
        for param in decl.params:
            type_ctx = type_ctx.extend_type(param)

        # Convert constructors and build their types
        core_constructors: list[tuple[str, list[Type]]] = []
        constructor_types: dict[str, Type] = {}

        for con_info in decl.constructors:
            core_args = [self._surface_to_core_type(arg, type_ctx) for arg in con_info.args]
            core_constructors.append((con_info.name, core_args))

            # Build constructor type: args -> result
            con_type: Type = result_type
            for arg in reversed(core_args):
                con_type = TypeArrow(arg, con_type)

            # Add forall for each type parameter
            for param in reversed(decl.params):
                con_type = TypeForall(param, con_type)

            constructor_types[con_info.name] = con_type

        data_decl = core.DataDeclaration(
            name=decl.name,
            params=decl.params,
            constructors=core_constructors,
        )

        return (data_decl, constructor_types)

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
            full_name = name
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

    def _generate_coercion_axioms(
        self,
        other_decls: list[tuple[int, SurfaceDeclaration]],
        ctx: TypeContext,
    ) -> TypeContext:
        """Generate coercion axioms for ADT declarations.

        This method implements Phase 3.5 of the System FC elaboration pipeline:
        1. Run SCC analysis to identify recursive ADT groups
        2. Generate coercion axioms for each data declaration
        3. Add axioms to the type context for use during elaboration

        Args:
            other_decls: List of (index, declaration) tuples from elaboration
            ctx: Current type context

        Returns:
            Updated type context with coercion axioms added
        """
        from systemf.surface.types import SurfaceDataDeclaration

        # Extract data declarations for SCC analysis
        data_decls: list[SurfaceDataDeclaration] = []
        for _, decl in other_decls:
            if isinstance(decl, SurfaceDataDeclaration):
                data_decls.append(decl)

        if not data_decls:
            # No data declarations to process
            return ctx

        # Build SCC nodes from data declarations
        scc_nodes: list[SCCNode[SurfaceDataDeclaration]] = []
        decl_map: dict[str, SurfaceDataDeclaration] = {}

        for decl in data_decls:
            # Find dependencies (types referenced in constructor arguments)
            dependencies: set[str] = set()
            for con_info in decl.constructors:
                for arg_type in con_info.args:
                    # Extract type names from arguments
                    self._collect_type_dependencies(arg_type, dependencies)

            node = SCCNode(
                id=decl.name,
                data=decl,
                dependencies=list(dependencies),
            )
            scc_nodes.append(node)
            decl_map[decl.name] = decl

        # Run SCC analysis
        analyzer = SCCAnalyzer(scc_nodes)
        scc_result = analyzer.analyze()

        # Generate coercion axioms for each data declaration
        axiom_generator = CoercionAxiomGenerator()

        # Process components in order (respecting dependencies)
        for component in scc_result.components:
            for node_id in component.get_node_ids():
                if node_id in decl_map:
                    decl = decl_map[node_id]
                    # Generate axiom: ax_Name : Name ~ Repr(Name)
                    core_decl = self._convert_surface_to_core_data_decl(decl)
                    adt_axiom = axiom_generator.generate_axiom(core_decl)

                    # Add axiom to context
                    ctx = ctx.add_coercion_axiom(adt_axiom.coercion)

        return ctx

    def _collect_type_dependencies(
        self,
        surface_type: SurfaceType,
        dependencies: set[str],
    ) -> None:
        """Collect type constructor names from a surface type.

        Args:
            surface_type: Surface type to analyze
            dependencies: Set to add dependency names to
        """
        from systemf.surface.types import (
            SurfaceTypeConstructor,
            SurfaceTypeArrow,
            SurfaceTypeForall,
        )

        match surface_type:
            case SurfaceTypeConstructor(name=name, args=args):
                dependencies.add(name)
                for arg in args:
                    self._collect_type_dependencies(arg, dependencies)
            case SurfaceTypeArrow(arg=arg, ret=ret):
                self._collect_type_dependencies(arg, dependencies)
                self._collect_type_dependencies(ret, dependencies)
            case SurfaceTypeForall(body=body):
                self._collect_type_dependencies(body, dependencies)
            case _:
                pass

    def _convert_surface_to_core_data_decl(
        self,
        decl: SurfaceDataDeclaration,
    ) -> core.DataDeclaration:
        """Convert a surface data declaration to core data declaration.

        Args:
            decl: Surface data declaration

        Returns:
            Core data declaration
        """
        core_constructors: list[tuple[str, list[Type]]] = []

        for con_info in decl.constructors:
            core_args = [self._surface_to_core_type(arg, TypeContext()) for arg in con_info.args]
            core_constructors.append((con_info.name, core_args))

        return core.DataDeclaration(
            name=decl.name,
            params=decl.params,
            constructors=core_constructors,
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
    | SurfaceLit
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
