"""Bidirectional type checker for System F with data types."""

import itertools

from systemf.core.ast import (
    Abs,
    App,
    Branch,
    Case,
    Constructor,
    Constructor as AstConstructor,
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
    Var,
)
from systemf.core.context import Context
from systemf.core.errors import (
    TypeMismatch,
    UndefinedConstructor,
    UndefinedVariable,
)
from systemf.core.types import Type, TypeArrow, TypeConstructor, TypeForall, TypeVar
from systemf.core.unify import Substitution, unify


class TypeChecker:
    """Bidirectional type checker for System F with data types."""

    def __init__(
        self,
        datatype_constructors: dict[str, Type] | None = None,
        global_types: dict[str, Type] | None = None,
        primitive_types: dict[str, Type] | None = None,
    ):
        """Initialize with data type constructor signatures.

        Args:
            datatype_constructors: Maps constructor names to their polymorphic types.
                Example: {"Nil": ∀a. List a, "Cons": ∀a. a → List a → List a}
            global_types: Maps global term names to their types.
                Example: {"id": ∀a. a → a}
            primitive_types: Maps primitive type names to their types.
                Example: {"Int": Int}
        """
        self.constructors = datatype_constructors if datatype_constructors is not None else {}
        self.global_types = global_types if global_types is not None else {}
        self.primitive_types = primitive_types if primitive_types is not None else {}
        self._meta_counter = itertools.count(0)

    def infer(self, ctx: Context, term: Term) -> Type:
        """Synthesize type from term (bottom-up, ⇒ mode).

        Args:
            ctx: Typing context
            term: Term to infer type for

        Returns:
            The inferred type

        Raises:
            UndefinedVariable: If a variable is not in context
            TypeMismatch: If types don't match
        """
        match term:
            case Var(index):
                # Var: Look up type in context
                try:
                    return ctx.lookup_type(index)
                except IndexError as e:
                    raise UndefinedVariable(index) from e

            case Global(name):
                # Global: Look up type in global environment
                if name not in self.global_types:
                    raise TypeError(f"Undefined global: {name}")
                return self.global_types[name]

            case App(func, arg):
                # App: Infer function type, check argument against domain
                func_type = self.infer(ctx, func)
                match func_type:
                    case TypeArrow(arg_type, ret_type):
                        self.check(ctx, arg, arg_type)
                        return ret_type
                    case _:
                        raise TypeMismatch(TypeArrow(TypeVar("_"), TypeVar("_")), func_type)

            case TApp(func, type_arg):
                # TApp: Infer polymorphic type, instantiate with type arg
                # Special case: if func is a Constructor, look up its type directly
                # to avoid premature instantiation
                if isinstance(func, AstConstructor):
                    if func.name not in self.constructors:
                        raise UndefinedConstructor(func.name)
                    ctor_type = self.constructors[func.name]
                    match ctor_type:
                        case TypeForall(var, body):
                            subst = Substitution.singleton(var, type_arg)
                            return subst.apply(body)
                        case _:
                            # Constructor is not polymorphic, just return its type
                            return ctor_type
                else:
                    func_type = self.infer(ctx, func)
                    match func_type:
                        case TypeForall(var, body):
                            # Instantiate with the type argument
                            subst = Substitution.singleton(var, type_arg)
                            return subst.apply(body)
                        case _:
                            raise TypeMismatch(TypeForall("_", TypeVar("_")), func_type)

            case Constructor(name, args):
                # Constructor: Look up constructor type, instantiate
                if name not in self.constructors:
                    raise UndefinedConstructor(name)
                ctor_type = self.constructors[name]
                return self._infer_constructor(ctx, ctor_type, args)

            case Case(scrutinee, branches):
                # Case: Infer scrutinee type, check all branches match
                scrut_type = self.infer(ctx, scrutinee)
                return self._check_branches(ctx, scrut_type, branches)

            case Let(name, value, body):
                # Let: Infer value, extend context, infer body
                value_type = self.infer(ctx, value)
                new_ctx = ctx.extend_term(value_type)
                return self.infer(new_ctx, body)

            case Abs(var_type, body):
                # Lambda with annotation: we can infer τ → τ' where τ is the annotation
                # and τ' is inferred from the body in the extended context
                new_ctx = ctx.extend_term(var_type)
                body_type = self.infer(new_ctx, body)
                return TypeArrow(var_type, body_type)

            case TAbs(var, body):
                # Type abstraction: infer ∀α.τ where τ is the body type
                new_ctx = ctx.extend_type(var)
                body_type = self.infer(new_ctx, body)
                return TypeForall(var, body_type)

            case IntLit(_):
                # Lookup from prelude-populated registry
                if "Int" not in self.primitive_types:
                    raise TypeError("Int type not registered in primitive_types")
                return self.primitive_types["Int"]

            case StringLit(_):
                # Lookup from prelude-populated registry
                if "String" not in self.primitive_types:
                    raise TypeError("String type not registered in primitive_types")
                return self.primitive_types["String"]

            case PrimOp(name):
                # Handle LLM primitives (e.g., "llm.xxx")
                if name.startswith("llm."):
                    # The type annotation should be set by the elaborator
                    # and stored in the declaration, not here directly
                    # For now, look up in global_types directly
                    func_name = name[4:]  # Strip "llm." prefix
                    if func_name in self.global_types:
                        return self.global_types[func_name]
                    raise TypeError(f"Unknown LLM function: {func_name}")

                # Add $prim. prefix if not already present
                full_name = name if name.startswith("$prim.") else f"$prim.{name}"
                if full_name not in self.global_types:
                    raise TypeError(f"Unknown primitive: {name}")
                return self.global_types[full_name]

            case _:
                # Fall back to checking with a fresh meta-variable
                metavar = self._fresh_meta()
                self.check(ctx, term, metavar)
                return metavar

    def check(self, ctx: Context, term: Term, expected: Type) -> None:
        """Check term against expected type (top-down, ⇐ mode).

        Args:
            ctx: Typing context
            term: Term to check
            expected: Expected type

        Raises:
            TypeMismatch: If term doesn't have the expected type
        """
        match term:
            case Abs(var_type, body):
                # Abs: Match expected arrow type, extend context, check body
                match expected:
                    case TypeArrow(arg_type, ret_type):
                        # Check that var_type matches arg_type
                        subst = unify(var_type, arg_type)
                        # Extend context with the argument type (after unification)
                        new_ctx = ctx.extend_term(arg_type)
                        # Check body with return type
                        self.check(new_ctx, body, ret_type)
                    case _:
                        raise TypeMismatch(expected, TypeArrow(var_type, TypeVar("_")))

            case TAbs(var, body):
                # TAbs: Match expected forall type, extend type context, check body
                match expected:
                    case TypeForall(exp_var, exp_body):
                        # Extend type context
                        new_ctx = ctx.extend_type(var)
                        # Check body, renaming bound variable if needed
                        if var != exp_var:
                            # Rename the bound variable to match
                            body_type = exp_body.substitute({exp_var: TypeVar(var)})
                        else:
                            body_type = exp_body
                        self.check(new_ctx, body, body_type)
                    case _:
                        raise TypeMismatch(expected, TypeForall(var, TypeVar("_")))

            case Constructor(name, args):
                # Con: Check constructor against expected data type
                if name not in self.constructors:
                    raise UndefinedConstructor(name)
                ctor_type = self.constructors[name]
                actual_type = self._infer_constructor(ctx, ctor_type, args)
                # Unify with expected type
                try:
                    unify(actual_type, expected)
                except Exception as e:
                    # Convert unification errors to type mismatch
                    if isinstance(e, TypeMismatch):
                        raise
                    raise TypeMismatch(expected, actual_type) from e

            case _:
                # Fall back to inference and unification
                actual_type = self.infer(ctx, term)
                try:
                    unify(actual_type, expected)
                except Exception as e:
                    # Convert unification errors to type mismatch
                    if isinstance(e, TypeMismatch):
                        raise
                    raise TypeMismatch(expected, actual_type) from e

    def _infer_constructor(self, ctx: Context, ctor_type: Type, args: list[Term]) -> Type:
        """Infer the type of a constructor application.

        Instantiates the constructor's polymorphic type and checks args.
        """
        # Count how many type parameters (foralls) the constructor has
        type_vars = []
        current_type = ctor_type
        while isinstance(current_type, TypeForall):
            type_vars.append(current_type.var)
            current_type = current_type.body

        # Create fresh type variables for instantiation
        subst = Substitution.empty()
        for var in type_vars:
            # Create a fresh meta-variable for this type parameter
            fresh = self._fresh_meta()
            subst = subst.compose(Substitution.singleton(var, fresh))

        # Apply substitution to get the instantiated type
        instantiated = subst.apply(current_type)

        # Now match against argument types
        result_type = instantiated
        for arg in args:
            match result_type:
                case TypeArrow(arg_type, ret_type):
                    self.check(ctx, arg, arg_type)
                    result_type = ret_type
                case _:
                    raise TypeMismatch(TypeArrow(TypeVar("_"), TypeVar("_")), result_type)

        return result_type

    def _check_branches(self, ctx: Context, scrut_type: Type, branches: list[Branch]) -> Type:
        """Check case branches and return the common result type."""
        if not branches:
            raise ValueError("Case expression must have at least one branch")

        result_type: Type | None = None

        for branch in branches:
            # Get constructor signature
            if branch.pattern.constructor not in self.constructors:
                raise UndefinedConstructor(branch.pattern.constructor)

            ctor_type = self.constructors[branch.pattern.constructor]

            # Instantiate the constructor type
            type_vars = []
            current_type = ctor_type
            while isinstance(current_type, TypeForall):
                type_vars.append(current_type.var)
                current_type = current_type.body

            # Create fresh type variables
            subst = Substitution.empty()
            for var in type_vars:
                fresh = self._fresh_meta()
                subst = subst.compose(Substitution.singleton(var, fresh))

            instantiated = subst.apply(current_type)

            # Collect argument types from constructor
            arg_types = []
            temp_type = instantiated
            while isinstance(temp_type, TypeArrow):
                arg_types.append(temp_type.arg)
                temp_type = temp_type.ret

            # temp_type should be the result type constructor
            # Unify with scrutinee type to resolve type parameters
            try:
                result_subst = unify(temp_type, scrut_type)
            except Exception as e:
                # Convert unification errors to type mismatch
                if isinstance(e, TypeMismatch):
                    raise
                raise TypeMismatch(scrut_type, temp_type) from e
            resolved_arg_types = [result_subst.apply(t) for t in arg_types]

            # Extend context with pattern variables
            branch_ctx = ctx
            for i, var_name in enumerate(branch.pattern.vars):
                if i < len(resolved_arg_types):
                    branch_ctx = branch_ctx.extend_term(resolved_arg_types[i])

            # Check the branch body
            branch_type = self.infer(branch_ctx, branch.body)

            # All branches must have the same type
            if result_type is None:
                result_type = branch_type
            else:
                # Unify this branch's type with previous branches
                try:
                    unify(result_type, branch_type)
                except Exception as e:
                    # Convert unification errors to type mismatch
                    if isinstance(e, TypeMismatch):
                        raise
                    raise TypeMismatch(result_type, branch_type) from e

        return result_type if result_type is not None else TypeVar("_")

    def _fresh_meta(self) -> Type:
        """Generate a fresh meta-variable for type inference."""
        idx = next(self._meta_counter)
        return TypeVar(f"_t{idx}")

    def check_program(self, decls: list[Declaration]) -> dict[str, Type]:
        """Type check a sequence of declarations.

        Returns mapping from names to their types.
        """
        ctx = Context.empty()
        result = {}

        for decl in decls:
            match decl:
                case DataDeclaration(name, params, constructors):
                    # Register constructors for this data type
                    for ctor_name, arg_types in constructors:
                        # Build polymorphic constructor type
                        ctor_type: Type = TypeConstructor(name, [TypeVar(p) for p in params])
                        for arg_type in reversed(arg_types):
                            ctor_type = TypeArrow(arg_type, ctor_type)
                        # Add forall for type parameters
                        for param in reversed(params):
                            ctor_type = TypeForall(param, ctor_type)
                        self.constructors[ctor_name] = ctor_type

                case TermDeclaration(name, type_annotation, body):
                    if type_annotation is not None:
                        # Add type annotation to global_types BEFORE checking body
                        # This allows recursive definitions to work
                        self.global_types[name] = type_annotation
                        # Check body against annotation
                        self.check(ctx, body, type_annotation)
                        result[name] = type_annotation
                    else:
                        # Infer type
                        ty = self.infer(ctx, body)
                        # Add inferred type to global_types for subsequent declarations
                        self.global_types[name] = ty
                        result[name] = ty

        return result
