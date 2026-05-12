import asyncio
from collections import defaultdict
import contextlib
import contextvars
import hashlib
from collections.abc import AsyncGenerator
from typing import Any

from pydantic.dataclasses import dataclass
from republic import AsyncTapeStore, TapeEntry, TapeQuery
from republic.tape.context import TapeContext
from republic.tape.session import TapeSession
from republic.tape.store import InMemoryTapeStore

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


contextvar_session = contextvars.ContextVar[TapeSession | None]("session")


class TapeService:
    _store: AsyncTapeStore
    _framework: BubFramework
    _tape_locks: dict[str, asyncio.Lock]

    def __init__(self, store: AsyncTapeStore, framework: BubFramework) -> None:
        self._store = store
        self._framework = framework
        self._tape_locks = defaultdict(asyncio.Lock)

    @classmethod
    def from_framework(cls, framework: BubFramework) -> TapeService:
        store = framework.get_tape_store()
        if store is None:
            store = InMemoryTapeStore()
        return cls(store, framework)

    @contextlib.asynccontextmanager
    async def session(
        self, tape_name: str, *, wait: bool = True
    ) -> AsyncGenerator[TapeSession, None]:
        """Fork tape, create session, yield session without bootstrapping."""
        if not wait and self._tape_locks[tape_name].locked():
            raise RuntimeError(f"Tape {tape_name} is currently in use, cannot acquire session")
        async with self._tape_locks[tape_name]:
            async with self._mk_session(tape_name) as session:
                # ensure bootstrapped, and hook persisted if any
                await self._bootstrap(session)
            async with self._mk_session(tape_name) as session:
                token = contextvar_session.set(session)
                try:
                    yield session
                finally:
                    contextvar_session.reset(token)

    def _mk_session(self, tape_name):
        return TapeSession(
            name=tape_name,
            store=self._store,
            context=self._framework.build_tape_context(),
        )

    async def _bootstrap(self, session: TapeSession) -> None:
        """Create initial anchor if tape has none."""
        entries = await self._store.fetch_all(TapeQuery(tape=session.name).kinds("anchor").limit(1))
        if not entries:
            _ = session.handoff("session/start", anchor_state={"owner": "human"})

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
        async with self.session(tape_name, wait=False) as session:
            entries = await self._store.fetch_all(TapeQuery(tape=tape_name).kinds("anchor"))
            if not entries:
                _ = session.handoff("session/start", anchor_state={"owner": "human"})

    async def anchors(self, tape_name: str, limit: int = 20) -> list[AnchorSummary]:
        entries = list(await self._store.fetch_all(TapeQuery(tape=tape_name).kinds("anchor")))
        results: list[AnchorSummary] = []
        for entry in entries[-limit:]:
            name = str(entry.payload.get("name", "-"))
            state = entry.payload.get("state")
            state_dict: dict[str, object] = dict(state) if isinstance(state, dict) else {}
            results.append(AnchorSummary(name=name, state=state_dict))
        return results

    async def reset(self, tape_name: str):
        async with self._obtain_session(tape_name) as session:
            await self._store.reset(tape_name)
            # handoff deferred to session close, so the order is correct
            anchor_state = {"owner": "human"}
            _ = session.handoff("session/start", anchor_state=anchor_state)

    async def create(self, tape_name: str):
        async with self._obtain_session(tape_name) as session:
            if any(a.name == "session/start" for a in await self.anchors(tape_name)):
                raise Exception("Tape already exists")
            anchor_state = {"owner": "human"}
            _ = session.handoff("session/start", anchor_state=anchor_state)

    async def handoff(self, tape_name: str, *, name: str, anchor_state: dict[str, Any] | None = None) -> list[TapeEntry]:
        """
        Handoff append is deferred to session close
        """
        async with self._obtain_session(tape_name) as session:
            entries = session.handoff(name, anchor_state=anchor_state)
        return entries

    async def search(self, query: TapeQuery) -> list[TapeEntry]:
        return list(await self._store.fetch_all(query))

    async def append_entry(self, tape_name: str, entry: TapeEntry) -> None:
        """
        Entry append is deferred to session close
        """
        async with self._obtain_session(tape_name) as session:
            session.append_entry(entry)

    async def append_event(self, tape_name: str, name: str, payload: dict[str, Any], **meta: Any) -> None:
        """
        Event append is immediate
        """
        async with self._obtain_session(tape_name) as session:
            await session.append_event(name=name, data=payload, **meta)

    async def fork_tape(self, tape_name: str, target_name: str):
        """
        Fork the tape
        
        Fork is read only to the original tape
        """
        await self._store.fork_tape(source_name=tape_name, target_name=target_name)

    @contextlib.asynccontextmanager
    async def _obtain_session(self, tape_name: str) -> AsyncGenerator[TapeSession, None]:
        if (session := contextvar_session.get(None)) is not None and session.name == tape_name:
            yield session
        else:
            async with self.session(tape_name, wait=False) as session:
                yield session