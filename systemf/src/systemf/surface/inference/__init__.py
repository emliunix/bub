"""Type inference module for System F surface language.

This module provides type elaboration functionality for Phase 2 of the
multi-pass elaborator pipeline.
"""

from systemf.surface.inference.context import TypeContext
from systemf.surface.inference.elaborator import TypeElaborator, elaborate_term
from systemf.surface.inference.errors import (
    TypeError,
    TypeMismatchError,
    InfiniteTypeError,
    UnificationError,
    KindError,
    UndefinedTypeError,
)
from systemf.surface.inference.unification import (
    TMeta,
    Substitution,
    unify,
    occurs_check,
    resolve_type,
    is_meta_variable,
    is_unresolved_meta,
)

__all__ = [
    "TypeContext",
    "TypeElaborator",
    "elaborate_term",
    "TypeError",
    "TypeMismatchError",
    "InfiniteTypeError",
    "UnificationError",
    "KindError",
    "UndefinedTypeError",
    # Unification
    "TMeta",
    "Substitution",
    "unify",
    "occurs_check",
    "resolve_type",
    "is_meta_variable",
    "is_unresolved_meta",
]
