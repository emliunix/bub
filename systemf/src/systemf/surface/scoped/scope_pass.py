"""Scope check pass - Phase 1 of the elaboration pipeline.

Transforms Surface AST (name-based) to Scoped AST (de Bruijn indices in term bodies).
Toplevel declarations remain name-based, only term bodies get de Bruijn indices.
"""

from __future__ import annotations

from systemf.surface.scoped.context import ScopeContext
from systemf.surface.scoped.errors import ScopeError, UndefinedVariableError
from systemf.surface.result import Result, Ok, Err
from systemf.surface.types import (
    GlobalVar,
    ScopedAbs,
    ScopedVar,
    SurfaceAbs,
    SurfaceAnn,
    SurfaceApp,
    SurfaceBranch,
    SurfaceCase,
    SurfaceConstructor,
    SurfaceDeclaration,
    SurfaceDeclarationRepr,
    SurfaceIf,
    SurfaceLet,
    SurfaceLit,
    SurfaceOp,
    SurfacePattern,
    SurfacePatternBase,
    SurfacePatternCons,
    SurfacePatternTuple,
    SurfaceLitPattern,
    SurfaceTerm,
    SurfaceTermDeclaration,
    SurfaceToolCall,
    SurfaceTuple,
    SurfaceTypeAbs,
    SurfaceTypeApp,
    SurfaceVar,
    SurfaceVarPattern,
    ValBind,
)


def _collect_pattern_vars(
    pattern: SurfacePatternBase,
) -> list[str]:
    """Collect variable names bound at the current pattern level.
    
    With flat pattern structure:
    - SurfacePattern([VarPat(x)]) -> single variable pattern, returns [x]
    - SurfacePattern([VarPat(Con), VarPat(x), ...]) -> constructor, collects from args
    - SurfaceVarPattern(name) -> variable, returns [name]
    """
    match pattern:
        case SurfacePattern(patterns=patterns):
            if len(patterns) == 1 and isinstance(patterns[0], SurfaceVarPattern):
                # Single item: variable pattern
                return [patterns[0].name]
            else:
                # Multiple items: constructor pattern, collect from args (skip constructor)
                result = []
                for pat in patterns[1:]:  # Skip constructor at patterns[0]
                    result.extend(_collect_pattern_vars(pat))
                return result
        case SurfaceVarPattern(name=name):
            return [name]
        case SurfacePatternTuple(elements=elements):
            result = []
            for elem in elements:
                result.extend(_collect_pattern_vars(elem))
            return result
        case SurfacePatternCons(head=head, tail=tail):
            result = []
            result.extend(_collect_pattern_vars(head))
            result.extend(_collect_pattern_vars(tail))
            return result
        case SurfaceLitPattern():
            return []
        case _:
            return []


def _suggest_similar_names(name: str, ctx: ScopeContext) -> list[str]:
    """Suggest similar names for error messages."""
    all_names = set(ctx.term_names) | ctx.globals
    suggestions = []

    for n in all_names:
        if name in n or n in name:
            suggestions.append(n)

    return suggestions[:5]


