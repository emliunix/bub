"""Bidirectional type inference algorithm for System F surface language.

This module provides the core bidirectional type inference algorithm used by
the term elaboration pass. It is a UTILITY CLASS, not a PipelinePass.

The algorithm implements the "Putting2007" paper (Complete and Decidable Type
Inference for GADTs) with bidirectional checking (infer/check modes).

Key features:
- Synthesis mode (infer): Given a term, compute its type
- Checking mode (check): Given a term and a type, verify they match
- Polymorphic type generalization (infer_sigma/check_sigma)
- Subsumption checking for polymorphic types
- Skolemization for polymorphic type checking

Example:
    >>> from systemf.surface.inference.bidi_inference import BidiInference
    >>> from systemf.surface.inference.context import TypeContext
    >>> from systemf.utils.location import Location
    >>>
    >>> bidi = BidiInference()
    >>> ctx = TypeContext()
    >>> loc = Location("test", 1, 1)
    >>>
    >>> # Infer type of a term
    >>> core_term, ty = bidi.infer(scoped_term, ctx)
    >>>
    >>> # Check term against expected type
    >>> core_term = bidi.check(scoped_term, expected_type, ctx)
"""

from __future__ import annotations

from typing import Optional

from systemf.core import ast as core
from systemf.core.types import (
    Type,
    TypeVar,
    TypeArrow,
    TypeForall,
    TypeConstructor,
    TypeSkolem,
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
    SurfaceIf,
    SurfaceTuple,
    SurfaceLit,
    SurfaceOp,
    SurfaceToolCall,
)
from systemf.surface.inference.context import TypeContext
from systemf.surface.inference.errors import (
    TypeMismatchError,
    UnificationError,
)
from systemf.surface.inference.unification import (
    TMeta,
    Substitution,
    unify,
)


def _fresh_binder_names(count: int, ty: Type) -> list[str]:
    """Generate fresh binder names not already used in ty."""
    used = ty.free_vars()
    candidates = [chr(c) for c in range(ord("a"), ord("z") + 1)] + [
        f"{chr(c)}{i}" for i in range(1, 100) for c in range(ord("a"), ord("z") + 1)
    ]
    result = []
    for name in candidates:
        if name not in used and len(result) < count:
            result.append(name)
    return result


