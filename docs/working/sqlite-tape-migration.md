# SQLite Tape Migration Implementation Plan

## 1. Overview

The current FileTapeStore implementation uses JSONL files for tape storage, which served us well for initial development but now presents limitations as the system scales. This migration moves tape storage to SQLite with SQLAlchemy ORM and Alembic migrations, providing a robust foundation for future growth.

The primary architectural shift is the introduction of **immutable tape IDs with mutable name aliases**. Currently, tape names serve as both identifier and display label, making renaming impossible without breaking references. The new design separates these concerns: each tape receives a permanent UUID that never changes, while names become mutable aliases that can be reassigned. This enables powerful features like tape resets (create new tape, transfer name) while preserving history, and allows users to rename tapes without invalidating existing references.

SQLite was chosen over alternatives for several compelling reasons. It requires no separate server process, simplifying deployment and operations. The embedded nature means zero network overhead for queries. ACID compliance provides reliability guarantees that JSONL cannot offer. Most importantly, SQLite's FTS5 extension enables full-text search across tape entries without external dependencies like Elasticsearch. Combined with proper indexing, query performance for large tapes will significantly exceed the current linear JSONL scanning approach.

## 2. Schema Design

### Core Tables

```sql
-- Tapes table: immutable tape records
CREATE TABLE tapes (
    id UUID PRIMARY KEY,                    -- Immutable tape identifier
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    archived_at TIMESTAMP,                   -- NULL = active, set = archived
    parent_tape_id UUID REFERENCES tapes(id) -- For forked tapes
);

-- Tape aliases: mutable name→id mappings
CREATE TABLE tape_aliases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL UNIQUE,       -- The alias/name
    tape_id UUID NOT NULL REFERENCES tapes(id),
    is_primary BOOLEAN NOT NULL DEFAULT 0,   -- Only one primary per tape
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(tape_id, is_primary) WHERE is_primary = 1
);

-- Tape entries: the actual message data
CREATE TABLE tape_entries (
    tape_id UUID NOT NULL REFERENCES tapes(id),
    id INTEGER NOT NULL,                     -- Sequential within tape
    kind VARCHAR(50) NOT NULL,               -- Message type
    payload JSON NOT NULL,                   -- Message content
    meta JSON,                               -- Optional metadata
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    PRIMARY KEY (tape_id, id)
);

-- Anchors: named positions in tapes
CREATE TABLE anchors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(255) NOT NULL,
    tape_id UUID NOT NULL REFERENCES tapes(id),
    entry_id INTEGER NOT NULL,               -- References tape_entries.id
    state JSON,                              -- Snapshot state at anchor
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    
    UNIQUE(name, tape_id)
);

-- FTS5 virtual table for full-text search
CREATE VIRTUAL TABLE tape_entries_fts USING fts5(
    content,                                 -- Searchable text content
    tape_id,                                 -- For filtering by tape
    entry_id,                                -- For joining back to entries
    content='tape_entries',                  -- External content table
    content_rowid='rowid'
);

-- Triggers to keep FTS index in sync
CREATE TRIGGER tape_entries_ai AFTER INSERT ON tape_entries BEGIN
    INSERT INTO tape_entries_fts(rowid, content, tape_id, entry_id)
    VALUES (new.rowid, json_extract(new.payload, '$.content'), new.tape_id, new.id);
END;

CREATE TRIGGER tape_entries_ad AFTER DELETE ON tape_entries BEGIN
    INSERT INTO tape_entries_fts(tape_entries_fts, rowid, content, tape_id, entry_id)
    VALUES ('delete', old.rowid, json_extract(old.payload, '$.content'), old.tape_id, old.id);
END;

CREATE TRIGGER tape_entries_au AFTER UPDATE ON tape_entries BEGIN
    INSERT INTO tape_entries_fts(tape_entries_fts, rowid, content, tape_id, entry_id)
    VALUES ('delete', old.rowid, json_extract(old.payload, '$.content'), old.tape_id, old.id);
    INSERT INTO tape_entries_fts(rowid, content, tape_id, entry_id)
    VALUES (new.rowid, json_extract(new.payload, '$.content'), new.tape_id, new.id);
END;
```

### Indexes for Performance

