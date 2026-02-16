"""Tape server - FastAPI REST API for tape operations."""

from __future__ import annotations

from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from loguru import logger
from pydantic import BaseModel
from uvicorn import Config, Server

from bub.config.settings import TapeSettings
from bub.tape.store import FileTapeStore


class TapeEntryIn(BaseModel):
    """Incoming tape entry."""

    kind: str
    payload: dict[str, Any]
    meta: dict[str, Any] = {}


class TapeEntryOut(BaseModel):
    """Outgoing tape entry."""

    id: int
    kind: str
    payload: dict[str, Any]
    meta: dict[str, Any]


class CreateTapeRequest(BaseModel):
    """Request to create a new tape."""

    tape_id: str
    title: str | None = None


class ForkRequest(BaseModel):
    """Request to fork a tape."""

    new_tape_id: str | None = None
    from_entry_id: int | None = None
    from_anchor: str | None = None


class CreateAnchorRequest(BaseModel):
    """Request to create an anchor."""

    name: str
    tape_id: str
    entry_id: int
    state: dict[str, Any] | None = None


class TapeListResponse(BaseModel):
    """Response for listing tapes."""

    tapes: list[str]


class EntriesResponse(BaseModel):
    """Response for reading entries."""

    tape_id: str
    entries: list[dict[str, Any]]
    total: int
    from_entry_id: int | None = None
    to_entry_id: int | None = None


class AppendResponse(BaseModel):
    """Response for appending an entry."""

    id: int
    kind: str
    status: str


class AnchorResponse(BaseModel):
    """Response for anchor operations."""

    name: str
    tape_id: str
    entry_id: int
    state: dict[str, Any] | None


class AnchorsResponse(BaseModel):
    """Response for listing anchors."""

    anchors: list[dict[str, Any]]


class ForkResponse(BaseModel):
    """Response for forking a tape."""

    id: str
    from_entry_id: int


_store: Any = None


