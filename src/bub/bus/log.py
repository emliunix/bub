"""Async activity logging with SQLAlchemy.

Provides queue-based async logging to SQLite using SQLAlchemy ORM.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from loguru import logger
from sqlalchemy import Engine, Index, Text, create_engine, event
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column, sessionmaker


class Base(DeclarativeBase):
    """Base class for SQLAlchemy models."""


class ActivityLogEntry(Base):
    """Activity log entry model."""

    __tablename__ = "activity_log"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ts: Mapped[str] = mapped_column(Text, nullable=False)
    event: Mapped[str] = mapped_column(Text, nullable=False)
    message_id: Mapped[str] = mapped_column(Text, nullable=False)
    rpc_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    actor: Mapped[str | None] = mapped_column(Text, nullable=True)
    to_address: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str | None] = mapped_column(Text, nullable=True)
    payload_json: Mapped[str] = mapped_column(Text, nullable=False, default="{}")
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


# Create indexes
Index("idx_activity_message_id", ActivityLogEntry.message_id)
Index("idx_activity_ts", ActivityLogEntry.ts)


@dataclass
class LogEntry:
    """Log entry dataclass for queue operations."""

    ts: str
    event: str
    message_id: str
    rpc_id: str | None
    actor: str | None
    to_address: str | None
    status: str | None
    payload_json: str
    error: str | None


class ActivityLogWriter:
    """Async append-only activity logger using SQLAlchemy.

    Uses an async queue to separate log submission from database writes.
    Database operations run in a background thread to avoid blocking the event loop.
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._engine: Engine | None = None
        self._session_factory: sessionmaker[Session] | None = None
        self._queue: asyncio.Queue[LogEntry | None] = asyncio.Queue()
        self._worker: asyncio.Task[None] | None = None
        self._stop_event = asyncio.Event()

    async def start(self) -> None:
        """Initialize database and start background worker."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize SQLAlchemy engine in thread
        def _init_engine():

            engine: Engine = create_engine(f"sqlite:///{self._db_path}", echo=False)
            return engine

        # Enable WAL mode for better concurrency
        def _enable_wal(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

        engine_result = await asyncio.to_thread(_init_engine)
        if engine_result is None:
            raise RuntimeError("Failed to initialize database engine")
        self._engine = engine_result
        event.listen(self._engine, "connect", _enable_wal)
        self._session_factory = sessionmaker(bind=self._engine)

        # Create tables
        await asyncio.to_thread(Base.metadata.create_all, self._engine)

        # Start background worker
        self._worker = asyncio.create_task(self._run())
        logger.debug("activity_log.writer.started db_path={}", self._db_path)

    async def stop(self) -> None:
        """Stop background worker and close database."""
        if self._worker is None:
            return

        # Signal worker to stop
        await self._queue.put(None)

        # Wait for worker to finish
        try:
            await asyncio.wait_for(self._worker, timeout=5.0)
        except asyncio.TimeoutError:
            logger.warning("activity_log.worker.stop_timeout")
            self._worker.cancel()
            try:
                await self._worker
            except asyncio.CancelledError:
                pass

        self._worker = None

        # Close engine
        if self._engine:
            await asyncio.to_thread(self._engine.dispose)
            self._engine = None

        logger.debug("activity_log.writer.stopped")

    async def log(
        self,
        *,
        event: str,
        message_id: str,
        rpc_id: str | None = None,
        actor: str | None = None,
        to: str | None = None,
        status: str | None = None,
        payload: dict[str, object] | None = None,
        error: str | None = None,
    ) -> None:
        """Queue a log entry for async writing."""
        entry = LogEntry(
            ts=datetime.now(UTC).isoformat(),
            event=event,
            message_id=message_id,
            rpc_id=rpc_id,
            actor=actor,
            to_address=to,
            status=status,
            payload_json=json.dumps(payload or {}, ensure_ascii=False),
            error=error,
        )
        await self._queue.put(entry)

    async def _run(self) -> None:
        """Background worker that batches and writes log entries."""
        batch: list[LogEntry] = []
        batch_timeout = 0.1  # Flush batch after 100ms

        while not self._stop_event.is_set():
            try:
                # Wait for entry with timeout for batching
                entry = await asyncio.wait_for(
                    self._queue.get(),
                    timeout=batch_timeout if batch else None,
                )

                if entry is None:
                    # Stop signal
                    if batch:
                        await self._write_batch(batch)
                    break

                batch.append(entry)

                # Flush batch when it reaches size limit
                if len(batch) >= 10:
                    await self._write_batch(batch)
                    batch = []

            except asyncio.TimeoutError:
                # Timeout reached, flush pending batch
                if batch:
                    await self._write_batch(batch)
                    batch = []

        # Flush any remaining entries
        if batch:
            await self._write_batch(batch)

    async def _write_batch(self, entries: list[LogEntry]) -> None:
        """Write a batch of entries to the database."""
        if self._session_factory is None:
            logger.error("activity_log.session_factory_not_initialized")
            return

        factory = self._session_factory

        def _insert():
            with factory() as session:
                try:
                    for entry in entries:
                        log_entry = ActivityLogEntry(
                            ts=entry.ts,
                            event=entry.event,
                            message_id=entry.message_id,
                            rpc_id=entry.rpc_id,
                            actor=entry.actor,
                            to_address=entry.to_address,
                            status=entry.status,
                            payload_json=entry.payload_json,
                            error=entry.error,
                        )
                        session.add(log_entry)
                    session.commit()
                except Exception:
                    session.rollback()
                    raise

        try:
            await asyncio.to_thread(_insert)
            logger.debug("activity_log.batch_written count={}", len(entries))
        except Exception as e:
            logger.exception("activity_log.batch_write_failed count={} error={}", len(entries), e)


__all__ = ["ActivityLogWriter", "ActivityLogEntry", "LogEntry"]
