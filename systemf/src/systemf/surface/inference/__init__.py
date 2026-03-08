"""Type inference module for System F surface language.

This module provides type elaboration functionality for Phase 2 of the
multi-pass elaborator pipeline.
"""

from systemf.surface.inference.bidi_inference import BidiInference
from systemf.surface.inference.signature_collect_pass import signature_collect_pass
from systemf.surface.inference.data_decl_elab_pass import data_decl_elab_pass
from systemf.surface.inference.prepare_contexts_pass import prepare_contexts_pass
from systemf.surface.inference.elab_bodies_pass import elab_bodies_pass
from systemf.surface.inference.build_decls_pass import build_decls_pass
from systemf.surface.inference.context import TypeContext
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
    # Pass functions
    "BidiInference",
    "signature_collect_pass",
    "data_decl_elab_pass",
    "prepare_contexts_pass",
    "elab_bodies_pass",
    "build_decls_pass",
    # Context
    "TypeContext",
    # Errors
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
