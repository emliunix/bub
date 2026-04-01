"""Scope checker for System F surface language.

Transforms Surface AST (with names) to Scoped AST (with de Bruijn indices).
This is Phase 1 of the elaboration pipeline.
"""

from __future__ import annotations

from systemf.surface.scoped.context import ScopeContext
from systemf.surface.scoped.errors import UndefinedVariableError
from systemf.surface.types import (
    GlobalVar,
    SurfaceAbs,
    SurfaceAnn,
    SurfaceApp,
    SurfaceCase,
    SurfaceConstructor,
    SurfaceDeclaration,
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


class ScopeChecker:
    """Transforms Surface AST to Scoped AST by resolving names to de Bruijn indices.

    The scope checker traverses the AST and:
    1. Converts SurfaceVar -> ScopedVar (name -> de Bruijn index)
    2. Converts SurfaceAbs -> ScopedAbs (extends context, checks body)
    3. Recursively processes other nodes
    4. Maintains separate contexts for term and type variables

    Example:
        >>> from systemf.surface.types import SurfaceVar, SurfaceAbs
        >>> from systemf.utils.location import Location
        >>> checker = ScopeChecker()
        >>> ctx = ScopeContext()
        >>> loc = Location("test", 1, 1)
        >>> # \\x -> x
        >>> abs_term = SurfaceAbs("x", None, SurfaceVar("x", loc), loc)
        >>> scoped = checker.check_term(abs_term, ctx)
        >>> print(scoped)
        \\x -> #0(x)
    """

    def check_term(self, term: "SurfaceTerm", ctx: ScopeContext) -> "SurfaceTerm":
        """Transform a surface term to a scoped term.

        Recursively processes the term, converting name-based variable references
        to index-based references using the provided scope context.

        Args:
            term: The surface term to scope-check
            ctx: Current scope context with variable bindings

        Returns:
            The scoped term with de Bruijn indices

        Raises:
            UndefinedVariableError: If a variable is not in scope
        """
        from systemf.surface.types import (
            ScopedAbs,
            ScopedVar,
        )

        match term:
            case SurfaceVar(location=location, name=name):
                # Convert name-based variable to index-based
                # Check locals first (shadowing: local > global)
                index = ctx.lookup_term(name)
                if index is not None:
                    return ScopedVar(index=index, debug_name=name, location=location)
                # Not a local - check if it's a global variable
                if ctx.is_global(name):
                    # Global variables keep their name (not DBI)
                    return GlobalVar(name=name, location=location)
                # Variable not found - report with available suggestions
                available = self._suggest_similar_names(name, ctx)
                raise UndefinedVariableError(
                    name=name,
                    location=location,
                    available=available,
                    term=term,
                )

            case SurfaceAbs(location=location, var=var, var_type=var_type, body=body):
                # Extend context with parameter and check body
                new_ctx = ctx.extend_term(var)
                scoped_body = self.check_term(body, new_ctx)
                return ScopedAbs(
                    var_name=var, var_type=var_type, body=scoped_body, location=location
                )

            case SurfaceApp(location=location, func=func, arg=arg):
                # Recursively check function and argument
                scoped_func = self.check_term(func, ctx)
                scoped_arg = self.check_term(arg, ctx)
                return SurfaceApp(func=scoped_func, arg=scoped_arg, location=location)

            case SurfaceTypeAbs(location=location, var=var, body=body):
                # Extend type context and check body
                new_ctx = ctx.extend_type(var)
                scoped_body = self.check_term(body, new_ctx)
                return SurfaceTypeAbs(var=var, body=scoped_body, location=location)

            case SurfaceTypeApp(location=location, func=func, type_arg=type_arg):
                # Check function term, type args are handled separately
                scoped_func = self.check_term(func, ctx)
                return SurfaceTypeApp(func=scoped_func, type_arg=type_arg, location=location)

            case SurfaceLet(location=location, bindings=bindings, body=body):
                # Process bindings sequentially (each can refer to previous)
                new_ctx = ctx
                scoped_bindings = []
                for var_name, var_type, value in bindings:
                    # Check value in current context
                    scoped_value = self.check_term(value, new_ctx)
                    scoped_bindings.append((var_name, var_type, scoped_value))
                    # Extend context for subsequent bindings and body
                    new_ctx = new_ctx.extend_term(var_name)
                # Check body with all bindings in scope
                scoped_body = self.check_term(body, new_ctx)
                return SurfaceLet(bindings=scoped_bindings, body=scoped_body, location=location)

            case SurfaceAnn(location=location, term=term_inner, type=type_):
                # Check inner term, preserve annotation
                scoped_term = self.check_term(term_inner, ctx)
                return SurfaceAnn(term=scoped_term, type=type_, location=location)

            case SurfaceIf(
                location=location, cond=cond, then_branch=then_branch, else_branch=else_branch
            ):
                # Check all branches
                scoped_cond = self.check_term(cond, ctx)
                scoped_then = self.check_term(then_branch, ctx)
                scoped_else = self.check_term(else_branch, ctx)
                return SurfaceIf(
                    cond=scoped_cond,
                    then_branch=scoped_then,
                    else_branch=scoped_else,
                    location=location,
                )

            case SurfaceCase(location=location, scrutinee=scrutinee, branches=branches):
                # Check scrutinee and each branch
                from systemf.surface.types import SurfaceBranch

                scoped_scrutinee = self.check_term(scrutinee, ctx)
                scoped_branches = []
                for branch in branches:
                    # Pattern bindings extend context for branch body
                    branch_ctx = ctx
                    if branch.pattern is not None:
                        pattern_vars = _collect_pattern_vars(branch.pattern)
                        for var_name in pattern_vars:
                            branch_ctx = branch_ctx.extend_term(var_name)
                    scoped_body = self.check_term(branch.body, branch_ctx)
                    scoped_branches.append(
                        SurfaceBranch(
                            pattern=branch.pattern, body=scoped_body, location=branch.location
                        )
                    )
                return SurfaceCase(
                    scrutinee=scoped_scrutinee, branches=scoped_branches, location=location
                )

            case SurfaceConstructor(location=location, name=name, args=args):
                # Recursively check constructor arguments
                scoped_args = [self.check_term(arg, ctx) for arg in args]
                return SurfaceConstructor(name=name, args=scoped_args, location=location)

            case SurfaceTuple(location=location, elements=elements):
                # Recursively check tuple elements
                scoped_elements = [self.check_term(elem, ctx) for elem in elements]
                return SurfaceTuple(elements=scoped_elements, location=location)

            case SurfaceOp(location=location, left=left, op=op, right=right):
                # Check both operands
                scoped_left = self.check_term(left, ctx)
                scoped_right = self.check_term(right, ctx)
                return SurfaceOp(left=scoped_left, op=op, right=scoped_right, location=location)

            case SurfaceToolCall(location=location, tool_name=tool_name, args=args):
                # Recursively check tool call arguments
                scoped_args = [self.check_term(arg, ctx) for arg in args]
                return SurfaceToolCall(tool_name=tool_name, args=scoped_args, location=location)

            case SurfaceLit():
                # Literals don't contain variables, return unchanged
                return term

            case _:
                # Unknown term type - return unchanged (allows extension)
                return term

    def check_declarations(self, decls: list["SurfaceDeclaration"]) -> list["SurfaceDeclaration"]:
        """Scope-check multiple top-level declarations with mutual recursion support.

        This method implements the top-level collection strategy required for mutual
        recursion. It collects all declaration names first, then scope-checks each
        body with all globals in scope.

        Process:
            1. Collect all global names from term declarations
            2. Create a context with all globals
            3. Scope-check each declaration body with the full context

        This enables mutually recursive functions:
            even : Int -> Bool
            even n = if n == 0 then True else odd (n - 1)

            odd : Int -> Bool
            odd n = if n == 0 then False else even (n - 1)

        Args:
            decls: List of surface declarations to scope-check

        Returns:
            List of scoped declarations with de Bruijn indices in all bodies

        Example:
            >>> checker = ScopeChecker()
            >>> # Two mutually recursive functions
            >>> decls = [even_decl, odd_decl]
            >>> scoped_decls = checker.check_declarations(decls)
            >>> # Both can reference each other in their bodies
        """
        from systemf.surface.types import SurfaceTermDeclaration

        # Step 1: Collect all global names from term declarations
        global_names = set()
        for decl in decls:
            if isinstance(decl, SurfaceTermDeclaration):
                global_names.add(decl.name)

        # Step 2: Create context with all globals
        ctx = ScopeContext(globals=global_names)

        # Step 3: Scope-check each declaration with full context
        scoped_decls = []
        for decl in decls:
            scoped_decl = self.check_declaration(decl, ctx)
            scoped_decls.append(scoped_decl)

        return scoped_decls

    def check_declaration(
        self, decl: "SurfaceDeclaration", ctx: ScopeContext
    ) -> "SurfaceDeclaration":
        """Scope-check a single top-level declaration.

        Handles term declarations by scope-checking the body in the provided
        context. Other declaration types pass through unchanged (they don't
        contain term-level variables that need resolution).

        For checking multiple declarations with mutual recursion support,
        use check_declarations() instead.

        Args:
            decl: The surface declaration to scope-check
            ctx: Current scope context with global bindings

        Returns:
            The scoped declaration
        """
        from systemf.surface.types import (
            SurfaceDataDeclaration,
            SurfacePrimOpDecl,
            SurfacePrimTypeDecl,
            SurfaceTermDeclaration,
        )

        match decl:
            case SurfaceTermDeclaration(
                location=location,
                name=name,
                type_annotation=type_annotation,
                body=body,
                docstring=docstring,
                pragma=pragma,
            ):
                # Scope-check the body with current context (globals are already in ctx)
                scoped_body = self.check_term(body, ctx)
                return SurfaceTermDeclaration(
                    name=name,
                    type_annotation=type_annotation,
                    body=scoped_body,
                    location=location,
                    docstring=docstring,
                    pragma=pragma,
                )

            case SurfaceDataDeclaration() | SurfacePrimTypeDecl() | SurfacePrimOpDecl():
                # These don't contain term-level variable references
                return decl

            case _:
                # Unknown declaration type - return unchanged
                return decl

    def _suggest_similar_names(self, name: str, ctx: ScopeContext) -> list[str]:
        """Generate suggestions for similar variable names.

        Looks at all bound names and returns those that are similar
        to the undefined name (for error messages).

        Args:
            name: The undefined variable name
            ctx: Current scope context

        Returns:
            List of similar bound variable names
        """
        all_names = set(ctx.term_names)
        suggestions = []

        # Simple similarity: same first character or substring match
        for bound_name in all_names:
            if bound_name == name:
                continue
            if bound_name.startswith(name[0]) if name else False:
                suggestions.append(bound_name)
            elif name in bound_name or bound_name in name:
                suggestions.append(bound_name)

        return suggestions[:5]  # Limit to 5 suggestions