def _check_term(term: SurfaceTerm, ctx: ScopeContext) -> Result[SurfaceTerm, ScopeError]:
    """Transform a surface term to a scoped term.

        Recursively processes the term, converting name-based variable references
    to index-based references using the provided scope context.

    Returns Ok(scoped_term) on success, Err(ScopeError) on undefined variable.
    """
    match term:
        case SurfaceVar(location=location, name=name):
            index = ctx.lookup_term(name)
            if index is not None:
                return Ok(ScopedVar(index=index, debug_name=name, location=location))
            if ctx.is_global(name):
                return Ok(GlobalVar(name=name, location=location))

            available = _suggest_similar_names(name, ctx)
            return Err(
                UndefinedVariableError(
                    name=name,
                    location=location,
                    available=available,
                    term=term,
                )
            )

        case SurfaceAbs(location=location, params=params, body=body):
            if not params:
                # Empty params - just check the body
                result = _check_term(body, ctx)
                return result.map(lambda b: SurfaceAbs(params=[], body=b, location=location))

            # Process params sequentially, extending context
            new_ctx = ctx
            scoped_params = []

            for var_name, var_type in params:
                new_ctx = new_ctx.extend_term(var_name)
                scoped_params.append((var_name, var_type))

            # Check body with extended context
            body_result = _check_term(body, new_ctx)

            match body_result:
                case Ok(scoped_body):
                    # Create single ScopedAbs for each param (nested)
                    result = scoped_body
                    for var_name, var_type in reversed(scoped_params):
                        result = ScopedAbs(
                            var_name=var_name,
                            var_type=var_type,
                            body=result,
                            location=location,
                        )
                    return Ok(result)
                case Err(error):
                    return Err(error)

        case SurfaceApp(location=location, func=func, arg=arg):
            func_result = _check_term(func, ctx)
            match func_result:
                case Err(error):
                    return Err(error)
                case Ok(scoped_func):
                    arg_result = _check_term(arg, ctx)
                    match arg_result:
                        case Err(error):
                            return Err(error)
                        case Ok(scoped_arg):
                            return Ok(
                                SurfaceApp(func=scoped_func, arg=scoped_arg, location=location)
                            )

        case SurfaceTypeAbs(location=location, vars=vars, body=body):
            if not vars:
                result = _check_term(body, ctx)
                return result.map(lambda b: SurfaceTypeAbs(vars=[], body=b, location=location))

            new_ctx = ctx
            for var in vars:
                new_ctx = new_ctx.extend_type(var)

            result = _check_term(body, new_ctx)
            match result:
                case Ok(scoped_body):
                    return Ok(SurfaceTypeAbs(vars=vars, body=scoped_body, location=location))
                case Err(error):
                    return Err(error)

        case SurfaceTypeApp(location=location, func=func, type_arg=type_arg):
            result = _check_term(func, ctx)
            match result:
                case Ok(scoped_func):
                    return Ok(
                        SurfaceTypeApp(func=scoped_func, type_arg=type_arg, location=location)
                    )
                case Err(error):
                    return Err(error)

        case SurfaceLet(location=location, bindings=bindings, body=body):
            new_ctx = ctx
            scoped_bindings = []

            for b in bindings:
                value_result = _check_term(b.value, new_ctx)
                match value_result:
                    case Err(error):
                        return Err(error)
                    case Ok(scoped_value):
                        scoped_bindings.append(ValBind(
                            name=b.name,
                            type_ann=b.type_ann,
                            value=scoped_value,
                            location=b.location
                        ))
                        new_ctx = new_ctx.extend_term(b.name)

            body_result = _check_term(body, new_ctx)
            match body_result:
                case Ok(scoped_body):
                    return Ok(
                        SurfaceLet(bindings=scoped_bindings, body=scoped_body, location=location)
                    )
                case Err(error):
                    return Err(error)

        case SurfaceAnn(location=location, term=inner_term, type=type_):
            result = _check_term(inner_term, ctx)
            match result:
                case Ok(scoped_term):
                    return Ok(SurfaceAnn(term=scoped_term, type=type_, location=location))
                case Err(error):
                    return Err(error)

        case SurfaceIf(
            location=location, cond=cond, then_branch=then_branch, else_branch=else_branch
        ):
            cond_result = _check_term(cond, ctx)
            match cond_result:
                case Err(error):
                    return Err(error)
                case Ok(scoped_cond):
                    then_result = _check_term(then_branch, ctx)
                    match then_result:
                        case Err(error):
                            return Err(error)
                        case Ok(scoped_then):
                            else_result = _check_term(else_branch, ctx)
                            match else_result:
                                case Err(error):
                                    return Err(error)
                                case Ok(scoped_else):
                                    return Ok(
                                        SurfaceIf(
                                            cond=scoped_cond,
                                            then_branch=scoped_then,
                                            else_branch=scoped_else,
                                            location=location,
                                        )
                                    )

        case SurfaceCase(location=location, scrutinee=scrutinee, branches=branches):
            scrut_result = _check_term(scrutinee, ctx)
            match scrut_result:
                case Err(error):
                    return Err(error)
                case Ok(scoped_scrutinee):
                    scoped_branches = []
                    for branch in branches:
                        branch_ctx = ctx
                        if branch.pattern is not None:
                            pattern_vars = _collect_pattern_vars(branch.pattern)
                            for var_name in pattern_vars:
                                branch_ctx = branch_ctx.extend_term(var_name)

                        body_result = _check_term(branch.body, branch_ctx)
                        match body_result:
                            case Err(error):
                                return Err(error)
                            case Ok(scoped_body):
                                scoped_branches.append(
                                    SurfaceBranch(
                                        pattern=branch.pattern,
                                        body=scoped_body,
                                        location=branch.location,
                                    )
                                )

                    return Ok(
                        SurfaceCase(
                            scrutinee=scoped_scrutinee,
                            branches=scoped_branches,
                            location=location,
                        )
                    )

        case SurfaceConstructor(location=location, name=name, args=args):
            scoped_args = []
            for arg in args:
                arg_result = _check_term(arg, ctx)
                match arg_result:
                    case Err(error):
                        return Err(error)
                    case Ok(scoped_arg):
                        scoped_args.append(scoped_arg)

            return Ok(SurfaceConstructor(name=name, args=scoped_args, location=location))

        case SurfaceTuple(location=location, elements=elements):
            scoped_elements = []
            for elem in elements:
                elem_result = _check_term(elem, ctx)
                match elem_result:
                    case Err(error):
                        return Err(error)
                    case Ok(scoped_elem):
                        scoped_elements.append(scoped_elem)

            return Ok(SurfaceTuple(elements=scoped_elements, location=location))

        case SurfaceOp(location=location, left=left, op=op, right=right):
            left_result = _check_term(left, ctx)
            match left_result:
                case Err(error):
                    return Err(error)
                case Ok(scoped_left):
                    right_result = _check_term(right, ctx)
                    match right_result:
                        case Err(error):
                            return Err(error)
                        case Ok(scoped_right):
                            return Ok(
                                SurfaceOp(
                                    left=scoped_left, op=op, right=scoped_right, location=location
                                )
                            )

        case SurfaceToolCall(location=location, tool_name=tool_name, args=args):
            scoped_args = []
            for arg in args:
                arg_result = _check_term(arg, ctx)
                match arg_result:
                    case Err(error):
                        return Err(error)
                    case Ok(scoped_arg):
                        scoped_args.append(scoped_arg)

            return Ok(SurfaceToolCall(tool_name=tool_name, args=scoped_args, location=location))

        case SurfaceLit():
            return Ok(term)

        case _:
            return Ok(term)