def get_store() -> Any:
    """Get the tape store instance."""
    global _store
    if _store is None:
        raise HTTPException(status_code=500, detail="Tape store not initialized")
    return _store


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup/shutdown."""
    global _store
    logger.info("Starting tape server...")
    yield
    logger.info("Stopping tape server...")


def create_app(tape_store: Any) -> FastAPI:
    """Create FastAPI app with tape store."""
    global _store
    _store = tape_store

    app = FastAPI(
        title="Bub Tape Server",
        description="REST API for tape operations",
        version="1.0.0",
        lifespan=lifespan,
    )

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    @app.get("/tapes", response_model=TapeListResponse)
    async def list_tapes():
        store = get_store()
        tapes = store.list_tapes()
        return TapeListResponse(tapes=tapes)

    @app.post("/tapes", response_model=dict)
    async def create_tape(req: CreateTapeRequest):
        store = get_store()
        store.create_tape(req.tape_id, title=req.title)
        return {"tape_id": req.tape_id, "status": "created"}

    @app.get("/tapes/{tape_id}", response_model=dict)
    async def get_tape(tape_id: str):
        store = get_store()
        title = store.get_title(tape_id)
        if title is None:
            raise HTTPException(status_code=404, detail="Tape not found")
        return {"tape_id": tape_id, "title": title}

    @app.get("/tapes/{tape_id}/entries", response_model=EntriesResponse)
    async def read_entries(
        tape_id: str,
        from_entry_id: int | None = None,
        to_entry_id: int | None = None,
    ):
        store = get_store()
        entries = store.read(tape_id, from_entry_id=from_entry_id, to_entry_id=to_entry_id)
        if entries is None:
            raise HTTPException(status_code=404, detail="Tape not found")
        return EntriesResponse(
            tape_id=tape_id,
            entries=[_entry_to_dict(e) for e in entries],
            total=len(entries),
            from_entry_id=from_entry_id,
            to_entry_id=to_entry_id,
        )

    @app.post("/tapes/{tape_id}/entries", response_model=AppendResponse)
    async def append_entry(tape_id: str, entry: TapeEntryIn):
        store = get_store()

        tape_entry = _entry_from_dict(entry.model_dump())
        store.append(tape_id, tape_entry)
        return AppendResponse(
            id=tape_entry.id,
            kind=tape_entry.kind,
            status="appended",
        )

    @app.post("/tapes/{tape_id}/fork", response_model=ForkResponse)
    async def fork_tape(tape_id: str, req: ForkRequest):
        store = get_store()
        new_tape_id = store.fork(
            tape_id,
            new_tape_id=req.new_tape_id,
            from_entry=(tape_id, req.from_entry_id) if req.from_entry_id else None,
            from_anchor=req.from_anchor,
        )
        return ForkResponse(id=new_tape_id, from_entry_id=req.from_entry_id or 0)

    @app.post("/tapes/{tape_id}/archive", response_model=dict)
    async def archive_tape(tape_id: str):
        store = get_store()
        archive_path = store.archive(tape_id)
        return {"tape_id": tape_id, "archived": str(archive_path) if archive_path else None}

    @app.post("/tapes/{tape_id}/reset", response_model=dict)
    async def reset_tape(tape_id: str):
        store = get_store()
        store.reset(tape_id)
        return {"tape_id": tape_id, "status": "reset"}

    @app.post("/anchors", response_model=dict)
    async def create_anchor(req: CreateAnchorRequest):
        store = get_store()
        store.create_anchor(req.name, req.tape_id, req.entry_id, req.state)
        return {"name": req.name, "status": "created"}

    @app.get("/anchors/{name}", response_model=AnchorResponse)
    async def get_anchor(name: str):
        store = get_store()
        anchor = store.get_anchor(name)
        if anchor is None:
            raise HTTPException(status_code=404, detail="Anchor not found")
        return AnchorResponse(
            name=anchor.name,
            tape_id=anchor.tape_id,
            entry_id=anchor.entry_id,
            state=anchor.state,
        )

    @app.get("/anchors", response_model=AnchorsResponse)
    async def list_anchors():
        store = get_store()
        anchors = store.list_anchors()
        return AnchorsResponse(
            anchors=[
                {
                    "name": a.name,
                    "tape_id": a.tape_id,
                    "entry_id": a.entry_id,
                    "state": a.state,
                }
                for a in anchors
            ]
        )

    return app


def _entry_to_dict(entry: Any) -> dict[str, Any]:
    """Convert TapeEntry to dict for JSON serialization."""
    return {
        "id": entry.id,
        "kind": entry.kind,
        "payload": entry.payload,
        "meta": getattr(entry, "meta", {}),
    }


def _entry_from_dict(data: dict[str, Any]) -> Any:
    """Create TapeEntry from dict."""
    from republic.tape import TapeEntry

    kind = data.get("kind", "message")
    payload = data.get("payload", {})

    if kind == "anchor":
        return TapeEntry.anchor(name=payload.get("name", ""), state=payload.get("state"))
    elif kind == "event":
        return TapeEntry.event(name=payload.get("name", ""), data=payload.get("data", {}))
    elif kind == "system":
        return TapeEntry.system(content=payload.get("content", ""))
    elif kind == "tool_call":
        return TapeEntry.tool_call(payload.get("calls", []))
    elif kind == "tool_result":
        return TapeEntry.tool_result(payload.get("results", []))
    else:
        return TapeEntry.message(payload)


class TapeServer:
    """Tape server that wraps FileTapeStore with REST API."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 7890,
        tape_store: Any = None,
    ) -> None:
        self.host = host
        self.port = port
        self._store = tape_store
        self._server: Server | None = None
        self._app: FastAPI | None = None

    def start(self, tape_settings: TapeSettings, workspace: Path) -> None:
        """Start the tape server."""
        if self._store is None:
            self._store = FileTapeStore(tape_settings.resolve_home(), workspace)

        self._app = create_app(self._store)
        config = Config(
            self._app,
            host=self.host,
            port=self.port,
            log_level="info",
        )
        self._server = Server(config)

        tape_home = tape_settings.resolve_home()
        logger.info(
            "tape.serve host={} port={} workspace={} home={}",
            self.host,
            self.port,
            str(workspace),
            str(tape_home),
        )
        self._server.run()

    def stop(self) -> None:
        """Stop the tape server."""
        if self._server:
            self._server.should_exit = True


if __name__ == "__main__":
    import sys

    host = sys.argv[1] if len(sys.argv) > 1 else "localhost"
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 7890

    server = TapeServer(host=host, port=port)
    from bub.config import Settings

    settings = Settings()
    server.start(settings, Path.cwd())
