"""LLM pragma processing module for System F surface language.

This module provides functionality for Phase 3 of the elaboration pipeline:
processing LLM pragma annotations on function declarations.
"""

from systemf.surface.llm.pragma_pass import (
    llm_pragma_pass,
    LLMError,
    parse_pragma_config,
)
from systemf.core.module import LLMMetadata

__all__ = [
    "llm_pragma_pass",
    "LLMMetadata",
    "LLMError",
    "parse_pragma_config",
]
