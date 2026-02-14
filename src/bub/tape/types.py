"""Tape types."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class TapeMeta:
    """Metadata for a tape."""

    id: str
    file: str
    title: str | None = None
    parent: tuple[str, int] | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass(frozen=True)
class Anchor:
    """Standalone anchor pointer to a tape entry."""

    name: str
    tape_id: str
    entry_id: int
    state: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class Manifest:
    """In-memory manifest for managing tapes and anchors."""

    VERSION = 1

    def __init__(self) -> None:
        self._tapes: dict[str, TapeMeta] = {}
        self._anchors: dict[str, Anchor] = {}

    @property
    def version(self) -> int:
        return self.VERSION

    @property
    def tapes(self) -> dict[str, TapeMeta]:
        return self._tapes

    @property
    def anchors(self) -> dict[str, Anchor]:
        return self._anchors

    def create_tape(
        self,
        tape_id: str,
        file: str | None = None,
        title: str | None = None,
        parent: tuple[str, int] | None = None,
    ) -> TapeMeta:
        """Create a new tape in the manifest."""
        if file is None:
            file = f"{tape_id}.jsonl"
        meta = TapeMeta(id=tape_id, file=file, title=title, parent=parent)
        self._tapes[tape_id] = meta
        return meta

    def get_tape(self, tape_id: str) -> TapeMeta | None:
        """Get tape metadata by ID."""
        return self._tapes.get(tape_id)

    def update_tape(self, tape_id: str, title: str | None = None) -> None:
        """Update tape metadata."""
        if tape_id not in self._tapes:
            raise KeyError(f"Tape not found: {tape_id}")
        meta = self._tapes[tape_id]
        self._tapes[tape_id] = TapeMeta(
            id=meta.id,
            file=meta.file,
            title=title if title is not None else meta.title,
            parent=meta.parent,
            created_at=meta.created_at,
        )

    def delete_tape(self, tape_id: str) -> None:
        """Delete a tape from the manifest."""
        self._tapes.pop(tape_id, None)

    def fork_tape(self, source_id: str, new_id: str, parent: tuple[str, int] | None = None) -> TapeMeta:
        """Fork a tape, creating a new one pointing to the same file."""
        source = self.get_tape(source_id)
        if source is None:
            source_file = f"{source_id}.jsonl"
            source = self.create_tape(source_id, file=source_file)
        if parent is None:
            parent = (source_id, 0)
        return self.create_tape(new_id, file=source.file, parent=parent)

    def create_anchor(
        self,
        name: str,
        tape_id: str,
        entry_id: int,
        state: dict[str, object] | None = None,
    ) -> Anchor:
        """Create a new anchor."""
        anchor = Anchor(name=name, tape_id=tape_id, entry_id=entry_id, state=state or {})
        self._anchors[name] = anchor
        return anchor

    def get_anchor(self, name: str) -> Anchor | None:
        """Get anchor by name."""
        return self._anchors.get(name)

    def update_anchor(
        self,
        name: str,
        entry_id: int | None = None,
        tape_id: str | None = None,
        state: dict[str, object] | None = None,
    ) -> None:
        """Update anchor metadata."""
        if name not in self._anchors:
            raise KeyError(f"Anchor not found: {name}")
        current = self._anchors[name]
        self._anchors[name] = Anchor(
            name=name,
            tape_id=tape_id or current.tape_id,
            entry_id=entry_id or current.entry_id,
            state=state or current.state,
            created_at=current.created_at,
        )

    def delete_anchor(self, name: str) -> None:
        """Delete an anchor."""
        self._anchors.pop(name, None)

    def resolve_anchor(self, name: str) -> int:
        """Resolve anchor name to entry ID."""
        anchor = self.get_anchor(name)
        if anchor is None:
            raise KeyError(f"Anchor not found: {name}")
        return anchor.entry_id
