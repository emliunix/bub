"""Surface to Core language elaborator.

Converts surface syntax (name-based binding) to core syntax (de Bruijn indices).
"""

from __future__ import annotations

from typing import Optional

from systemf.core import ast as core
from systemf.core.errors import ElaborationError
from systemf.core.module import Module
from systemf.core.types import PrimitiveType, Type as CoreType
from systemf.core.types import TypeArrow, TypeConstructor, TypeForall, TypeVar
from systemf.surface.ast import (
    SurfaceAbs,
    SurfaceAnn,
    SurfaceApp,
    SurfaceBranch,
    SurfaceCase,
    SurfaceConstructor,
    SurfaceDataDeclaration,
    SurfaceDeclaration,
    SurfaceIntLit,
    SurfaceLet,
    SurfaceOp,
    SurfacePattern,
    SurfacePrimOpDecl,
    SurfacePrimTypeDecl,
    SurfaceStringLit,
    SurfaceTerm,
    SurfaceTermDeclaration,
    SurfaceToolCall,
    SurfaceType,
    SurfaceTypeAbs,
    SurfaceTypeApp,
    SurfaceTypeArrow,
    SurfaceTypeConstructor,
    SurfaceTypeForall,
    SurfaceTypeVar,
    SurfaceVar,
)
from systemf.utils.location import Location


class UndefinedVariable(ElaborationError):
    """Variable not found in scope."""

    def __init__(self, name: str, location: Location):
        super().__init__(f"Undefined variable: {name}", location)
        self.name = name


class UndefinedTypeVariable(ElaborationError):
    """Type variable not found in scope."""

    def __init__(self, name: str, location: Location):
        super().__init__(f"Undefined type variable: {name}", location)
        self.name = name


