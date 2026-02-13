"""Session graph for tracking session lineage and intentions."""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class AgentIntention:
    """Intention for a forked agent session."""

    next_steps: str
    context_summary: str
    trigger_on_complete: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_state(self) -> dict[str, Any]:
        return {
            "next_steps": self.next_steps,
            "context_summary": self.context_summary,
            "trigger_on_complete": self.trigger_on_complete,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_state(cls, state: dict[str, Any]) -> AgentIntention:
        created_at = state.get("created_at")
        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        return cls(
            next_steps=state.get("next_steps", ""),
            context_summary=state.get("context_summary", ""),
            trigger_on_complete=state.get("trigger_on_complete"),
            created_at=created_at or datetime.now(UTC),
        )


@dataclass
class SessionMetadata:
    """Metadata for a session in the graph."""

    session_id: str
    parent_session_id: str | None
    from_anchor: str | None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    status: str = "active"


class SessionGraph:
    """Tracks session lineage and intentions."""

    def __init__(self, home: Path, workspace_path: Path) -> None:
        self._home = home
        self._workspace_path = workspace_path
        self._graph_file = home / "session_graph.jsonl"
        self._sessions: dict[str, SessionMetadata] = {}
        self._load()

    def _load(self) -> None:
        if not self._graph_file.exists():
            return
        with self._graph_file.open("r", encoding="utf-8") as f:
            for line in f:
                try:
                    data = json.loads(line)
                    meta = SessionMetadata(
                        session_id=data["session_id"],
                        parent_session_id=data.get("parent_session_id"),
                        from_anchor=data.get("from_anchor"),
                        created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(UTC),
                        status=data.get("status", "active"),
                    )
                    self._sessions[meta.session_id] = meta
                except (json.JSONDecodeError, KeyError):
                    continue

    def _persist(self, meta: SessionMetadata) -> None:
        data = {
            "session_id": meta.session_id,
            "parent_session_id": meta.parent_session_id,
            "from_anchor": meta.from_anchor,
            "created_at": meta.created_at.isoformat(),
            "status": meta.status,
        }
        with self._graph_file.open("a", encoding="utf-8") as f:
            f.write(json.dumps(data, ensure_ascii=False) + "\n")

    def fork(
        self,
        parent_session_id: str | None,
        from_anchor: str | None,
    ) -> str:
        child_id = f"{parent_session_id}-fork-{uuid.uuid4().hex[:8]}" if parent_session_id else uuid.uuid4().hex[:16]
        meta = SessionMetadata(
            session_id=child_id,
            parent_session_id=parent_session_id,
            from_anchor=from_anchor,
        )
        self._sessions[child_id] = meta
        self._persist(meta)
        return child_id

    def get_parent(self, session_id: str) -> str | None:
        meta = self._sessions.get(session_id)
        return meta.parent_session_id if meta else None

    def get_metadata(self, session_id: str) -> SessionMetadata | None:
        return self._sessions.get(session_id)

    def get_children(self, parent_session_id: str) -> list[str]:
        return [
            sid for sid, meta in self._sessions.items()
            if meta.parent_session_id == parent_session_id
        ]

    def list_sessions(self) -> list[SessionMetadata]:
        return list(self._sessions.values())

    def set_status(self, session_id: str, status: str) -> None:
        if session_id in self._sessions:
            self._sessions[session_id].status = status
