from __future__ import annotations

import json
import os
import pathlib
import re
from collections.abc import Callable
from typing import Any, Literal

from pydantic import Field
from pydantic_settings import SettingsConfigDict

from bub import Settings, config, ensure_config

DEFAULT_MODEL = "openrouter:openrouter/free"
DEFAULT_MAX_TOKENS = 16384


def provider_specific(setting_name: str) -> Callable[[], dict[str, str] | None]:
    def default_factory() -> dict[str, str] | None:
        setting_regex = re.compile(rf"^BUB_(.+)_{setting_name.upper()}$")
        loaded_env = os.environ
        result: dict[str, str] = {}
        for key, value in loaded_env.items():
            if value is None:
                continue
            if match := setting_regex.match(key):
                provider = match.group(1).lower()
                result[provider] = value
        return result or None

    return default_factory


def provider_specific_json(setting_name: str) -> Callable[[], dict[str, Any] | None]:
    """Like provider_specific but parses values as JSON (for dict-valued settings like client_args)."""

    def default_factory() -> dict[str, Any] | None:
        setting_regex = re.compile(rf"^BUB_(.+)_{setting_name.upper()}$")
        result: dict[str, Any] = {}
        for key, value in os.environ.items():
            if value is None:
                continue
            if match := setting_regex.match(key):
                provider = match.group(1).lower()
                try:
                    result[provider] = json.loads(value)
                except json.JSONDecodeError:
                    result[provider] = value
        if result and "default" not in result:
            result["default"] = {}
        return result or None

    return default_factory


@config()
class AgentSettings(Settings):
    """Configuration settings for the Agent."""

    model_config = SettingsConfigDict(env_prefix="BUB_", env_parse_none_str="null", extra="ignore")
    model: str = DEFAULT_MODEL
    fallback_models: list[str] | None = None
    api_key: str | dict[str, str] | None = Field(default_factory=provider_specific("api_key"))
    api_base: str | dict[str, str] | None = Field(default_factory=provider_specific("api_base"))
    api_format: Literal["completion", "responses", "messages"] = "completion"
    reasoning_effort: str | None = None
    reasoning_strategy: str | dict[str, str] | None = Field(
        default_factory=provider_specific("reasoning_strategy"),
        description="Strategy for pruning reasoning_content from historical assistant messages. "
        "Valid values: full, prune, last_turn_only, tool_calls_only. "
        "Can be provider-specific: {openai: full, anthropic: prune}.",
    )
    max_steps: int = 50
    max_tokens: int = DEFAULT_MAX_TOKENS
    model_timeout_seconds: int | None = None
    client_args: dict[str, Any] | None = Field(
        default_factory=provider_specific_json("client_args"),
        description="Extra arguments passed to the LLM client constructor. Can be global or provider-specific. "
        "Provider-specific mode requires a 'default' key (auto-injected from env).",
    )
    transport_args: dict[str, Any] | None = Field(
        default_factory=provider_specific_json("transport_args"),
        description="Extra kwargs passed to each LLM transport call (request body). Can be global or provider-specific. "
        "Use this for provider-specific request params like 'thinking' for zai.",
    )
    verbose: int = Field(default=0, description="Verbosity level for logging. Higher means more verbose.", ge=0, le=2)

    @property
    def home(self) -> pathlib.Path:
        import warnings

        import bub

        warnings.warn(
            "Using the 'home' property from AgentSettings is deprecated. Please use 'bub.home' instead.",
            DeprecationWarning,
            stacklevel=2,
        )

        return bub.home


def load_settings() -> AgentSettings:
    return ensure_config(AgentSettings)
