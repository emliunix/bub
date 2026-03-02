"""Scope checker for System F surface language.

Transforms Surface AST (with names) to Scoped AST (with de Bruijn indices).
This is Phase 1 of the elaboration pipeline.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from systemf.surface.scoped.context import ScopeContext
from systemf.surface.scoped.errors import UndefinedVariableError

if TYPE_CHECKING:
    from systemf.surface.types import (
        SurfaceAbs,
        SurfaceAnn,
        SurfaceApp,
        SurfaceCase,
        SurfaceConstructor,
        SurfaceDeclaration,
        SurfaceIf,
        SurfaceIntLit,
        SurfaceLet,
        SurfaceOp,
        SurfaceStringLit,
        SurfaceTerm,
        SurfaceTermDeclaration,
        SurfaceToolCall,
        SurfaceTuple,
        SurfaceTypeAbs,
        SurfaceTypeApp,
        SurfaceVar,
    )


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
        # Import here to avoid circular imports
        from systemf.surface.types import (
            ScopedAbs,
            ScopedVar,
            SurfaceAbs,
            SurfaceAnn,
            SurfaceApp,
            SurfaceCase,
            SurfaceConstructor,
            SurfaceIf,
            SurfaceIntLit,
            SurfaceLet,
            SurfaceOp,
            SurfaceStringLit,
            SurfaceToolCall,
            SurfaceTuple,
            SurfaceTypeAbs,
            SurfaceTypeApp,
            SurfaceVar,
        )

        match term:
            case SurfaceVar(name, location):
                # Convert name-based variable to index-based
                try:
                    index = ctx.lookup_term(name)
                    return ScopedVar(index, name, location)
                except NameError:
                    # Variable not found - report with available suggestions
                    available = self._suggest_similar_names(name, ctx)
                    raise UndefinedVariableError(
                        name=name,
                        location=location,
                        available=available,
                        term=term,
                    )

            case SurfaceAbs(var, var_type, body, location, _):
                # Extend context with parameter and check body
                new_ctx = ctx.extend_term(var)
                scoped_body = self.check_term(body, new_ctx)
                return ScopedAbs(var, var_type, scoped_body, location)

            case SurfaceApp(func, arg, location):
                # Recursively check function and argument
                scoped_func = self.check_term(func, ctx)
                scoped_arg = self.check_term(arg, ctx)
                return SurfaceApp(scoped_func, scoped_arg, location)

            case SurfaceTypeAbs(var, body, location):
                # Extend type context and check body
                new_ctx = ctx.extend_type(var)
                scoped_body = self.check_term(body, new_ctx)
                return SurfaceTypeAbs(var, scoped_body, location)

            case SurfaceTypeApp(func, type_arg, location):
                # Check function term, type args are handled separately
                scoped_func = self.check_term(func, ctx)
                return SurfaceTypeApp(scoped_func, type_arg, location)

            case SurfaceLet(bindings, body, location):
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
                return SurfaceLet(scoped_bindings, scoped_body, location)

            case SurfaceAnn(term_inner, type_, location):
                # Check inner term, preserve annotation
                scoped_term = self.check_term(term_inner, ctx)
                return SurfaceAnn(scoped_term, type_, location)

            case SurfaceIf(cond, then_branch, else_branch, location):
                # Check all branches
                scoped_cond = self.check_term(cond, ctx)
                scoped_then = self.check_term(then_branch, ctx)
                scoped_else = self.check_term(else_branch, ctx)
                return SurfaceIf(scoped_cond, scoped_then, scoped_else, location)

            case SurfaceCase(scrutinee, branches, location):
                # Check scrutinee and each branch
                from systemf.surface.types import SurfaceBranch

                scoped_scrutinee = self.check_term(scrutinee, ctx)
                scoped_branches = []
                for branch in branches:
                    # Pattern bindings extend context for branch body
                    branch_ctx = ctx
                    for var_name in branch.pattern.vars:
                        branch_ctx = branch_ctx.extend_term(var_name)
                    scoped_body = self.check_term(branch.body, branch_ctx)
                    scoped_branches.append(
                        SurfaceBranch(branch.pattern, scoped_body, branch.location)
                    )
                return SurfaceCase(
                    scrutinee=scoped_scrutinee, branches=scoped_branches, location=location
                )

            case SurfaceConstructor(name, args, location):
                # Recursively check constructor arguments
                scoped_args = [self.check_term(arg, ctx) for arg in args]
                return SurfaceConstructor(name, scoped_args, location)

            case SurfaceTuple(elements, location):
                # Recursively check tuple elements
                scoped_elements = [self.check_term(elem, ctx) for elem in elements]
                return SurfaceTuple(scoped_elements, location)

            case SurfaceOp(left, op, right, location):
                # Check both operands
                scoped_left = self.check_term(left, ctx)
                scoped_right = self.check_term(right, ctx)
                return SurfaceOp(scoped_left, op, scoped_right, location)

            case SurfaceToolCall(tool_name, args, location):
                # Recursively check tool call arguments
                scoped_args = [self.check_term(arg, ctx) for arg in args]
                return SurfaceToolCall(tool_name, scoped_args, location)

            case SurfaceIntLit(_, _) | SurfaceStringLit(_, _):
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
            case SurfaceTermDeclaration(name, type_annotation, body, location, docstring, pragma):
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

            case (
                SurfaceDataDeclaration(_, _, _, _, _, _)
                | SurfacePrimTypeDecl(_, _, _, _)
                | SurfacePrimOpDecl(_, _, _, _, _)
            ):
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
