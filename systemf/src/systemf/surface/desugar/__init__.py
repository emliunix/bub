"""Desugaring passes for surface language.

Each pass is an independent transformation that can be composed.
This module provides a collection of standalone desugaring functions.
"""

from __future__ import annotations

# Re-export pass functions with consistent naming
from systemf.surface.desugar.passes import (
    if_to_case_pass,
    operator_to_prim_pass,
    multi_arg_lambda_pass,
    multi_var_type_abs_pass,
    implicit_type_abs_pass,
    desugar_term,
    desugar_declaration,
)

__all__ = [
    # Individual passes
    "if_to_case_pass",
    "operator_to_prim_pass",
    "multi_arg_lambda_pass",
    "multi_var_type_abs_pass",
    "implicit_type_abs_pass",
    # Composite passes
    "desugar_term",
    "desugar_declaration",
]
