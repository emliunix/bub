"""Persistent tape store implementation."""

from __future__ import annotations

import json
import shutil
import threading
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import md5
from pathlib import Path
from typing import cast
from urllib.parse import quote, unquote

from loguru import logger
from republic.tape import TapeEntry

from bub.tape.types import Anchor, Manifest, TapeMeta

TAPE_FILE_SUFFIX = ".jsonl"


@dataclass(frozen=True)
class TapePaths:
    """Resolved tape paths for one workspace."""

    home: Path
    tape_root: Path
    workspace_hash: str


class TapeFile:
    """Helper for one tape file."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self.fork_start_id: int | None = None
        self._lock = threading.Lock()
        self._read_entries: list[TapeEntry] = []
        self._read_offset = 0

    def copy_to(self, target: TapeFile, from_entry_id: int | None = None) -> None:
        if self.path.exists():
            shutil.copy2(self.path, target.path)
        target._read_entries = self.read()
        target.fork_start_id = self._next_id()
        target._read_offset = self._read_offset
        if from_entry_id is not None and from_entry_id > 0:
            target.fork_start_id = from_entry_id

    def copy_from(self, source: TapeFile) -> None:
        entries = [entry for entry in source.read() if entry.id >= (source.fork_start_id or 0)]
        self._append_many(entries)
        # Refresh to update intenal state
        self.read()

    def _next_id(self) -> int:
        if self._read_entries:
            return cast(int, self._read_entries[-1].id + 1)
        return 1

    def _reset(self) -> None:
        self._read_entries = []
        self._read_offset = 0

    def reset(self) -> None:
        with self._lock:
            if self.path.exists():
                self.path.unlink()
            self._reset()

    def read(self) -> list[TapeEntry]:
        with self._lock:
            return self._read_locked()

    def _read_locked(self) -> list[TapeEntry]:
        if not self.path.exists():
            self._reset()
            return []

        file_size = self.path.stat().st_size
        if file_size < self._read_offset:
            # The file was truncated or replaced, so cached entries are stale.
            self._reset()

        with self.path.open("r", encoding="utf-8") as handle:
            handle.seek(self._read_offset)
            for raw_line in handle:
                line = raw_line.strip()
                if not line:
                    continue
                try:
                    payload = json.loads(line)
                except json.JSONDecodeError:
                    continue
                entry = self.entry_from_payload(payload)
                if entry is not None:
                    self._read_entries.append(entry)
            self._read_offset = handle.tell()

        return list(self._read_entries)

    @staticmethod
    def entry_to_payload(entry: TapeEntry) -> dict[str, object]:
        return {
            "id": entry.id,
            "kind": entry.kind,
            "payload": dict(entry.payload),
            "meta": dict(entry.meta),
        }

    @staticmethod
    def entry_from_payload(payload: object) -> TapeEntry | None:
        if not isinstance(payload, dict):
            return None
        entry_id = payload.get("id")
        kind = payload.get("kind")
        entry_payload = payload.get("payload")
        meta = payload.get("meta")
        if not isinstance(entry_id, int):
            return None
        if not isinstance(kind, str):
            return None
        if not isinstance(entry_payload, dict):
            return None
        if not isinstance(meta, dict):
            meta = {}
        return TapeEntry(entry_id, kind, dict(entry_payload), dict(meta))

    def append(self, entry: TapeEntry) -> None:
        return self._append_many([entry])

    def _append_many(self, entries: list[TapeEntry]) -> None:
        if not entries:
            return

        with self._lock:
            # Keep cache and offset in sync before allocating new IDs.
            self._read_locked()
            with self.path.open("a", encoding="utf-8") as handle:
                next_id = self._next_id()
                for entry in entries:
                    stored = TapeEntry(next_id, entry.kind, dict(entry.payload), dict(entry.meta))
                    handle.write(json.dumps(self.entry_to_payload(stored), ensure_ascii=False) + "\n")
                    self._read_entries.append(stored)
                    next_id += 1
                self._read_offset = handle.tell()

    def archive(self) -> Path | None:
        if not self.path.exists():
            return None
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        archive_file = self.path.with_suffix(f"{TAPE_FILE_SUFFIX}.{stamp}.bak")
        self.path.replace(archive_file)
        return archive_file


class FileTapeStore:
    """Append-only JSONL tape store with manifest-based tape management.

    All tape operations go through this class. The manifest is an internal
    implementation detail for tracking tape metadata and anchors.
    """

    def __init__(self, home: Path, workspace_path: Path) -> None:
        self._paths = self._resolve_paths(home, workspace_path)
        self._lock = threading.Lock()

    # -------------------------------------------------------------------------
    # Tape operations
    # -------------------------------------------------------------------------

    def create_tape(self, tape: str, title: str | None = None) -> str:
        """Create a new tape. Returns the tape ID."""
        logger.debug("tape.store.create tape={} title={}", tape, title)
        manifest = self._load_manifest()
        manifest.create_tape(tape, title=title)
        self.save_manifest(manifest)
        logger.info("tape.store.created tape={}", tape)
        return tape

    def get_title(self, tape: str) -> str | None:
        """Get the title of a tape."""
        manifest = self._load_manifest()
        meta = manifest.get_tape(tape)
        return meta.title if meta else None

    def set_title(self, tape: str, title: str) -> None:
        """Set the title of a tape."""
        manifest = self._load_manifest()
        manifest.update_tape(tape, title=title)
        self.save_manifest(manifest)

    def list_tapes(self) -> list[str]:
        """List all tapes."""
        with self._lock:
            tapes: list[str] = []
            prefix = f"{self._paths.workspace_hash}__"
            for path in self._paths.tape_root.glob(f"{prefix}*{TAPE_FILE_SUFFIX}"):
                encoded = path.name.removeprefix(prefix).removesuffix(TAPE_FILE_SUFFIX)
                if not encoded or "__" in encoded:
                    continue
                tapes.append(unquote(encoded))
            return sorted(set(tapes))

    def read(
        self, tape: str, from_entry_id: int | None = None, to_entry_id: int | None = None
    ) -> list[TapeEntry] | None:
        """Read tape entries, optionally by range."""
        logger.debug("tape.store.read tape={} from={} to={}", tape, from_entry_id, to_entry_id)
        tape_file = self._make_tape_file(tape)
        if not tape_file.path.exists():
            logger.warning("tape.store.not_found tape={}", tape)
            return None
        entries = tape_file.read()
        if from_entry_id is not None:
            entries = [e for e in entries if e.id >= from_entry_id]
        if to_entry_id is not None:
            entries = [e for e in entries if e.id <= to_entry_id]
        logger.debug("tape.store.read_complete tape={} count={}", tape, len(entries))
        return entries

    def append(self, tape: str, entry: TapeEntry) -> None:
        """Append an entry to a tape (auto-creates tape if needed)."""
        logger.debug("tape.store.append tape={} kind={}", tape, entry.kind)
        self._make_tape_file(tape).append(entry)
        logger.debug("tape.store.append_complete tape={} kind={}", tape, entry.kind)

    def fork(
        self,
        from_tape: str,
        new_tape_id: str | None = None,
        from_entry: tuple[str, int] | None = None,
        from_anchor: str | None = None,
    ) -> str:
        """Fork a tape. Returns the new tape ID.

        Args:
            from_tape: Source tape ID
            new_tape_id: New tape ID (auto-generated if None)
            from_entry: Fork from (tape_id, entry_id) tuple - partial copy
            from_anchor: Fork from anchor name (resolves to entry_id)
        """
        logger.debug(
            "tape.store.fork from_tape={} new_tape={} from_entry={} from_anchor={}",
            from_tape,
            new_tape_id,
            from_entry,
            from_anchor,
        )
        manifest = self._load_manifest()
        if from_anchor is not None:
            anchor = manifest.get_anchor(from_anchor)
            if anchor is None:
                logger.error("tape.store.fork_anchor_not_found from_tape={} anchor={}", from_tape, from_anchor)
                raise ValueError(f"Anchor not found: {from_anchor}")
            from_entry = (anchor.tape_id, anchor.entry_id)
        elif from_entry is None:
            from_entry = (from_tape, 0)

        source_tape, source_entry_id = from_entry
        if new_tape_id is None:
            new_tape_id = f"{from_tape}__{uuid.uuid4().hex[:8]}"
        source_file = self._make_tape_file(source_tape)
        target_file = self._make_tape_file(new_tape_id)
        source_file.copy_to(target_file, from_entry_id=source_entry_id)
        # Use next_id as fork_start_id (where fork starts reading from target)
        fork_start_id = source_file._next_id()
        manifest.fork_tape(source_tape, new_tape_id, parent=(source_tape, fork_start_id))
        self.save_manifest(manifest)
        logger.info("tape.store.fork_complete from_tape={} new_tape={}", from_tape, new_tape_id)
        return new_tape_id

    def archive(self, tape_id: str) -> Path | None:
        """Archive a tape."""
        logger.debug("tape.store.archive tape_id={}", tape_id)
        tape_file = self._make_tape_file(tape_id)
        manifest = self._load_manifest()
        manifest.delete_tape(tape_id)
        self.save_manifest(manifest)
        result = tape_file.archive()
        logger.info("tape.store.archived tape_id={} path={}", tape_id, result)
        return result

    def reset(self, tape_id: str) -> None:
        """Reset (clear) a tape."""
        logger.debug("tape.store.reset tape_id={}", tape_id)
        self._make_tape_file(tape_id).reset()
        logger.info("tape.store.reset_complete tape_id={}", tape_id)

    # -------------------------------------------------------------------------
    # Anchor operations
    # -------------------------------------------------------------------------

    def create_anchor(self, name: str, tape_id: str, entry_id: int, state: dict[str, object] | None = None) -> None:
        """Create an anchor."""
        logger.debug("tape.store.create_anchor name={} tape_id={} entry_id={}", name, tape_id, entry_id)
        manifest = self._load_manifest()
        manifest.create_anchor(name, tape_id, entry_id, state)
        self.save_manifest(manifest)
        logger.info("tape.store.anchor_created name={} tape_id={} entry_id={}", name, tape_id, entry_id)

    def get_anchor(self, name: str) -> Anchor | None:
        """Get an anchor by name."""
        logger.debug("tape.store.get_anchor name={}", name)
        manifest = self._load_manifest()
        anchor = manifest.get_anchor(name)
        logger.debug("tape.store.get_anchor_result name={} found={}", name, anchor is not None)
        return anchor

    def update_anchor(self, name: str, entry_id: int | None = None, state: dict[str, object] | None = None) -> None:
        """Update an anchor."""
        logger.debug("tape.store.update_anchor name={} entry_id={}", name, entry_id)
        manifest = self._load_manifest()
        manifest.update_anchor(name, entry_id=entry_id, state=state)
        self.save_manifest(manifest)
        logger.info("tape.store.anchor_updated name={} entry_id={}", name, entry_id)

    def delete_anchor(self, name: str) -> None:
        """Delete an anchor."""
        logger.debug("tape.store.delete_anchor name={}", name)
        manifest = self._load_manifest()
        manifest.delete_anchor(name)
        self.save_manifest(manifest)
        logger.info("tape.store.anchor_deleted name={}", name)

    def list_anchors(self) -> list[Anchor]:
        """List all anchors."""
        logger.debug("tape.store.list_anchors")
        manifest = self._load_manifest()
        anchors = list(manifest.anchors.values())
        logger.debug("tape.store.list_anchors_result count={}", len(anchors))
        return anchors

    def resolve_anchor(self, name: str) -> int:
        """Resolve anchor name to entry ID."""
        logger.debug("tape.store.resolve_anchor name={}", name)
        manifest = self._load_manifest()
        result = manifest.resolve_anchor(name)
        logger.debug("tape.store.resolve_anchor_result name={} entry_id={}", name, result)
        return result

    # -------------------------------------------------------------------------
    # Internal methods
    # -------------------------------------------------------------------------

    def save_manifest(self, manifest: Manifest) -> None:
        """Save the manifest to disk."""
        path = self._paths.home / "manifest.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "tapes": {
                tape_id: {
                    "id": meta.id,
                    "file": meta.file,
                    "title": meta.title,
                    "parent": list(meta.parent) if meta.parent else None,
                    "created_at": meta.created_at.isoformat(),
                }
                for tape_id, meta in manifest.tapes.items()
            },
            "anchors": {
                name: {
                    "name": anchor.name,
                    "tape_id": anchor.tape_id,
                    "entry_id": anchor.entry_id,
                    "state": anchor.state,
                    "created_at": anchor.created_at.isoformat(),
                }
                for name, anchor in manifest.anchors.items()
            },
        }
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

    def _load_manifest(self) -> Manifest:
        """Load manifest from disk."""
        manifest = Manifest()
        path = self._paths.home / "manifest.json"
        if not path.exists():
            return manifest

        data = json.loads(path.read_text(encoding="utf-8"))
        for tape_id, meta in data.get("tapes", {}).items():
            parent_data = meta.get("parent")
            parent: tuple[str, int] | None = None
            if parent_data and isinstance(parent_data, list) and len(parent_data) == 2:
                parent = (parent_data[0], parent_data[1])
            elif meta.get("parent_id"):
                parent = (meta["parent_id"], meta.get("head_id", 0))
            meta_obj = TapeMeta(
                id=meta["id"],
                file=meta["file"],
                title=meta.get("title"),
                parent=parent,
                created_at=datetime.fromisoformat(meta["created_at"]) if meta.get("created_at") else datetime.now(UTC),
            )
            manifest._tapes[tape_id] = meta_obj

        for anchor_name, anchor in data.get("anchors", {}).items():
            anchor_obj = Anchor(
                name=anchor["name"],
                tape_id=anchor["tape_id"],
                entry_id=anchor["entry_id"],
                state=anchor.get("state", {}),
                created_at=datetime.fromisoformat(anchor["created_at"])
                if anchor.get("created_at")
                else datetime.now(UTC),
            )
            manifest._anchors[anchor_name] = anchor_obj

        return manifest

    def _make_tape_file(self, tape: str) -> TapeFile:
        """Create a new TapeFile for the given tape."""
        encoded_name = quote(tape, safe="")
        file_name = f"{self._paths.workspace_hash}__{encoded_name}{TAPE_FILE_SUFFIX}"
        return TapeFile(self._paths.tape_root / file_name)

    @staticmethod
    def _resolve_paths(home: Path, workspace_path: Path) -> TapePaths:
        tape_root = (home / "tapes").resolve()
        tape_root.mkdir(parents=True, exist_ok=True)
        workspace_hash = md5(str(workspace_path.resolve()).encode("utf-8")).hexdigest()  # noqa: S324
        return TapePaths(home=home, tape_root=tape_root, workspace_hash=workspace_hash)
