"""Application-level type definitions."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from republic.tape import TapeEntry

from bub.bub_types import MessageBus


class AgentSettings(Protocol):
    """Protocol for agent settings."""

    model: str
    max_tokens: int
    max_steps: int
    system_prompt: str
    model_timeout_seconds: int | None
    ollama_api_key: str | None
    ollama_api_base: str | None


class TapeSettings(Protocol):
    """Protocol for tape settings."""

    name: str

    @property
    def tape_name(self) -> str: ...

    def resolve_home(self) -> Path: ...


class AgentRuntime(Protocol):
    """Protocol for agent runtime."""

    workspace: Path

    @property
    def settings(self) -> AgentSettings: ...

    @property
    def tape_settings(self) -> TapeSettings: ...

    bus: MessageBus

    def get_session(self, session_id: str) -> Session: ...
    def reset_session_context(self, session_id: str) -> None: ...
    def discover_skills(self) -> list[Any]: ...
    def load_skill_body(self, skill_name: str) -> str | None: ...


class Session(Protocol):
    """Protocol for session runtime state."""

    def reset_context(self) -> None: ...


class TapeStore(Protocol):
    """Protocol for tape store implementations."""

    def create_tape(self, tape: str, title: str | None = None) -> str: ...
    def get_title(self, tape: str) -> str | None: ...
    def list_tapes(self) -> list[str]: ...
    def read(
        self, tape: str, from_entry_id: int | None = None, to_entry_id: int | None = None
    ) -> list[TapeEntry] | None: ...
    def append(self, tape: str, entry: TapeEntry) -> None: ...
    def fork(
        self,
        from_tape: str,
        new_tape_id: str | None = None,
        from_entry: tuple[str, int] | None = None,
        from_anchor: str | None = None,
    ) -> str: ...
    def archive(self, tape_id: str) -> Path | None: ...
    def reset(self, tape: str) -> None: ...
    def create_anchor(self, name: str, tape_id: str, entry_id: int, state: dict[str, Any] | None = None) -> None: ...
    def get_anchor(self, name: str) -> TapeEntry | None: ...
    def list_anchors(self) -> list[TapeEntry]: ...
    def resolve_anchor(self, name: str) -> int: ...
