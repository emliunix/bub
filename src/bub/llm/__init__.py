"""LLM integration layer for Bub.

This module provides:
- Standard message format definitions (OpenAI-compatible)
- Provider-specific adapters for converting to/from standard format

Design Principle:
    Standard Format (OpenAI) <-> Tape Storage <-> Provider Adapter <-> LLM API

All internal code uses the standard format. Provider adapters convert at the
API boundary, ensuring tape always stores a consistent format regardless of
which provider is used.
"""

from bub.llm.adapters import (
    AnthropicAdapter,
    MiniMaxAdapter,
    OpenAIAdapter,
    ProviderAdapter,
    adapt_messages_for_provider,
    get_provider_adapter,
)
from bub.llm.format import (
    STANDARD_ROLES,
    StandardMessage,
    ToolCall,
    ToolCallFunction,
    create_assistant_message,
    create_system_message,
    create_tool_message,
    create_user_message,
    is_valid_standard_message,
    validate_standard_message,
)

__all__ = [
    # Adapters
    "ProviderAdapter",
    "OpenAIAdapter",
    "MiniMaxAdapter",
    "AnthropicAdapter",
    "get_provider_adapter",
    "adapt_messages_for_provider",
    # Format
    "StandardMessage",
    "ToolCall",
    "ToolCallFunction",
    "STANDARD_ROLES",
    "validate_standard_message",
    "is_valid_standard_message",
    "create_system_message",
    "create_user_message",
    "create_assistant_message",
    "create_tool_message",
]