```sql
-- For tape lookup by alias
CREATE INDEX idx_tape_aliases_tape_id ON tape_aliases(tape_id);

-- For entry range queries (pagination, anchor traversal)
CREATE INDEX idx_tape_entries_tape_created ON tape_entries(tape_id, created_at);

-- For anchor lookups
CREATE INDEX idx_anchors_tape_entry ON anchors(tape_id, entry_id);
CREATE INDEX idx_anchors_name ON anchors(name);

-- For parent tape queries (fork history)
CREATE INDEX idx_tapes_parent ON tapes(parent_tape_id);
```

## 3. SQLAlchemy Models

```python
# src/bub/tape/models.py
from __future__ import annotations

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    JSON, Boolean, Column, DateTime, ForeignKey, Integer, String,
    UniqueConstraint, create_engine, event
)
from sqlalchemy.orm import DeclarativeBase, relationship, sessionmaker
from sqlalchemy.dialects.sqlite import UUID

if TYPE_CHECKING:
    from collections.abc import Sequence


class Base(DeclarativeBase):
    pass


class Tape(Base):
    """Immutable tape entity with UUID primary key."""
    
    __tablename__ = "tapes"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        primary_key=True, 
        default=uuid.uuid4
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        nullable=False
    )
    archived_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    parent_tape_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("tapes.id"), 
        nullable=True
    )
    
    # Relationships
    aliases: Mapped[list[TapeAlias]] = relationship(
        "TapeAlias", 
        back_populates="tape",
        cascade="all, delete-orphan"
    )
    entries: Mapped[list[TapeEntry]] = relationship(
        "TapeEntry", 
        back_populates="tape",
        cascade="all, delete-orphan",
        order_by="TapeEntry.id"
    )
    anchors: Mapped[list[Anchor]] = relationship(
        "Anchor", 
        back_populates="tape",
        cascade="all, delete-orphan"
    )
    parent: Mapped[Tape | None] = relationship(
        "Tape", 
        remote_side=[id], 
        backref="forks"
    )
    
    @property
    def primary_alias(self) -> str | None:
        """Get the primary (current) name of this tape."""
        for alias in self.aliases:
            if alias.is_primary:
                return alias.name
        return None
    
    @property
    def is_archived(self) -> bool:
        return self.archived_at is not None


class TapeAlias(Base):
    """Mutable name alias for a tape. Only one primary alias per tape."""
    
    __tablename__ = "tape_aliases"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    tape_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("tapes.id"), 
        nullable=False
    )
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        nullable=False
    )
    
    tape: Mapped[Tape] = relationship("Tape", back_populates="aliases")
    
    __table_args__ = (
        UniqueConstraint(
            'tape_id', 
            'is_primary', 
            name='uq_primary_per_tape',
            sqlite_where=(is_primary == True)
        ),
    )


class TapeEntry(Base):
    """Individual entry in a tape with composite primary key."""
    
    __tablename__ = "tape_entries"
    
    tape_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("tapes.id"), 
        primary_key=True
    )
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    kind: Mapped[str] = mapped_column(String(50), nullable=False)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    meta: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        nullable=False
    )
    
    tape: Mapped[Tape] = relationship("Tape", back_populates="entries")


class Anchor(Base):
    """Named position in a tape with optional state snapshot."""
    
    __tablename__ = "anchors"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tape_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), 
        ForeignKey("tapes.id"), 
        nullable=False
    )
    entry_id: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=datetime.utcnow, 
        nullable=False
    )
    
    tape: Mapped[Tape] = relationship("Tape", back_populates="anchors")
    
    __table_args__ = (
        UniqueConstraint('name', 'tape_id', name='uq_anchor_name_per_tape'),
    )
```

## 4. SQLiteTapeStore Implementation