class Elaborator:
    """Elaborates surface syntax to core language.

    Performs scope resolution (names -> de Bruijn indices) and type translation.
    """

    def __init__(self, evaluator=None):
        """Initialize elaborator with empty environments."""
        # Local term environment: name -> de Bruijn index
        # Index 0 is the most recently bound variable (lambda params, etc.)
        self.term_env: dict[str, int] = {}

        # Global term definitions: names of top-level declarations
        # These are tracked separately from local variables
        self.global_terms: set[str] = set()

        # Type environment: set of bound type variable names
        self.type_env: set[str] = set()

        # Constructor types for data constructors
        self.constructor_types: dict[str, CoreType] = {}

        # Data declarations for elaborating constructors
        self.data_decls: dict[str, SurfaceDataDeclaration] = {}

        # Primitive types registry: name -> PrimitiveType
        self.primitive_types: dict[str, PrimitiveType] = {}

        # Global types: name -> CoreType (for primitive operations)
        self.global_types: dict[str, CoreType] = {}

        # Optional evaluator for registering LLM closures
        self.evaluator = evaluator

    # =====================================================================
    # Environment Management
    # =====================================================================

    def _add_term_binding(self, name: str) -> None:
        """Add a term variable binding.

        Shifts existing indices up by 1, and binds the new variable at index 0.
        """
        self.term_env = {k: v + 1 for k, v in self.term_env.items()}
        self.term_env[name] = 0

    def _remove_term_binding(self, name: str) -> None:
        """Remove a term variable binding.

        Shifts remaining indices down by 1.
        """
        if name in self.term_env:
            del self.term_env[name]
            self.term_env = {k: v - 1 for k, v in self.term_env.items()}

    def _add_global_term(self, name: str) -> None:
        """Add a global term definition."""
        self.global_terms.add(name)

    def _lookup_term(self, name: str, location: Location) -> core.Term:
        """Look up a term variable.

        Returns Var for local bindings, Global for top-level definitions,
        or PrimOp for $prim.xxx names.
        """
        if name in self.term_env:
            return core.Var(self.term_env[name])
        if name in self.global_terms:
            return core.Global(name)
        if name.startswith("$prim."):
            op_name = name[6:]  # Strip "$prim."
            return core.PrimOp(op_name)
        raise UndefinedVariable(name, location)

    def _add_type_binding(self, name: str) -> None:
        """Add a type variable binding."""
        self.type_env.add(name)

    def _remove_type_binding(self, name: str) -> None:
        """Remove a type variable binding."""
        self.type_env.discard(name)

    def _lookup_type(self, name: str, location: Location) -> str:
        """Look up a type variable, returning its name."""
        if name not in self.type_env:
            raise UndefinedTypeVariable(name, location)
        return name

    # =====================================================================
    # Declaration Elaboration
    # =====================================================================

    def elaborate(self, decls: list[SurfaceDeclaration]) -> Module:
        """Elaborate surface declarations to a Module.

        Args:
            decls: List of surface declarations

        Returns:
            Module containing elaborated declarations and type information
        """
        declarations: list[core.Declaration] = []
        for decl in decls:
            core_decl = self.elaborate_declaration(decl)
            declarations.append(core_decl)

        return Module(
            name="main",
            declarations=declarations,
            constructor_types=self.constructor_types,
            global_types=self.global_types,
            primitive_types=self.primitive_types,
            docstrings={},
            llm_functions={},  # Extracted after type checking
            errors=[],
            warnings=[],
        )

    def elaborate_declaration(self, decl: SurfaceDeclaration) -> core.Declaration:
        """Elaborate a single declaration."""
        match decl:
            case SurfaceDataDeclaration():
                return self._elaborate_data_decl(decl)
            case SurfaceTermDeclaration():
                return self._elaborate_term_decl(decl)
            case SurfacePrimTypeDecl(name, location):
                return self._elaborate_prim_type_decl(name, location)
            case SurfacePrimOpDecl(name, type_annotation, location):
                return self._elaborate_prim_op_decl(name, type_annotation, location)
            case _:
                raise ElaborationError(f"Unknown declaration type: {type(decl)}")

    def _elaborate_data_decl(self, decl: SurfaceDataDeclaration) -> core.DataDeclaration:
        """Elaborate a data type declaration."""
        # Store for later reference
        self.data_decls[decl.name] = decl

        # Build constructor types
        for con_info in decl.constructors:
            # Constructor type: forall params. arg_types -> T params
            con_type = self._build_constructor_type(decl, con_info.args)
            self.constructor_types[con_info.name] = con_type

        # Convert surface types to core types
        core_constructors = []
        for con_info in decl.constructors:
            # Extend type environment with data type parameters
            for param in decl.params:
                self._add_type_binding(param)

            core_arg_types = [self._elaborate_type(at) for at in con_info.args]
            core_constructors.append((con_info.name, core_arg_types))

            # Remove type bindings
            for param in reversed(decl.params):
                self._remove_type_binding(param)

        return core.DataDeclaration(
            name=decl.name,
            params=decl.params,
            constructors=core_constructors,
        )

    def _build_constructor_type(self, decl: SurfaceDataDeclaration, arg_types: list) -> CoreType:
        """Build the type of a data constructor."""
        # Build result type: T params
        result_type = TypeConstructor(decl.name, [TypeVar(p) for p in decl.params])

        # Build arrow type: arg_types -> T params
        con_type = result_type
        for arg_type in reversed(arg_types):
            con_type = TypeArrow(TypeVar("_"), con_type)  # Simplified

        # Add forall for type parameters
        for param in reversed(decl.params):
            con_type = TypeForall(param, con_type)

        return con_type

    def _elaborate_term_decl(self, decl: SurfaceTermDeclaration) -> core.TermDeclaration:
        """Elaborate a term declaration."""
        # Elaborate type annotation if present
        core_type = None
        if decl.type_annotation:
            core_type = self._elaborate_type(decl.type_annotation)

        # Check for LLM pragma (stored as dict {"LLM": "raw_content"})
        is_llm = decl.pragma is not None and "LLM" in decl.pragma

        if is_llm and isinstance(decl.body, SurfaceAbs):
            # This is an LLM function declaration
            return self._elaborate_llm_term_decl(decl, core_type)

        # Add the declared name to global_terms BEFORE elaborating the body
        # This allows recursive definitions to work by making them Global references
        self._add_global_term(decl.name)

        # Elaborate the body (now recursive calls will find the name)
        core_body = self.elaborate_term(decl.body)

        # Get pragma params for non-LLM declarations (None for regular functions)
        pragma_params = None
        if decl.pragma and "LLM" in decl.pragma:
            pragma_params = decl.pragma["LLM"].strip() or None

        return core.TermDeclaration(
            name=decl.name,
            type_annotation=core_type,
            body=core_body,
            pragma=pragma_params,
        )

    def _elaborate_llm_term_decl(
        self, decl: SurfaceTermDeclaration, core_type: Optional[CoreType]
    ) -> core.TermDeclaration:
        """Elaborate an LLM function declaration.

        Extracts metadata from the declaration and creates an LLM closure.
        The body is replaced with a PrimOp that calls the LLM.
        """
        # Extract function docstring
        func_docstring = decl.docstring

        # Extract parameter info from lambda
        lambda_body = decl.body
        assert isinstance(lambda_body, SurfaceAbs)

        arg_names = [lambda_body.var]
        arg_docstrings: list[str | None] = (
            list(lambda_body.param_docstrings) if lambda_body.param_docstrings else [None]
        )  # type: ignore[assignment]

        # Extract types from type annotation
        arg_types: list[CoreType] = []
        if core_type:
            # The type should be an arrow type: arg_type -> return_type
            # We extract the argument type
            match core_type:
                case TypeArrow(arg_t, _):
                    arg_types = [arg_t]
                case _:
                    arg_types = []
        else:
            arg_types = []

        # Ensure arg_types has the same length as arg_names
        while len(arg_types) < len(arg_names):
            arg_types.append(TypeVar("_"))

        # Get raw pragma parameters (opaque to elaborator)
        pragma_params = None
        if decl.pragma and "LLM" in decl.pragma:
            pragma_params = decl.pragma["LLM"].strip() or None

        # Extract parameter docstrings from lambda
        param_docstrings: list[str] = []
        if lambda_body.param_docstrings:
            param_docstrings = [str(ds) if ds else "" for ds in lambda_body.param_docstrings]

        # Elaborate to PrimOp("$llm.{name}")
        # Add to global_terms
        self._add_global_term(decl.name)

        # Register type in global_types for type checking
        if core_type is not None:
            self.global_types[decl.name] = core_type

        # Pass metadata fields to Core - LLMMetadata will be extracted after type checking
        return core.TermDeclaration(
            name=decl.name,
            type_annotation=core_type,
            body=core.PrimOp(f"llm.{decl.name}"),
            pragma=pragma_params,
            docstring=func_docstring,
            param_docstrings=param_docstrings if param_docstrings else None,
        )

    def _elaborate_prim_type_decl(self, name: str, location: Location) -> core.DataDeclaration:
        """Elaborate a primitive type declaration.

        Registers the primitive type in the primitive_types registry
        and returns a DataDeclaration placeholder.
        """
        prim_type = PrimitiveType(name)
        self.primitive_types[name] = prim_type
        # Return a DataDeclaration as placeholder (no constructors for primitive types)
        return core.DataDeclaration(
            name=name,
            params=[],
            constructors=[],
        )

    def _elaborate_prim_op_decl(
        self, name: str, type_annotation: "SurfaceType", location: Location
    ) -> core.TermDeclaration:
        """Elaborate a primitive operation declaration.

        Registers the operation with its type signature in global_types
        as $prim.name and returns a TermDeclaration placeholder.
        """
        core_type = self._elaborate_type(type_annotation)
        full_name = f"$prim.{name}"
        self.global_types[full_name] = core_type
        # Return a TermDeclaration as placeholder with a PrimOp body
        return core.TermDeclaration(
            name=name,
            type_annotation=core_type,
            body=core.PrimOp(name),
        )

    # =====================================================================
    # Term Elaboration
    # =====================================================================

    def elaborate_term(self, term: SurfaceTerm) -> core.Term:
        """Elaborate a surface term to a core term.

        Args:
            term: Surface term to elaborate

        Returns:
            Core term with de Bruijn indices
        """
        match term:
            case SurfaceVar(name, location):
                return self._lookup_term(name, location)

            case SurfaceAbs(var, var_type, body, location):
                # Elaborate the type annotation if present
                core_var_type = None
                if var_type:
                    core_var_type = self._elaborate_type(var_type)
                else:
                    # Default to a placeholder type (should be inferred)
                    core_var_type = TypeVar("_")

                # Extend environment and elaborate body
                self._add_term_binding(var)
                core_body = self.elaborate_term(body)
                self._remove_term_binding(var)

                return core.Abs(core_var_type, core_body)

            case SurfaceApp(func, arg, location):
                core_func = self.elaborate_term(func)
                core_arg = self.elaborate_term(arg)
                # If func is a constructor, convert App to Constructor with args
                if isinstance(core_func, core.Constructor):
                    return core.Constructor(core_func.name, core_func.args + [core_arg])
                return core.App(core_func, core_arg)

            case SurfaceTypeAbs(var, body, location):
                # Extend type environment and elaborate body
                self._add_type_binding(var)
                core_body = self.elaborate_term(body)
                self._remove_type_binding(var)

                return core.TAbs(var, core_body)

            case SurfaceTypeApp(func, type_arg, location):
                core_func = self.elaborate_term(func)
                core_type_arg = self._elaborate_type(type_arg)
                # If func is a constructor, don't create TApp - constructors don't need
                # type applications at runtime. The type checker will handle the type.
                if isinstance(core_func, core.Constructor):
                    return core_func
                return core.TApp(core_func, core_type_arg)

            case SurfaceLet(name, value, body, location):
                core_value = self.elaborate_term(value)
                self._add_term_binding(name)
                core_body = self.elaborate_term(body)
                # Don't remove - let binding stays in scope
                return core.Let(name, core_value, core_body)

            case SurfaceAnn(term_inner, type_ann, location):
                # Elaborate the term (annotation is for type checking)
                return self.elaborate_term(term_inner)

            case SurfaceConstructor(name, args, location):
                core_args = [self.elaborate_term(arg) for arg in args]
                return core.Constructor(name, core_args)

            case SurfaceCase(scrutinee, branches, location):
                core_scrut = self.elaborate_term(scrutinee)
                core_branches = []

                for branch in branches:
                    # Extend environment with pattern variables
                    for var in branch.pattern.vars:
                        self._add_term_binding(var)

                    core_body = self.elaborate_term(branch.body)

                    # Remove pattern variables
                    for var in reversed(branch.pattern.vars):
                        self._remove_term_binding(var)

                    core_branches.append(
                        core.Branch(
                            pattern=core.Pattern(
                                branch.pattern.constructor,
                                branch.pattern.vars,
                            ),
                            body=core_body,
                        )
                    )

                return core.Case(core_scrut, core_branches)

            case SurfaceToolCall(tool_name, args, location):
                # Elaborate tool call arguments
                core_args = [self.elaborate_term(arg) for arg in args]
                return core.ToolCall(tool_name, core_args)

            case SurfaceIntLit(value, location):
                # Convert integer literal to core IntLit
                return core.IntLit(value)

            case SurfaceStringLit(value, location):
                # Convert string literal to core StringLit
                return core.StringLit(value)

            case SurfaceOp(left, op, right, location):
                # Desugar operator to primitive application
                from systemf.surface.desugar import desugar

                desugared = desugar(term)
                return self.elaborate_term(desugared)

            case _:
                raise ElaborationError(f"Unknown term type: {type(term)}")

    # =====================================================================
    # Type Elaboration
    # =====================================================================

    def _elaborate_type(self, ty: "SurfaceType") -> CoreType:
        """Elaborate a surface type to a core type."""
        match ty:
            case SurfaceTypeVar(name, location):
                # Type variables are by name in both surface and core
                return TypeVar(name)

            case SurfaceTypeArrow(arg, ret, location):
                core_arg = self._elaborate_type(arg)
                core_ret = self._elaborate_type(ret)
                return TypeArrow(core_arg, core_ret)

            case SurfaceTypeForall(var, body, location):
                self._add_type_binding(var)
                core_body = self._elaborate_type(body)
                self._remove_type_binding(var)
                return TypeForall(var, core_body)

            case SurfaceTypeConstructor(name, args, location):
                # Check if this is a primitive type (registered via prim_type)
                if name in self.primitive_types and not args:
                    return self.primitive_types[name]
                core_args = [self._elaborate_type(arg) for arg in args]
                return TypeConstructor(name, core_args)

            case _:
                raise ElaborationError(f"Unknown type: {type(ty)}")

    # =====================================================================
    # Convenience Methods
    # =====================================================================

    def elaborate_term_with_context(
        self, term: SurfaceTerm, term_vars: list[str], type_vars: Optional[list[str]] = None
    ) -> core.Term:
        """Elaborate a term with a pre-populated context.

        Args:
            term: Surface term to elaborate
            term_vars: List of bound term variable names (in order, 0 = outermost)
            type_vars: List of bound type variable names

        Returns:
            Core term with proper de Bruijn indices
        """
        # Set up environment
        self.term_env = {name: i for i, name in enumerate(reversed(term_vars))}
        self.type_env = set(type_vars) if type_vars else set()

        return self.elaborate_term(term)


def elaborate(
    decls: list[SurfaceDeclaration],
) -> Module:
    """Elaborate surface declarations and return a Module.

    Args:
        decls: List of surface declarations

    Returns:
        Module containing elaborated declarations and type information
    """
    elab = Elaborator()
    return elab.elaborate(decls)


def elaborate_term(term: SurfaceTerm, context: Optional[list[str]] = None) -> core.Term:
    """Elaborate a single surface term.

    Args:
        term: Surface term to elaborate
        context: List of bound variable names (outermost first)

    Returns:
        Core term

    Example:
        >>> from systemf.surface.parser import parse_term
        >>> term = parse_term("\\x -> x")
        >>> core_term = elaborate_term(term)
        >>> print(core_term)
        λ(_:_).x0
    """
    elab = Elaborator()
    if context:
        # Context is outermost first, but de Bruijn indices need innermost = 0
        # So we reverse the list
        elab.term_env = {name: i for i, name in enumerate(reversed(context))}
    return elab.elaborate_term(term)
