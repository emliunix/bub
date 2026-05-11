import contextlib
import functools
import hashlib
import json
from collections.abc import AsyncGenerator
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, cast

from pydantic.dataclasses import dataclass
from republic import AsyncTapeManager, AsyncTapeStore, TapeEntry, TapeQuery
from republic.tape.session import TapeSession
from republic.tape.store import InMemoryTapeStore

from bub.builtin.store import ForkTapeStore
from bub.framework import BubFramework



def session_tape_name(session_id: str, workspace: str) -> str:
    workspace_hash = hashlib.md5(workspace.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]
    tape_name = (
        workspace_hash + "__" + hashlib.md5(session_id.encode("utf-8"), usedforsecurity=False).hexdigest()[:16]
    )
    return tape_name


def get_tape_name(state: dict[str, Any]) -> str:
    tape_name = state.get("tape_name")
    if tape_name is None:
        session_id = state.get("session_id")
        workspace = state.get("_runtime_workspace")
        if session_id is None or workspace is None:
            raise RuntimeError("no tape found in state and cannot be derived")
        tape_name = session_tape_name(session_id, workspace)
    return tape_name


@dataclass(frozen=True)
class TapeInfo:
    """Runtime tape info summary."""

    name: str
    entries: int
    anchors: int
    last_anchor: str | None
    entries_since_last_anchor: int
    last_token_usage: int | None


@dataclass(frozen=True)
class AnchorSummary:
    """Rendered anchor summary."""

    name: str
    state: dict[str, object]


class TapeService:
    def __init__(self, store: ForkTapeStore, archive_path: Path, framework: BubFramework) -> None:
        self._store = store
        self._archive_path = archive_path
        self._framework = framework

    @classmethod
    def from_framework(cls, framework: BubFramework) -> TapeService:
        import bub
        store = framework.get_tape_store()
        if store is None:
            store = InMemoryTapeStore()
        return cls(ForkTapeStore(store), bub.home / "tapes", framework)

    @functools.cached_property
    def _tape_mgr(self) -> AsyncTapeManager:
        ctx = self._framework.build_tape_context()
        return AsyncTapeManager(store=self._store, default_context=ctx)

    @contextlib.asynccontextmanager
    async def session(
        self, tape_name: str, *, merge_back: bool = True,
    ) -> AsyncGenerator[TapeSession, None]:
        """Fork tape, create session, bootstrap anchor, yield session."""
        async with self._store.fork(tape_name, merge_back=merge_back):
            async with self._tape_mgr.session(tape_name) as session:
                await self._bootstrap(session)
                yield session

    async def _bootstrap(self, session: TapeSession) -> None:
        """Create initial anchor if tape has none."""
        entries = await self._store.fetch_all(TapeQuery(tape=session.name))
        if not any(e.kind == "anchor" for e in entries):
            await session.handoff("session/start", anchor_state={"owner": "human"})

    async def info(self, tape_name: str) -> TapeInfo:
        entries = list(await self._store.fetch_all(TapeQuery(tape=tape_name)))
        anchors = [(i, entry) for i, entry in enumerate(entries) if entry.kind == "anchor"]
        if anchors:
            last_anchor = anchors[-1][1].payload.get("name")
            entries_since_last_anchor = len(entries) - anchors[-1][0] - 1
        else:
            last_anchor = None
            entries_since_last_anchor = len(entries)
        last_token_usage: int | None = None
        for entry in reversed(entries):
            if entry.kind == "event" and entry.payload.get("name") == "run":
                with contextlib.suppress(AttributeError):
                    token_usage = entry.payload.get("data", {}).get("usage", {}).get("total_tokens")
                    if token_usage and isinstance(token_usage, int):
                        last_token_usage = token_usage
                        break
        return TapeInfo(
            name=tape_name,
            entries=len(entries),
            anchors=len(anchors),
            last_anchor=str(last_anchor) if last_anchor else None,
            entries_since_last_anchor=entries_since_last_anchor,
            last_token_usage=last_token_usage,
        )

    async def ensure_bootstrap_anchor(self, tape_name: str) -> None:
        entries = await self._store.fetch_all(TapeQuery(tape=tape_name).kinds("anchor"))
        if not entries:
            _ = await self._tape_mgr.handoff(tape_name, "session/start", anchor_state={"owner": "human"})

    async def anchors(self, tape_name: str, limit: int = 20) -> list[AnchorSummary]:
        entries = list(await self._store.fetch_all(TapeQuery(tape=tape_name).kinds("anchor")))
        results: list[AnchorSummary] = []
        for entry in entries[-limit:]:
            name = str(entry.payload.get("name", "-"))
            state = entry.payload.get("state")
            state_dict: dict[str, object] = dict(state) if isinstance(state, dict) else {}
            results.append(AnchorSummary(name=name, state=state_dict))
        return results

    async def _archive(self, tape_name: str) -> Path:
        stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        self._archive_path.mkdir(parents=True, exist_ok=True)
        archive_path = self._archive_path / f"{tape_name}.jsonl.{stamp}.bak"
        with archive_path.open("w", encoding="utf-8") as f:
            for entry in await self._store.fetch_all(TapeQuery(tape=tape_name)):
                f.write(json.dumps(asdict(entry), ensure_ascii=False) + "\n")
        return archive_path

    async def reset(self, tape_name: str, *, archive: bool = False) -> str:
        archive_path: Path | None = None
        if archive:
            archive_path = await self._archive(tape_name)
        await self._store.reset(tape_name)
        anchor_state = {"owner": "human"}
        if archive_path is not None:
            anchor_state["archived"] = str(archive_path)
        _ = await self._tape_mgr.handoff(tape_name, "session/start", anchor_state=anchor_state)
        return f"Archived: {archive_path}" if archive_path else "ok"

    async def handoff(self, tape_name: str, *, name: str, anchor_state: dict[str, Any] | None = None) -> list[TapeEntry]:
        entries = await self._tape_mgr.handoff(tape_name, name, anchor_state=anchor_state)
        return entries

    async def search(self, query: TapeQuery) -> list[TapeEntry]:
        return list(await self._store.fetch_all(query))

    async def append_event(self, tape_name: str, name: str, payload: dict[str, Any], **meta: Any) -> None:
        await self._tape_mgr.append_entry(tape_name, TapeEntry.event(name=name, data=payload, **meta))

    @contextlib.asynccontextmanager
    async def fork_tape(self, tape_name: str, merge_back: bool = True) -> AsyncGenerator[None, None]:
        async with self._store.fork(tape_name, merge_back=merge_back):
            yield