```python
# src/bub/tape/sqlite_store.py
from __future__ import annotations

import uuid
from collections.abc import Iterator, Sequence
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Any

from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from bub.tape.models import Anchor, Base, Tape, TapeAlias, TapeEntry
from bub.tape.store import TapeStore

if TYPE_CHECKING:
    from bub.tape.types import TapeEntry as TapeEntryType


class SQLiteTapeStore(TapeStore):
    """SQLite-backed tape store with FTS5 search."""
    
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            connect_args={"check_same_thread": False}
        )
        self.Session = sessionmaker(bind=self.engine)
        self._ensure_schema()
    
    def _ensure_schema(self) -> None:
        """Create tables if they don't exist."""
        Base.metadata.create_all(self.engine)
    
    @contextmanager
    def _session(self) -> Iterator[Session]:
        """Context manager for database sessions."""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    def create_tape(self, name: str | None = None, title: str | None = None) -> str:
        """Create a new tape. Returns the immutable UUID.
        
        If name is provided, creates a primary alias.
        If title is provided, stores it in tape meta.
        """
        with self._session() as session:
            tape = Tape()
            if title:
                # Store title as initial meta
                tape.meta = {"title": title}
            
            session.add(tape)
            session.flush()  # Get the ID
            
            if name:
                alias = TapeAlias(
                    name=name,
                    tape_id=tape.id,
                    is_primary=True
                )
                session.add(alias)
            
            return str(tape.id)
    
    def resolve_name(self, name: str) -> str | None:
        """Resolve a name/alias to a tape UUID. Returns None if not found."""
        with self._session() as session:
            alias = session.scalar(
                select(TapeAlias).where(TapeAlias.name == name)
            )
            return str(alias.tape_id) if alias else None
    
    def register_alias(self, name: str, tape_id: str, primary: bool = True) -> None:
        """Register a new alias for a tape.
        
        If primary=True, marks this as the primary alias and demotes any existing primary.
        """
        tape_uuid = uuid.UUID(tape_id)
        
        with self._session() as session:
            if primary:
                # Demote existing primary
                session.execute(
                    text("""
                        UPDATE tape_aliases 
                        SET is_primary = 0 
                        WHERE tape_id = :tape_id AND is_primary = 1
                    """),
                    {"tape_id": tape_uuid}
                )
            
            alias = TapeAlias(
                name=name,
                tape_id=tape_uuid,
                is_primary=primary
            )
            session.add(alias)
    
    def append(self, tape_id: str, entry: TapeEntryType) -> int:
        """Append an entry to a tape. Returns the entry ID."""
        tape_uuid = uuid.UUID(tape_id)
        
        with self._session() as session:
            # Get next entry ID
            result = session.scalar(
                select(func.max(TapeEntry.id)).where(TapeEntry.tape_id == tape_uuid)
            )
            next_id = (result or 0) + 1
            
            db_entry = TapeEntry(
                tape_id=tape_uuid,
                id=next_id,
                kind=entry.kind,
                payload=entry.payload,
                meta=entry.meta
            )
            session.add(db_entry)
            
            return next_id
    
    def read(
        self, 
        tape_id: str, 
        from_entry: int = 0, 
        to_entry: int | None = None
    ) -> list[TapeEntryType]:
        """Read entries from a tape, optionally within a range."""
        tape_uuid = uuid.UUID(tape_id)
        
        with self._session() as session:
            query = select(TapeEntry).where(
                TapeEntry.tape_id == tape_uuid,
                TapeEntry.id >= from_entry
            ).order_by(TapeEntry.id)
            
            if to_entry is not None:
                query = query.where(TapeEntry.id <= to_entry)
            
            entries = session.scalars(query).all()
            
            return [
                TapeEntryType(
                    id=e.id,
                    kind=e.kind,
                    payload=e.payload,
                    meta=e.meta,
                    created_at=e.created_at
                )
                for e in entries
            ]
    
    def fork(
        self, 
        from_tape: str, 
        new_tape_name: str, 
        from_anchor: str | None = None
    ) -> str:
        """Fork a tape at a specific anchor or the end.
        
        Returns the new tape's UUID.
        """
        from_uuid = uuid.UUID(from_tape)
        
        with self._session() as session:
            # Determine entry cutoff
            if from_anchor:
                anchor = session.scalar(
                    select(Anchor).where(
                        Anchor.tape_id == from_uuid,
                        Anchor.name == from_anchor
                    )
                )
                if not anchor:
                    raise ValueError(f"Anchor '{from_anchor}' not found")
                entry_cutoff = anchor.entry_id
            else:
                entry_cutoff = session.scalar(
                    select(func.max(TapeEntry.id)).where(TapeEntry.tape_id == from_uuid)
                ) or 0
            
            # Create new tape with parent reference
            new_tape = Tape(parent_tape_id=from_uuid)
            session.add(new_tape)
            session.flush()
            
            # Copy entries up to cutoff
            entries = session.scalars(
                select(TapeEntry).where(
                    TapeEntry.tape_id == from_uuid,
                    TapeEntry.id <= entry_cutoff
                )
            ).all()
            
            for entry in entries:
                new_entry = TapeEntry(
                    tape_id=new_tape.id,
                    id=entry.id,
                    kind=entry.kind,
                    payload=entry.payload.copy(),
                    meta=entry.meta.copy() if entry.meta else None
                )
                session.add(new_entry)
            
            # Register primary alias
            alias = TapeAlias(
                name=new_tape_name,
                tape_id=new_tape.id,
                is_primary=True
            )
            session.add(alias)
            
            return str(new_tape.id)
    
    def reset(self, tape_id: str) -> str:
        """Reset a tape: create new empty tape, transfer primary alias.
        
        Returns the new tape's UUID. Old tape is archived but preserved.
        """
        old_uuid = uuid.UUID(tape_id)
        
        with self._session() as session:
            # Get primary alias
            old_alias = session.scalar(
                select(TapeAlias).where(
                    TapeAlias.tape_id == old_uuid,
                    TapeAlias.is_primary == True
                )
            )
            
            if not old_alias:
                raise ValueError(f"No primary alias found for tape {tape_id}")
            
            name = old_alias.name
            
            # Archive old tape
            old_tape = session.get(Tape, old_uuid)
            if old_tape:
                from datetime import datetime
                old_tape.archived_at = datetime.utcnow()
            
            # Create new tape
            new_tape = Tape(parent_tape_id=old_uuid)
            session.add(new_tape)
            session.flush()
            
            # Transfer primary alias to new tape
            old_alias.is_primary = False
            new_alias = TapeAlias(
                name=name,
                tape_id=new_tape.id,
                is_primary=True
            )
            session.add(new_alias)
            
            return str(new_tape.id)
    
    def search(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """Search entries using FTS5. Returns list of matches with context."""
        with self._session() as session:
            # FTS5 query with snippet for context
            results = session.execute(
                text("""
                    SELECT 
                        e.tape_id,
                        e.id as entry_id,
                        e.kind,
                        snippet(tape_entries_fts, 0, '[', ']', '...', 32) as snippet,
                        rank
                    FROM tape_entries_fts
                    JOIN tape_entries e ON 
                        tape_entries_fts.tape_id = e.tape_id 
                        AND tape_entries_fts.entry_id = e.id
                    WHERE tape_entries_fts MATCH :query
                    ORDER BY rank
                    LIMIT :limit
                """),
                {"query": query, "limit": limit}
            ).fetchall()
            
            return [
                {
                    "tape_id": str(row.tape_id),
                    "entry_id": row.entry_id,
                    "kind": row.kind,
                    "snippet": row.snippet,
                    "rank": row.rank
                }
                for row in results
            ]
    
    def between_anchors(
        self, 
        tape_id: str, 
        start: str, 
        end: str
    ) -> list[TapeEntryType]:
        """Get all entries between two anchors (inclusive)."""
        tape_uuid = uuid.UUID(tape_id)
        
        with self._session() as session:
            start_anchor = session.scalar(
                select(Anchor).where(
                    Anchor.tape_id == tape_uuid,
                    Anchor.name == start
                )
            )
            end_anchor = session.scalar(
                select(Anchor).where(
                    Anchor.tape_id == tape_uuid,
                    Anchor.name == end
                )
            )
            
            if not start_anchor:
                raise ValueError(f"Start anchor '{start}' not found")
            if not end_anchor:
                raise ValueError(f"End anchor '{end}' not found")
            
            entries = session.scalars(
                select(TapeEntry).where(
                    TapeEntry.tape_id == tape_uuid,
                    TapeEntry.id >= start_anchor.entry_id,
                    TapeEntry.id <= end_anchor.entry_id
                ).order_by(TapeEntry.id)
            ).all()
            
            return [
                TapeEntryType(
                    id=e.id,
                    kind=e.kind,
                    payload=e.payload,
                    meta=e.meta,
                    created_at=e.created_at
                )
                for e in entries
            ]
    
    def set_anchor(
        self, 
        tape_id: str, 
        name: str, 
        entry_id: int, 
        state: dict | None = None
    ) -> None:
        """Set or update an anchor at a specific entry."""
        tape_uuid = uuid.UUID(tape_id)
        
        with self._session() as session:
            # Upsert anchor
            anchor = session.scalar(
                select(Anchor).where(
                    Anchor.tape_id == tape_uuid,
                    Anchor.name == name
                )
            )
            
            if anchor:
                anchor.entry_id = entry_id
                anchor.state = state
            else:
                anchor = Anchor(
                    name=name,
                    tape_id=tape_uuid,
                    entry_id=entry_id,
                    state=state
                )
                session.add(anchor)
```

