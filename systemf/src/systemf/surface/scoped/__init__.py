"""Scoped module for System F surface language.

This module contains the scope checking infrastructure for transforming
name-based variable references to de Bruijn index-based references.
"""

from systemf.surface.scoped.scope_pass import scope_check_pass
from systemf.surface.scoped.context import ScopeContext
from systemf.surface.scoped.errors import (
    DuplicateBindingError,
    GlobalVariableError,
    ScopeDepthError,
    ScopeError,
    UndefinedTypeVariableError,
    UndefinedVariableError,
)

__all__ = [
    # Pass function
    "scope_check_pass",
    # Context
    "ScopeContext",
    # Errors
    "ScopeError",
    "UndefinedVariableError",
    "UndefinedTypeVariableError",
    "DuplicateBindingError",
    "ScopeDepthError",
    "GlobalVariableError",
]