def _check_declaration(
    decl: SurfaceDeclaration, ctx: ScopeContext
) -> Result[SurfaceDeclaration, ScopeError]:
    """Scope-check a single declaration.

        Only term declarations have their bodies scope-checked.
    Other declarations pass through unchanged.
    """
    match decl:
        case SurfaceTermDeclaration(
            name=name,
            type_annotation=type_annotation,
            body=body,
            docstring=docstring,
            pragma=pragma,
            location=location,
        ):
            if body is None:
                return Ok(decl)

            body_result = _check_term(body, ctx)
            match body_result:
                case Ok(scoped_body):
                    return Ok(
                        SurfaceTermDeclaration(
                            name=name,
                            type_annotation=type_annotation,
                            body=scoped_body,
                            docstring=docstring,
                            pragma=pragma,
                            location=location,
                        )
                    )
                case Err(error):
                    return Err(error)

        case _:
            return Ok(decl)


def scope_check_pass(
    decls: list[SurfaceDeclaration], ctx: ScopeContext | None = None
) -> Result[list[SurfaceDeclaration], ScopeError]:
    """Scope-check a list of declarations, enabling mutual recursion.

        Phase 1 of the elaboration pipeline. Transforms Surface AST to Scoped AST
        by resolving names to de Bruijn indices in term bodies. Toplevel declarations
    remain name-based - only term bodies get de Bruijn indices.

        This pass:
        1. Collects all global names from term declarations
        2. Collects all constructor names from data declarations
        3. Creates a context with all globals and constructors (enables mutual recursion)
        4. Scope-checks each declaration's body

        Args:
            decls: List of surface declarations to scope-check
            ctx: Optional initial scope context (creates empty context if None)

        Returns:
            Ok(list[SurfaceDeclaration]): Declarations with scoped bodies on success
            Err(ScopeError): First scope error encountered

    Example:
            >>> from systemf.surface.types import SurfaceVar, SurfaceAbs, SurfaceTermDeclaration
            >>> from systemf.utils.location import Location
            >>> loc = Location("test", 1, 1)
            >>> # x = \y -> y
            >>> body = SurfaceAbs(params=[("y", None)], body=SurfaceVar(name="y", location=loc), location=loc)
            >>> decl = SurfaceTermDeclaration(name="x", type_annotation=None, body=body, location=loc)
            >>> result = scope_check_pass([decl])
            >>> print(result)
            Ok([x : None = \y -> #0(y)])
    """
    if ctx is None:
        ctx = ScopeContext()

    # Collect all global names from term declarations
    global_names = set()
    for decl in decls:
        if isinstance(decl, SurfaceTermDeclaration):
            global_names.add(decl.name)

    # Collect all constructor names from data declarations
    from systemf.surface.types import SurfaceDataDeclaration

    constructor_names = set()
    for decl in decls:
        if isinstance(decl, SurfaceDataDeclaration):
            for con in decl.constructors:
                constructor_names.add(con.name)

    # Collect all primitive operation names
    from systemf.surface.types import SurfacePrimOpDecl

    primop_names = set()
    for decl in decls:
        if isinstance(decl, SurfacePrimOpDecl):
            primop_names.add(decl.name)

    # Extend context with all globals, constructors, and primitive ops
    for name in global_names:
        ctx = ctx.add_global(name)
    for name in constructor_names:
        ctx = ctx.add_global(name)
    for name in primop_names:
        ctx = ctx.add_global(name)
    for name in constructor_names:
        ctx = ctx.add_global(name)

    # Scope-check each declaration
    scoped_decls: list[SurfaceDeclaration] = []
    for decl in decls:
        decl_result = _check_declaration(decl, ctx)
        match decl_result:
            case Ok(scoped_decl):
                scoped_decls.append(scoped_decl)
            case Err(error):
                return Err(error)

    return Ok(scoped_decls)
