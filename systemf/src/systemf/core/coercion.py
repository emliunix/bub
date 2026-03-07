"""Coercion types for System FC.

System FC extends System F with explicit coercion types that witness type equality.
A coercion γ is a proof that two types are equal: γ : τ₁ ~ τ₂

Coercions enable:
- Zero-cost type conversions (coercions are erased at runtime)
- Impredicative polymorphism through type-safe casts
- ADT representation coercions (ax_Nat : Nat ~ Repr(Nat))

The coercion system forms a category with:
- Identity: Refl(τ) : τ ~ τ
- Composition: Comp(γ₁, γ₂) : τ₁ ~ τ₃ when γ₁ : τ₁ ~ τ₂ and γ₂ : τ₂ ~ τ₃
- Inverses: Sym(γ) : τ₂ ~ τ₁ when γ : τ₁ ~ τ₂
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Union

from systemf.core.types import Type


class Coercion:
    """Base class for coercions (proofs of type equality).

    A coercion γ represents a proof that two types are equal: γ : τ₁ ~ τ₂
    The coercion carries the left and right types explicitly for type checking.
    """

    @property
    def left(self) -> Type:
        """The left-hand side type (τ₁ in τ₁ ~ τ₂)."""
        raise NotImplementedError

    @property
    def right(self) -> Type:
        """The right-hand side type (τ₂ in τ₁ ~ τ₂)."""
        raise NotImplementedError

    def free_vars(self) -> set[str]:
        """Return set of free type variables in this coercion."""
        return self.left.free_vars() | self.right.free_vars()

    def substitute(self, subst: dict[str, Type]) -> Coercion:
        """Apply substitution to types in this coercion."""
        raise NotImplementedError


@dataclass(frozen=True)
class CoercionRefl(Coercion):
    """Reflexivity: τ ~ τ for any type τ.

    This is the identity coercion. Every type is equal to itself.
    Example: Refl(Int) : Int ~ Int
    """

    ty: Type

    @property
    def left(self) -> Type:
        return self.ty

    @property
    def right(self) -> Type:
        return self.ty

    def substitute(self, subst: dict[str, Type]) -> Coercion:
        return CoercionRefl(self.ty.substitute(subst))


@dataclass(frozen=True)
class CoercionSym(Coercion):
    """Symmetry: if γ : τ₁ ~ τ₂, then Sym(γ) : τ₂ ~ τ₁.

    Every coercion can be inverted. This is crucial for pattern matching
    where we need to convert from representation types back to abstract types.
    Example: Sym(ax_Nat) : Repr(Nat) ~ Nat
    """

    coercion: Coercion

    @property
    def left(self) -> Type:
        return self.coercion.right

    @property
    def right(self) -> Type:
        return self.coercion.left

    def substitute(self, subst: dict[str, Type]) -> Coercion:
        return CoercionSym(self.coercion.substitute(subst))


@dataclass(frozen=True)
class CoercionTrans(Coercion):
    """Transitivity: if γ₁ : τ₁ ~ τ₂ and γ₂ : τ₂ ~ τ₃, then Trans(γ₁, γ₂) : τ₁ ~ τ₃.

    Allows chaining coercions together. The intermediate type τ₂ must match.
    Example: If γ₁ : Int ~ Nat and γ₂ : Nat ~ Repr(Nat),
             then Trans(γ₁, γ₂) : Int ~ Repr(Nat)
    """

    first: Coercion  # γ₁ : τ₁ ~ τ₂
    second: Coercion  # γ₂ : τ₂ ~ τ₃

    @property
    def left(self) -> Type:
        return self.first.left

    @property
    def right(self) -> Type:
        return self.second.right

    def substitute(self, subst: dict[str, Type]) -> Coercion:
        return CoercionTrans(self.first.substitute(subst), self.second.substitute(subst))


@dataclass(frozen=True)
class CoercionComp(Coercion):
    """Composition: sequential composition of coercions.

    Similar to transitivity but used for composing coercion transformations.
    Comp(γ₁, γ₂) is semantically equivalent to Trans(γ₁, γ₂).
    We keep both for explicitness in different contexts.
    """

    before: Coercion  # γ₁ : τ₁ ~ τ₂ (applied first)
    after: Coercion  # γ₂ : τ₂ ~ τ₃ (applied second)

    @property
    def left(self) -> Type:
        return self.before.left

    @property
    def right(self) -> Type:
        return self.after.right

    def substitute(self, subst: dict[str, Type]) -> Coercion:
        return CoercionComp(self.before.substitute(subst), self.after.substitute(subst))


@dataclass(frozen=True)
class CoercionAxiom(Coercion):
    """Axiom coercion: named coercion axiom with type arguments.

    Axiom coercions are generated for ADT representations and other
    type-level equalities that the system accepts as given.

    Examples:
    - ax_Nat : Nat ~ Repr(Nat)  (ADT representation)
    - ax_List : ∀α. List α ~ Repr(List α)
    - ax_Arr : ∀α.∀β. Array α β ~ Repr(Array α β)

    Axiom coercions are parameterized by type arguments to support
    polymorphic types. The axiom name uniquely identifies the coercion rule.
    """

    name: str  # Unique axiom name (e.g., "ax_Nat", "ax_List")
    left_ty: Type  # Left type (τ₁ in τ₁ ~ τ₂)
    right_ty: Type  # Right type (τ₂ in τ₁ ~ τ₂)
    type_args: list[Type] = field(default_factory=list)  # Type arguments for polymorphic axioms

    @property
    def left(self) -> Type:
        return self.left_ty

    @property
    def right(self) -> Type:
        return self.right_ty

    def substitute(self, subst: dict[str, Type]) -> Coercion:
        return CoercionAxiom(
            self.name,
            self.left_ty.substitute(subst),
            self.right_ty.substitute(subst),
            [arg.substitute(subst) for arg in self.type_args],
        )


# Type alias for coercion union
coercion = Union[CoercionRefl, CoercionSym, CoercionTrans, CoercionComp, CoercionAxiom]


class CoercionError(Exception):
    """Error in coercion construction or composition."""

    pass


def coercion_equality(c1: Coercion, c2: Coercion) -> bool:
    """Check if two coercions are structurally equal.

    Two coercions are equal if:
    1. They have the same constructor
    2. Their components are recursively equal
    3. The types they witness are equal

    This is syntactic equality, not semantic equivalence.
    For example, Trans(Refl(τ), γ) and γ are semantically equal
    but syntactically different.
    """
    if type(c1) != type(c2):
        return False

    # Check that both witness the same type equality
    if c1.left != c2.left or c1.right != c2.right:
        return False

    match c1:
        case CoercionRefl():
            return True  # Types already checked above
        case CoercionSym(coercion=inner1):
            inner2 = c2.coercion  # type: ignore[attr-defined]
            return coercion_equality(inner1, inner2)
        case CoercionTrans(first=f1, second=s1):
            f2 = c2.first  # type: ignore[attr-defined]
            s2 = c2.second  # type: ignore[attr-defined]
            return coercion_equality(f1, f2) and coercion_equality(s1, s2)
        case CoercionComp(before=b1, after=a1):
            b2 = c2.before  # type: ignore[attr-defined]
            a2 = c2.after  # type: ignore[attr-defined]
            return coercion_equality(b1, b2) and coercion_equality(a1, a2)
        case CoercionAxiom(name=n1, type_args=args1):
            n2 = c2.name  # type: ignore[attr-defined]
            args2 = c2.type_args  # type: ignore[attr-defined]
            return (
                n1 == n2
                and len(args1) == len(args2)
                and all(a1 == a2 for a1, a2 in zip(args1, args2))
            )
        case _:
            return False


def compose_coercions(first: Coercion, second: Coercion) -> Coercion:
    """Compose two coercions: γ₁ ; γ₂ where γ₁ : τ₁ ~ τ₂ and γ₂ : τ₂ ~ τ₃.

    Returns γ : τ₁ ~ τ₃

    Raises CoercionError if the coercions don't compose (τ₂ doesn't match).

    Optimization: Normalizes Refl compositions.
    - compose(Refl(τ), γ) = γ
    - compose(γ, Refl(τ)) = γ
    """
    # Check that coercions compose: first.right must equal second.left
    if first.right != second.left:
        raise CoercionError(f"Cannot compose coercions: {first.right} != {second.left}")

    # Optimizations with Refl
    if isinstance(first, CoercionRefl):
        return second
    if isinstance(second, CoercionRefl):
        return first

    # General case: use transitivity
    return CoercionTrans(first, second)


def invert_coercion(c: Coercion) -> Coercion:
    """Invert a coercion: if γ : τ₁ ~ τ₂, return γ' : τ₂ ~ τ₁.

    This is the Sym operation but with normalization:
    - invert(Refl(τ)) = Refl(τ)  (identity is its own inverse)
    - invert(Sym(γ)) = γ  (double negation elimination)
    - invert(γ) = Sym(γ)  (general case)
    """
    match c:
        case CoercionRefl():
            return c  # Refl is its own inverse
        case CoercionSym(coercion=inner):
            return inner  # Double negation: Sym(Sym(γ)) = γ
        case _:
            return CoercionSym(c)


def normalize_coercion(c: Coercion) -> Coercion:
    """Normalize a coercion to a canonical form.

    Applies simplification rules:
    - Trans(Refl(τ), γ) → γ
    - Trans(γ, Refl(τ)) → γ
    - Sym(Sym(γ)) → γ
    - Trans(Trans(γ₁, γ₂), γ₃) → Trans(γ₁, Trans(γ₂, γ₃))

    This helps with coercion equality checking and keeps coercions minimal.
    """
    match c:
        case CoercionRefl():
            return c
        case CoercionSym(coercion=inner):
            inner_norm = normalize_coercion(inner)
            return invert_coercion(inner_norm)
        case CoercionTrans(first=f, second=s):
            f_norm = normalize_coercion(f)
            s_norm = normalize_coercion(s)

            # Trans(Refl, γ) = γ
            if isinstance(f_norm, CoercionRefl):
                return s_norm
            # Trans(γ, Refl) = γ
            if isinstance(s_norm, CoercionRefl):
                return f_norm

            return CoercionTrans(f_norm, s_norm)
        case CoercionComp(before=b, after=a):
            # Comp is semantically Trans
            return normalize_coercion(CoercionTrans(b, a))
        case CoercionAxiom():
            return c  # Axioms are already in normal form
        case _:
            return c