## 5. Name→ID Abstraction

The TapeService needs significant changes to support the name→ID abstraction:

```python
# src/bub/tape/service.py
class TapeService:
    def __init__(
        self, 
        store: TapeStore,
        tape_ref: str,  # Can be name OR UUID
        title: str | None = None
    ) -> None:
        self.store = store
        
        # Try to resolve as name first, then treat as UUID
        resolved_id = store.resolve_name(tape_ref)
        if resolved_id:
            self.tape_id = resolved_id
            self._name = tape_ref
        else:
            # Assume it's already a UUID
            self.tape_id = tape_ref
            self._name = None  # Will look up if needed
        
        self._title = title
    
    @property
    def name(self) -> str | None:
        """Get current name (primary alias)."""
        if self._name is None:
            # Look up primary alias
            self._name = self.store.get_primary_alias(self.tape_id)
        return self._name
    
    def reset(self) -> str:
        """Reset the tape: create new empty tape with same name."""
        old_id = self.tape_id
        new_id = self.store.reset(old_id)
        self.tape_id = new_id
        # Name transfers automatically via reset()
        return new_id
```

Key behaviors:
- **Constructor flexibility**: Accept either name or UUID, resolve internally
- **Internal operations**: Always use `tape_id` (UUID) for storage operations
- **Reset semantics**: New UUID created, old tape archived, name transfers to new tape
- **Immutable history**: Old tape remains accessible via its UUID even after reset

