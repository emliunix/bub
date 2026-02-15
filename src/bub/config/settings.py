"""Application settings."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class TapeSettings(BaseSettings):
    """Tape store settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="BUB_TAPE_",
        case_sensitive=False,
        extra="ignore",
    )

    home: str | None = Field(default=None)
    workspace_path: str | None = Field(default=None)
    name: str = Field(default="bub")
    host: str = Field(default="localhost")
    port: int = Field(default=7890)

    def resolve_home(self) -> Path:
        if self.home:
            return Path(self.home).expanduser().resolve()
        return (Path.home() / ".bub").resolve()

    @property
    def tape_name(self) -> str:
        return self.name


class BusSettings(BaseSettings):
    """Message bus / channel settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="BUB_BUS_",
        case_sensitive=False,
        extra="ignore",
    )

    host: str = Field(default="localhost")
    port: int = Field(default=7892)
    telegram_enabled: bool = Field(default=False)
    telegram_token: str | None = Field(default=None)
    telegram_allow_from: list[str] = Field(default_factory=list)
    telegram_allow_chats: list[str] = Field(default_factory=list)
    telegram_proxy: str | None = Field(default=None)


class AgentSettings(BaseSettings):
    """Agent / LLM settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="BUB_AGENT_",
        case_sensitive=False,
        extra="ignore",
        env_parse_none_str="null",
    )

    model: str = Field(default="openrouter:qwen/qwen3-coder-next")
    api_key: str | None = Field(default=None)
    api_base: str | None = Field(default=None)
    ollama_api_key: str | None = Field(default=None)
    ollama_api_base: str | None = Field(default=None)
    llm_api_key: str | None = Field(default=None, validation_alias="LLM_API_KEY")
    openrouter_api_key: str | None = Field(default=None, validation_alias="OPENROUTER_API_KEY")
    max_tokens: int = Field(default=1024, ge=1)
    model_timeout_seconds: int | None = 90
    system_prompt: str = Field(default="")
    max_steps: int = Field(default=20, ge=1)
    tape_server_url: str | None = Field(default=None)
    bus_url: str | None = Field(default=None)

    @property
    def resolved_api_key(self) -> str | None:
        if self.api_key:
            return self.api_key
        if self.llm_api_key:
            return self.llm_api_key
        if self.openrouter_api_key:
            return self.openrouter_api_key
        return os.getenv("LLM_API_KEY") or os.getenv("OPENROUTER_API_KEY")


class Settings(TapeSettings, BusSettings, AgentSettings):
    """Unified settings - composition of all component settings.

    For backwards compatibility, all settings are accessible from one place.
    """

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)


def load_settings(workspace_path: Path | None = None) -> Settings:
    """Load unified settings with optional workspace override."""
    if workspace_path is None:
        return Settings()
    return Settings(workspace_path=str(workspace_path.resolve()))
