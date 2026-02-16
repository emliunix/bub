"""Provider adapters for converting standard format to provider-specific formats.

Adapters in this module convert from the standard OpenAI-compatible format
to provider-specific formats at the API boundary. This ensures:
1. Tape always stores standard format
2. Each provider can have specific adaptations
3. Adding new providers only requires new adapters

Usage:
    adapter = get_provider_adapter("minimax")
    provider_messages = adapter.to_provider(standard_messages)
    standard_response = adapter.from_provider(provider_response)
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class ProviderAdapter(ABC):
    """Abstract base class for provider-specific format adapters."""

    @abstractmethod
    def to_provider(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert standard format messages to provider-specific format.

        Args:
            messages: List of messages in standard OpenAI format

        Returns:
            List of messages in provider-specific format
        """
        ...

    @abstractmethod
    def from_provider(self, response: Any) -> dict[str, Any]:
        """Convert provider response to standard format.

        Args:
            response: Raw provider response

        Returns:
            Standardized response dict with 'content', 'tool_calls', etc.
        """
        ...

    @property
    @abstractmethod
    def supported_roles(self) -> set[str]:
        """Return set of role names supported by this provider."""
        ...


class OpenAIAdapter(ProviderAdapter):
    """Adapter for OpenAI-compatible APIs.

    OpenAI is the reference implementation, so this is essentially a pass-through
    adapter that performs validation.
    """

    SUPPORTED_ROLES: set[str] = {"system", "user", "assistant", "tool", "developer"}

    def to_provider(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Pass through messages, converting developer role to system."""
        result: list[dict[str, Any]] = []
        for msg in messages:
            msg = dict(msg)  # Copy to avoid mutating original
            role = msg.get("role", "")

            # Convert developer role to system for compatibility
            if role == "developer":
                msg["role"] = "system"

            result.append(msg)

        return result

    def from_provider(self, response: Any) -> dict[str, Any]:
        """Extract standard fields from OpenAI response."""
        result: dict[str, Any] = {
            "content": None,
            "tool_calls": [],
            "finish_reason": None,
        }

        if hasattr(response, "choices") and response.choices:
            choice = response.choices[0]
            message = getattr(choice, "message", None)

            if message:
                result["content"] = getattr(message, "content", None)

                # Extract tool calls
                tool_calls = getattr(message, "tool_calls", None)
                if tool_calls:
                    result["tool_calls"] = [
                        {
                            "id": getattr(tc, "id", ""),
                            "type": getattr(tc, "type", "function"),
                            "function": {
                                "name": getattr(getattr(tc, "function", None), "name", ""),
                                "arguments": getattr(getattr(tc, "function", None), "arguments", ""),
                            },
                        }
                        for tc in tool_calls
                    ]

            result["finish_reason"] = getattr(choice, "finish_reason", None)

        return result

    @property
    def supported_roles(self) -> set[str]:
        return self.SUPPORTED_ROLES


class MiniMaxAdapter(OpenAIAdapter):
    """Adapter for MiniMax API.

    MiniMax is OpenAI-compatible but has some quirks:
    - Some versions don't support 'developer' role (converted to 'system')
    - Generally accepts standard OpenAI format including 'tool' role
    """

    # MiniMax supports all standard OpenAI roles
    SUPPORTED_ROLES: set[str] = {"system", "user", "assistant", "tool"}

    def to_provider(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert to MiniMax-compatible format."""
        # MiniMax accepts OpenAI format, so use parent implementation
        return super().to_provider(messages)

    @property
    def supported_roles(self) -> set[str]:
        return self.SUPPORTED_ROLES


class AnthropicAdapter(ProviderAdapter):
    """Adapter for Anthropic Claude API.

    Anthropic uses a different message format that needs conversion:
    - No 'tool' role - tool results are sent as user messages
    - Different tool call format
    """

    SUPPORTED_ROLES: set[str] = {"user", "assistant"}

    def to_provider(self, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Convert standard format to Anthropic format.

        Anthropic doesn't use 'tool' role - tool results become user messages.
        """
        result: list[dict[str, Any]] = []

        for msg in messages:
            msg = dict(msg)
            role = msg.get("role", "")

            if role == "system":
                # Anthropic handles system separately, skip here
                continue

            elif role == "tool":
                # Convert tool results to user messages
                content = msg.get("content", "")
                tool_call_id = msg.get("tool_call_id", "")
                name = msg.get("name", "")

                # Format as user message with tool result
                formatted = f"[Tool Result from {name} | id={tool_call_id}]\n{content}"
                msg["role"] = "user"
                msg["content"] = formatted
                # Remove tool-specific fields
                msg.pop("tool_call_id", None)
                msg.pop("name", None)

            result.append(msg)

        return result

    def from_provider(self, response: Any) -> dict[str, Any]:
        """Extract standard fields from Anthropic response."""
        result: dict[str, Any] = {
            "content": None,
            "tool_calls": [],
            "finish_reason": None,
        }

        # Anthropic response format handling
        content = getattr(response, "content", [])
        text_parts = []
        tool_calls = []

        for block in content:
            block_type = getattr(block, "type", "")
            if block_type == "text":
                text_parts.append(getattr(block, "text", ""))
            elif block_type == "tool_use":
                tool_calls.append({
                    "id": getattr(block, "id", ""),
                    "type": "function",
                    "function": {
                        "name": getattr(block, "name", ""),
                        "arguments": getattr(block, "input", {}),
                    },
                })

        result["content"] = "\n".join(text_parts) if text_parts else None
        result["tool_calls"] = tool_calls
        result["finish_reason"] = getattr(response, "stop_reason", None)

        return result

    @property
    def supported_roles(self) -> set[str]:
        return self.SUPPORTED_ROLES


def get_provider_adapter(provider: str) -> ProviderAdapter:
    """Get the appropriate adapter for a provider.

    Args:
        provider: Provider name (e.g., "openai", "minimax", "anthropic")

    Returns:
        ProviderAdapter instance for the provider

    Raises:
        ValueError: If provider is not supported
    """
    adapters: dict[str, type[ProviderAdapter]] = {
        "openai": OpenAIAdapter,
        "openrouter": OpenAIAdapter,  # OpenRouter is OpenAI-compatible
        "minimax": MiniMaxAdapter,
        "anthropic": AnthropicAdapter,
    }

    provider_lower = provider.lower()

    # Try exact match first
    if provider_lower in adapters:
        return adapters[provider_lower]()

    # Try partial match (e.g., "minimax:text-01" -> "minimax")
    for key, adapter_class in adapters.items():
        if key in provider_lower:
            return adapter_class()

    # Default to OpenAI adapter for unknown providers
    return OpenAIAdapter()


def adapt_messages_for_provider(
    messages: list[dict[str, Any]],
    provider: str,
) -> list[dict[str, Any]]:
    """Convenience function to adapt messages for a provider.

    Args:
        messages: List of messages in standard format
        provider: Provider name

    Returns:
        Messages in provider-specific format
    """
    adapter = get_provider_adapter(provider)
    return adapter.to_provider(messages)