## 6. Migration Strategy

**Chosen Approach: Option B (Eager Migration)**

While lazy migration offers zero downtime, the complexity of maintaining two storage backends and dual query paths outweighs the benefits for our use case. Tapes are not continuously active like a production database—there's natural downtime between sessions. An eager migration with a single `bub tape migrate` command provides a clean cutover and simpler long-term maintenance.

### Migration Command

```python
# src/bub/cli/tape.py
@app.command()
def migrate(
    dry_run: bool = typer.Option(False, help="Show what would be migrated"),
    force: bool = typer.Option(False, help="Skip confirmation"),
) -> None:
    """Migrate all JSONL tapes to SQLite."""
    # 1. Discover all JSONL tapes
    # 2. Validate no SQLite tapes exist (or --force to overwrite)
    # 3. Create SQLite database
    # 4. Migrate each tape:
    #    - Create tape record with UUID
    #    - Register primary alias (filename)
    #    - Copy all entries
    #    - Copy anchors
    # 5. Verify counts match
    # 6. Optionally archive JSONL files
```

### Migration Steps

1. **Pre-migration backup**: Copy all `.tape` files to `.tape.backup/`
2. **Schema creation**: Initialize SQLite with Alembic migrations
3. **Tape migration**: For each JSONL file:
   - Parse filename as primary alias
   - Generate UUID for tape
   - Import entries in batch (1000 at a time)
   - Import anchors with state
4. **Verification**: Count entries in SQLite vs JSONL
5. **Atomic switch**: Update config to use SQLite store
6. **Cleanup**: Move JSONL files to archive (optional, with --archive flag)

## 7. Testing Strategy

### Unit Tests