class BidiInference:
    """Bidirectional type inference engine.

    This class implements the core bidirectional type inference algorithm
    for System F surface terms. It operates on scoped terms (with de Bruijn
    indices) and produces typed core terms.

    The inference maintains:
    - Substitution: Accumulates unification results during inference
    - Meta counter: Generates fresh meta type variables
    - Skolem counter: Generates fresh skolem constants for polymorphism

    Example:
        >>> bidi = BidiInference()
        >>> ctx = TypeContext()
        >>> # Infer type of identity function
        >>> core_term, ty = bidi.infer(scoped_term, ctx)
    """

    def __init__(self):
        """Initialize the bidirectional inference engine."""
        self.subst: Substitution = Substitution.empty()
        self._meta_counter: int = 0
        self._skolem_counter: int = 0

    def _fresh_skolem(self, name: str) -> TypeSkolem:
        """Create a fresh rigid skolem constant."""
        uid = self._skolem_counter
        self._skolem_counter += 1
        return TypeSkolem(name, uid)

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
        """
        match term:
            case ScopedVar(location=location, index=index, debug_name=debug_name):
                # Look up variable type in context
                try:
                    var_type = ctx.lookup_term_type(index)
                    # Apply current substitution
                    var_type = self._apply_subst(var_type)
                    # INST1: instantiate sigma -> rho in synthesis mode
                    # This is the VAR rule from Putting2007
                    var_type = self._instantiate(var_type)
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
                    # Not a constructor - must be a global term
                    # Look up in globals
                    if name in ctx.globals:
                        global_type = ctx.globals[name]
                        global_type = self._apply_subst(global_type)
                        global_type = self._instantiate(global_type)
                        global_type = self._apply_subst(global_type)
                        # Global terms are represented as Global in core
                        core_term = core.Global(location, name)
                        return (core_term, global_type)
                    else:
                        raise TypeError(
                            f"Undefined global variable: {name}",
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
                        # Check argument against parameter type (use check_sigma for polymorphic args)
                        core_arg = self.check_sigma(arg, param_type, ctx)
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
                # Special case: if func is a GlobalVar, don't instantiate - keep the forall
                match func:
                    case GlobalVar(name=name):
                        # Look up global without instantiating - we need the forall for type app
                        if name in ctx.globals:
                            func_type = ctx.globals[name]
                            func_type = self._apply_subst(func_type)
                            core_func = core.Global(location, name)
                        else:
                            raise TypeError(
                                f"Undefined global variable: {name}",
                                location,
                                term,
                            )
                    case _:
                        core_func, func_type = self.infer(func, ctx)
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
                    # GEN1: Infer and generalise value type
                    core_value, value_type = self.infer_sigma(value, new_ctx)

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
                return (core_term, result_type)

            case SurfaceCase(location=location, scrutinee=scrutinee, branches=branches):
                # Pattern matching: infer scrutinee type, check branches
                core_scrut, scrut_type = self.infer(scrutinee, ctx)
                scrut_type = self._apply_subst(scrut_type)

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

                # Infer condition (for completeness)
                core_cond, _ = self.infer(cond, ctx)

                # Build if as a case expression
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
                if not elements:
                    raise TypeError("Empty tuples not supported", location, term)

                # Infer all elements
                core_elems = []
                elem_types = []

                for elem in elements:
                    core_elem, elem_type = self.infer(elem, ctx)
                    core_elems.append(core_elem)
                    elem_types.append(elem_type)

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
                core_left, left_type = self.infer(left, ctx)
                core_right, right_type = self.infer(right, ctx)

                # Primitive operations typically require same-type operands
                left_type = self._apply_subst(left_type)
                right_type = self._apply_subst(right_type)
                self._unify(left_type, right_type, location)

                result_type = self._apply_subst(left_type)

                # Create primitive operation application
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
                        # Lambda against forall: skolemize and check (GEN2)
                        return self.check_sigma(term, forall_type, ctx)

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

    def _skolemise(self, ty: Type) -> tuple[list[TypeSkolem], Type]:
        """Weak prenex conversion: pr(σ) = ∀ā.ρ.

        From Putting2007 paper Section 4.5:
        - PRPOLY: pr(∀ā.σ) = ∀āb̄.ρ where pr(σ) = ∀b̄.ρ
        - PRFUN:  pr(σ₁→σ₂) = ∀ā.(σ₁→ρ₂) where pr(σ₂) = ∀ā.ρ₂, ā ∉ fv(σ₁)
        - PRMONO: pr(τ) = τ

        Returns skolem constants and the rho body.

        Args:
            ty: The type to skolemize

        Returns:
            Tuple of (skolem constants, rho type)
        """
        skolems: list[TypeSkolem] = []
        current = ty

        while True:
            match current:
                case TypeForall(var, body):
                    # Create rigid skolem constant for this bound variable
                    sk = self._fresh_skolem(var)
                    skolems.append(sk)
                    # Substitute skolem for bound variable
                    current = self._subst_type_var(body, var, sk)

                case TypeArrow(arg, ret, doc):
                    # Check if return type has foralls that can be hoisted
                    match ret:
                        case TypeForall(ret_var, ret_body):
                            # PRFUN: hoist foralls from return type
                            # pr(σ₁→∀ā.σ₂) = ∀ā.(σ₁→σ₂) if ā ∉ fv(σ₁)
                            sk = self._fresh_skolem(ret_var)
                            skolems.append(sk)
                            new_ret = self._subst_type_var(ret_body, ret_var, sk)
                            current = TypeArrow(arg, new_ret, doc)
                            # Continue processing in case there are more foralls
                            continue
                        case _:
                            break
                case _:
                    break

        return skolems, current

    def infer_sigma(self, term, ctx: TypeContext) -> tuple[core.Term, Type]:
        """Infer a term's type and generalize over free metas (GEN1).

        Paper: inferSigma (putting-2007-implementation.hs L520-531)
        """
        core_term, rho = self.infer(term, ctx)
        rho = self._apply_subst(rho)

        # Collect metas in the environment (must NOT generalise these)
        env_metas: set[int] = set()
        for t in ctx.term_types:
            env_metas |= self._collect_metas(t)
        for t in ctx.globals.values():
            env_metas |= self._collect_metas(t)

        # Collect metas in the result type
        res_metas = self._collect_metas(rho)

        # Generalisable = in result but not in environment
        forall_metas = res_metas - env_metas

        if not forall_metas:
            return (core_term, rho)

        # Quantify: bind each generalisable meta to a fresh bound variable
        binder_names = _fresh_binder_names(len(forall_metas), rho)
        meta_to_var: dict[int, str] = {}
        for mid, name in zip(sorted(forall_metas), binder_names):
            meta_to_var[mid] = name
            # Extend the substitution so the meta resolves to the bound var
            self.subst = self.subst.extend(TMeta(mid), TypeVar(name))

        # Apply substitution to get the type with TypeVars instead of TMetas
        generalised_body = self._apply_subst(rho)

        # Wrap in foralls (outermost first)
        result_type = generalised_body
        for name in reversed(binder_names):
            result_type = TypeForall(name, result_type)

        return (core_term, result_type)

    def _collect_metas(self, ty: Type) -> set[int]:
        """Collect all TMeta ids that appear (after applying subst)."""
        ty = self._apply_subst(ty)
        match ty:
            case TMeta(id=mid):
                return {mid}
            case TypeArrow(arg, ret, _):
                return self._collect_metas(arg) | self._collect_metas(ret)
            case TypeForall(_, body):
                return self._collect_metas(body)
            case TypeConstructor(_, args):
                result: set[int] = set()
                for a in args:
                    result |= self._collect_metas(a)
                return result
            case _:
                return set()

    def check_sigma(self, term, sigma: Type, ctx: TypeContext) -> core.Term:
        """GEN2: Check term against a polymorphic type by skolemising.

        Paper: checkSigma (putting-2007-implementation.hs L535-542)
        """
        skol_tvs, rho = self._skolemise(sigma)
        core_term = self.check(term, rho, ctx)

        # Skolem escape check
        if skol_tvs:
            env_skolems: set[TypeSkolem] = set()
            for t in ctx.term_types:
                env_skolems |= self._free_skolems(t)
            sigma_skolems = self._free_skolems(self._apply_subst(sigma))
            escaped = env_skolems | sigma_skolems
            bad = [sk for sk in skol_tvs if sk in escaped]
            if bad:
                raise TypeMismatchError(
                    expected=sigma,
                    actual="<term>",
                    location=getattr(term, "location", None),
                    term=term,
                    context="type not polymorphic enough",
                )

        return core_term

    def _free_skolems(self, ty: Type) -> set[TypeSkolem]:
        """Collect all TypeSkolem values that appear in ty."""
        ty = self._apply_subst(ty)
        match ty:
            case TypeSkolem() as sk:
                return {sk}
            case TypeArrow(arg, ret, _):
                return self._free_skolems(arg) | self._free_skolems(ret)
            case TypeForall(_, body):
                return self._free_skolems(body)
            case TypeConstructor(_, args):
                result: set[TypeSkolem] = set()
                for a in args:
                    result |= self._free_skolems(a)
                return result
            case _:
                return set()

    def typecheck(
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
        """Top-level type checking entry point.

        Like Haskell's 'typecheck' - infers the type and generalizes
        over free meta variables (GEN1).

        Returns generalized sigma types suitable for top-level declarations.
        """
        return self.infer_sigma(term, ctx)


# Import Location here to avoid circular imports
from systemf.utils.location import Location
