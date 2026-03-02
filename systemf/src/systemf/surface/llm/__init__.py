"""LLM pragma processing module for System F surface language.

This module provides functionality for Phase 3 of the elaboration pipeline:
processing LLM pragma annotations on function declarations.
"""

from systemf.surface.llm.pragma_pass import (
    LLMPragmaPass,
    LLMPragmaResult,
    process_llm_pragmas,
    parse_pragma_config,
)

__all__ = [
    "LLMPragmaPass",
    "LLMPragmaResult",
    "process_llm_pragmas",
    "parse_pragma_config",
]