```python
# tests/tape/test_sqlite_store.py
class TestSQLiteTapeStore:
    def test_create_tape_returns_uuid(self, tmp_path):
        store = SQLiteTapeStore(tmp_path / "test.db")
        tape_id = store.create_tape(name="test")
        assert uuid.UUID(tape_id)  # Valid UUID format
    
    def test_name_resolution(self, tmp_path):
        store = SQLiteTapeStore(tmp_path / "test.db")
        tape_id = store.create_tape(name="my-tape")
        assert store.resolve_name("my-tape") == tape_id
    
    def test_reset_creates_new_tape(self, tmp_path):
        store = SQLiteTapeStore(tmp_path / "test.db")
        old_id = store.create_tape(name="test")
        store.append(old_id, entry)
        
        new_id = store.reset(old_id)
        
        assert new_id != old_id
        assert store.resolve_name("test") == new_id  # Name transferred
        # Old tape should be empty (or check archived flag)
    
    def test_search_finds_content(self, tmp_path):
        store = SQLiteTapeStore(tmp_path / "test.db")
        tape_id = store.create_tape()
        store.append(tape_id, Entry(kind="message", payload={"content": "hello world"}))
        
        results = store.search("hello")
        assert len(results) == 1
        assert "hello world" in results[0]["snippet"]
```

### Migration Tests

```python
# tests/tape/test_migration.py
class TestMigration:
    def test_migrate_jsonl_to_sqlite(self, tmp_path, sample_tape):
        # Create sample JSONL tape
        jsonl_path = tmp_path / "test.tape"
        sample_tape.write_to(jsonl_path)
        
        # Run migration
        migrate_tapes(jsonl_dir=tmp_path, sqlite_path=tmp_path / "tapes.db")
        
        # Verify
        store = SQLiteTapeStore(tmp_path / "tapes.db")
        assert store.resolve_name("test") is not None
        entries = store.read(store.resolve_name("test"))
        assert len(entries) == len(sample_tape.entries)
```

### Performance Benchmarks

```python
# tests/benchmarks/test_tape_queries.py
@pytest.mark.benchmark
class TestQueryPerformance:
    def test_large_tape_read(self, benchmark, large_sqlite_tape):
        """Benchmark reading 10k entries from SQLite vs JSONL."""
        
    def test_search_performance(self, benchmark, indexed_tape):
        """Benchmark FTS5 search vs linear scan."""
```

### Concurrency Tests

```python
# tests/tape/test_concurrency.py
def test_concurrent_appends(sqlite_store):
    """Test WAL mode handles concurrent writes."""
    # SQLite WAL mode allows concurrent reads during writes
```

## 8. Rollback Plan

If migration fails or issues arise:

1. **Config flag**: `BUB_TAPE_BACKEND=jsonl` to revert to FileTapeStore
2. **Backup preservation**: Keep `.tape.backup/` until explicitly deleted
3. **Version check**: SQLite features only available after migration version marker
4. **Health check**: `bub tape verify` command to validate SQLite integrity

Rollback procedure:
```bash
# 1. Switch back to JSONL
export BUB_TAPE_BACKEND=jsonl

# 2. Restore from backup
cp -r ~/.local/share/bub/tapes.backup/* ~/.local/share/bub/tapes/

# 3. Delete SQLite database
rm ~/.local/share/bub/tapes.db
```

## 9. Implementation Phases

### Phase 1: Models + SQLiteTapeStore Core (2-3 days)
- [ ] SQLAlchemy models with relationships
- [ ] SQLiteTapeStore with core CRUD operations
- [ ] Unit tests for store methods
- [ ] Alembic migrations setup

### Phase 2: Name→ID Abstraction (1-2 days)
- [ ] Update TapeService to accept name or UUID
- [ ] Implement resolve_name in both stores
- [ ] Update all call sites to use tape_id internally
- [ ] Test name resolution edge cases

### Phase 3: Migration Tooling (1-2 days)
- [ ] `bub tape migrate` command
- [ ] JSONL→SQLite converter
- [ ] Progress reporting and validation
- [ ] Backup/restore utilities

### Phase 4: Query Optimization + FTS (1-2 days)
- [ ] FTS5 virtual table setup
- [ ] Search implementation with snippets
- [ ] Index optimization for common queries
- [ ] Performance benchmarking

