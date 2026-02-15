"""Remote tape store client that connects to tape server."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import httpx
from republic.tape import TapeEntry

from bub.tape.types import Anchor


class RemoteTapeStore:
    """Client for remote tape server."""

    def __init__(self, base_url: str, workspace_path: Path) -> None:
        self.base_url = base_url.rstrip("/")
        self.workspace_path = workspace_path
        self._client = httpx.Client(timeout=30.0)

    def _url(self, path: str) -> str:
        return f"{self.base_url}{path}"

    def close(self) -> None:
        """Close the HTTP client."""
        self._client.close()

    def create_tape(self, tape: str, title: str | None = None) -> str:
        """Create a new tape."""
        response = self._client.post(
            self._url("/tapes"),
            json={"tape_id": tape, "title": title},
        )
        response.raise_for_status()
        return tape

    def get_title(self, tape: str) -> str | None:
        """Get the title of a tape."""
        try:
            response = self._client.get(self._url(f"/tapes/{tape}"))
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            return data.get("title") if data else None
        except httpx.HTTPError:
            return None

    def set_title(self, tape: str, title: str) -> None:
        """Set the title of a tape (not supported in remote)."""
        pass

    def list_tapes(self) -> list[str]:
        """List all tapes."""
        response = self._client.get(self._url("/tapes"))
        response.raise_for_status()
        data = response.json()
        return list(data.get("tapes", []) or [])

    def read(
        self, tape: str, from_entry_id: int | None = None, to_entry_id: int | None = None
    ) -> list[TapeEntry] | None:
        """Read tape entries."""
        params = {}
        if from_entry_id is not None:
            params["from_entry_id"] = from_entry_id
        if to_entry_id is not None:
            params["to_entry_id"] = to_entry_id

        response = self._client.get(
            self._url(f"/tapes/{tape}/entries"),
            params=params if params else None,
        )
        if response.status_code == 404:
            return None
        response.raise_for_status()
        entries_data = response.json().get("entries", [])
        return [
            TapeEntry(
                id=entry.get("id", 0),
                kind=entry.get("kind", ""),
                payload=entry.get("payload", {}),
                meta=entry.get("meta", {}),
            )
            for entry in entries_data
        ]

    def append(self, tape: str, entry: Any) -> None:
        """Append an entry to a tape."""
        from republic.tape import TapeEntry

        if isinstance(entry, TapeEntry):
            entry_data = {
                "kind": entry.kind,
                "payload": entry.payload,
                "meta": getattr(entry, "meta", {}),
            }
        else:
            entry_data = entry

        response = self._client.post(
            self._url(f"/tapes/{tape}/entries"),
            json=entry_data,
        )
        response.raise_for_status()

    def fork(
        self,
        from_tape: str,
        new_tape_id: str | None = None,
        from_entry: tuple[str, int] | None = None,
        from_anchor: str | None = None,
    ) -> str:
        """Fork a tape."""
        from_entry_id = from_entry[1] if from_entry else None
        response = self._client.post(
            self._url(f"/tapes/{from_tape}/fork"),
            json={
                "new_tape_id": new_tape_id,
                "from_entry_id": from_entry_id,
                "from_anchor": from_anchor,
            },
        )
        response.raise_for_status()
        data = response.json()
        return data.get("id") or new_tape_id or ""

    def archive(self, tape_id: str) -> Path | None:
        """Archive a tape."""
        response = self._client.post(self._url(f"/tapes/{tape_id}/archive"))
        response.raise_for_status()
        archived = response.json().get("archived")
        return Path(archived) if archived else None

    def reset(self, tape_id: str) -> None:
        """Reset a tape."""
        response = self._client.post(self._url(f"/tapes/{tape_id}/reset"))
        response.raise_for_status()

    def create_anchor(self, name: str, tape_id: str, entry_id: int, state: dict[str, Any] | None = None) -> None:
        """Create an anchor."""
        response = self._client.post(
            self._url("/anchors"),
            json={"name": name, "tape_id": tape_id, "entry_id": entry_id, "state": state},
        )
        response.raise_for_status()

    def get_anchor(self, name: str) -> Anchor | None:
        """Get an anchor by name."""
        try:
            response = self._client.get(self._url(f"/anchors/{name}"))
            if response.status_code == 404:
                return None
            response.raise_for_status()
            data = response.json()
            return Anchor(
                name=data["name"],
                tape_id=data["tape_id"],
                entry_id=data["entry_id"],
                state=data.get("state"),
            )
        except httpx.HTTPError:
            return None

    def update_anchor(self, name: str, entry_id: int | None = None, state: dict[str, object] | None = None) -> None:
        """Update an anchor (not supported in remote)."""
        pass

    def delete_anchor(self, name: str) -> None:
        """Delete an anchor (not supported in remote)."""
        pass

    def list_anchors(self) -> list[Anchor]:
        """List all anchors."""
        response = self._client.get(self._url("/anchors"))
        response.raise_for_status()
        anchors = response.json().get("anchors", [])
        return [
            Anchor(
                name=a["name"],
                tape_id=a["tape_id"],
                entry_id=a["entry_id"],
                state=a.get("state"),
            )
            for a in anchors
        ]

    def resolve_anchor(self, name: str) -> int:
        """Resolve anchor name to entry ID."""
        anchor = self.get_anchor(name)
        if anchor is None:
            raise ValueError(f"Anchor not found: {name}")
        return anchor.entry_id