### Phase 5: Testing + Validation (2-3 days)
- [ ] Integration tests for full migration flow
- [ ] Concurrency tests under load
- [ ] Rollback procedure testing
- [ ] Documentation updates

**Total estimated effort: 7-12 days**

## 10. Open Questions

### Decisions Needed

1. **Alembic migration location**: 
   - Option A: `src/bub/tape/migrations/` (co-located with code)
   - Option B: Repository root `migrations/` (conventional location)
   - **Recommendation**: Option A for self-contained package

2. **Auto-run migrations**:
   - Option A: Automatic on store initialization
   - Option B: Manual `bub tape migrate` command
   - **Recommendation**: Option B for explicit control and validation

3. **Dual store support**:
   - Option A: Keep both implementations indefinitely
   - Option B: Deprecate JSONL after migration period
   - **Recommendation**: Option B with 1-month deprecation period

4. **FTS indexing scope**:
   - Option A: Index entire payload JSON
   - Option B: Index specific fields (content, title, etc.)
   - **Recommendation**: Option A initially, optimize based on usage

5. **Tape archiving**:
   - Should archived tapes be queryable?
   - How long to retain before permanent deletion?
   - **Recommendation**: Archived tapes queryable by UUID only, delete after 90 days

## 11. Code Examples

### Model Definitions

```python
# Key relationship patterns
class Tape(Base):
    # ... fields ...
    
    @property
    def entry_count(self) -> int:
        """Efficient count without loading all entries."""
        return object_session(self).scalar(
            select(func.count(TapeEntry.id)).where(TapeEntry.tape_id == self.id)
        )
```

### SQLiteTapeStore.create_tape() Implementation

```python
def create_tape(self, name: str | None = None, title: str | None = None) -> str:
    """Create new tape with optional primary alias.
    
    Returns:
        UUID string for the new tape
    """
    with self._session() as session:
        # Create tape record
        tape = Tape()
        if title:
            tape.meta = {"title": title}
        
        session.add(tape)
        session.flush()  # Generate UUID
        
        # Register primary alias if name provided
        if name:
            # Check for name collision
            existing = session.scalar(
                select(TapeAlias).where(TapeAlias.name == name)
            )
            if existing:
                raise ValueError(f"Name '{name}' already in use")
            
            alias = TapeAlias(
                name=name,
                tape_id=tape.id,
                is_primary=True
            )
            session.add(alias)
        
        return str(tape.id)
```

### Name Resolution Logic

```python
def resolve_name(self, name: str) -> str | None:
    """Resolve alias to tape UUID.
    
    Resolution order:
    1. Check if name is a valid UUID (return as-is)
    2. Look up in tape_aliases table
    3. Return None if not found
    """
    # Fast path: already a UUID
    try:
        uuid.UUID(name)
        return name  # Valid UUID, assume it's a tape_id
    except ValueError:
        pass
    
    # Look up alias
    with self._session() as session:
        alias = session.scalar(
            select(TapeAlias).where(TapeAlias.name == name)
        )
        return str(alias.tape_id) if alias else None
```

## Appendix: Configuration

### Environment Variables

```bash
# Storage backend
BUB_TAPE_BACKEND=sqlite  # or 'jsonl' for fallback

# SQLite specific
BUB_TAPE_SQLITE_PATH=~/.local/share/bub/tapes.db
BUB_TAPE_SQLITE_WAL=true  # Enable WAL mode for better concurrency

# Migration
BUB_TAPE_ARCHIVE_JSONL=true  # Move JSONL files after migration
```

### Database Connection

```python
# Connection pooling for SQLite (not usually needed, but good for concurrency)
engine = create_engine(
    "sqlite:///path/to/tapes.db",
    connect_args={
        "check_same_thread": False,
        "timeout": 30,  # Wait up to 30s for locks
    },
    echo=False,  # Set True for SQL debugging
)

# Enable WAL mode for better concurrent access
with engine.connect() as conn:
    conn.execute(text("PRAGMA journal_mode=WAL"))
    conn.execute(text("PRAGMA synchronous=NORMAL"))
```

---

*This plan provides a comprehensive roadmap for migrating to SQLite storage while maintaining backward compatibility and enabling future enhancements like FTS search and efficient anchor queries.*