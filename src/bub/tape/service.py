"""High-level tape service."""

from __future__ import annotations

import json
import re
from contextvars import ContextVar
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast

from loguru import logger
from rapidfuzz import fuzz, process
from republic import LLM, TapeEntry
from republic.tape import Tape

from bub.app.runtime import TapeStore
from bub.tape.anchors import AnchorSummary
from bub.tape.session import AgentIntention


@dataclass(frozen=True)
class TapeInfo:
    """Runtime tape info summary."""

    name: str
    entries: int
    anchors: int
    last_anchor: str | None
    entries_since_last_anchor: int


_tape_context: ContextVar[Tape] = ContextVar("tape")
WORD_PATTERN = re.compile(r"[a-z0-9_/-]+")
MIN_FUZZY_QUERY_LENGTH = 3
MIN_FUZZY_SCORE = 80
MAX_FUZZY_CANDIDATES = 128


def current_tape() -> str:
    """Get the name of the current tape in context."""
    tape = _tape_context.get(None)
    if tape is None:
        return "-"
    return tape.name  # type: ignore[no-any-return]


class TapeService:
    """Tape helper with app-specific operations."""

    def __init__(self, llm: LLM, tape_name: str, *, store: TapeStore) -> None:
        self._llm = llm
        self._store = store
        self._tape = llm.tape(tape_name)

    @property
    def tape(self) -> Tape:
        return _tape_context.get(self._tape)

    def fork_session(
        self,
        new_tape_name: str,
        from_anchor: str | None = None,
        intention: AgentIntention | None = None,
    ) -> TapeService:
        """Create a new session (tape) continuing from an anchor in this tape.

        Args:
            new_tape_name: Name for the new tape (usually includes session_id)
            from_anchor: Start from this anchor. If None, starts from beginning.
            intention: Optional intention to record on the new tape.

        Returns:
            New TapeService for the forked session.
        """
        entries = self.between_anchors(from_anchor, "latest") if from_anchor else self.read_entries()

        new_tape = TapeService(self._llm, new_tape_name, store=self._store)

        for entry in entries:
            if from_anchor and entry.payload.get("name") == from_anchor:
                continue
            new_tape.tape.append(entry)

        if intention:
            new_tape.handoff("intention", state=intention.to_state())
        else:
            new_tape.ensure_bootstrap_anchor()

        logger.info("Forked session '{}' from anchor '{}'", new_tape_name, from_anchor)
        return new_tape

    def get_intention(self) -> AgentIntention | None:
        """Get the intention from the current tape if it exists."""
        entries = [e for e in self.read_entries() if e.kind == "anchor" and e.payload.get("name") == "intention"]
        if not entries:
            return None
        state = entries[-1].payload.get("state")
        if isinstance(state, dict):
            return AgentIntention.from_state(state)
        return None

    def ensure_bootstrap_anchor(self) -> None:
        anchors = [entry for entry in self.read_entries() if entry.kind == "anchor"]
        if anchors:
            return
        self.handoff("session/start", state={"owner": "human"})

    def read_entries(self) -> list[TapeEntry]:
        logger.debug("tape.service.read_entries tape={}", self._tape.name)
        entries = cast(list[TapeEntry], self.tape.read_entries())
        logger.debug("tape.service.read_entries_complete tape={} count={}", self._tape.name, len(entries))
        return entries

    def handoff(self, name: str, *, state: dict[str, Any] | None = None) -> list[TapeEntry]:
        logger.debug("tape.service.handoff tape={} name={}", self._tape.name, name)
        result = cast(list[TapeEntry], self.tape.handoff(name, state=state))
        logger.info("tape.service.handoff_complete tape={} name={} entries={}", self._tape.name, name, len(result))
        return result

    def append_event(self, name: str, data: dict[str, Any]) -> None:
        logger.debug("tape.service.append_event tape={} name={}", self._tape.name, name)
        self.tape.append(TapeEntry.event(name, data=data))
        logger.debug("tape.service.append_event_complete tape={} name={}", self._tape.name, name)

    def append_system(self, content: str) -> None:
        logger.debug("tape.service.append_system tape={}", self._tape.name)
        self.tape.append(TapeEntry.system(content))
        logger.debug("tape.service.append_system_complete tape={}", self._tape.name)

    def info(self) -> TapeInfo:
        entries = self._tape.read_entries()
        anchors = [entry for entry in entries if entry.kind == "anchor"]
        last_anchor = anchors[-1].payload.get("name") if anchors else None
        if last_anchor is not None:
            entries_since_last_anchor = sum(1 for entry in entries if entry.id > anchors[-1].id)
        else:
            entries_since_last_anchor = len(entries)
        return TapeInfo(
            name=self._tape.name,
            entries=len(entries),
            anchors=len(anchors),
            last_anchor=str(last_anchor) if last_anchor else None,
            entries_since_last_anchor=entries_since_last_anchor,
        )

    def reset(self, *, archive: bool = False) -> str:
        logger.debug("tape.service.reset tape={} archive={}", self._tape.name, archive)
        archive_path: Path | None = None
        if archive and self._store is not None:
            archive_path = self._store.archive(self._tape.name)
        self._tape.reset()
        state = {"owner": "human"}
        if archive_path is not None:
            state["archived"] = str(archive_path)
        self._tape.handoff("session/start", state=state)
        result = f"Archived: {archive_path}" if archive_path else "ok"
        logger.info("tape.service.reset_complete tape={} result={}", self._tape.name, result)
        return result

    def anchors(self, *, limit: int = 20) -> list[AnchorSummary]:
        entries = [entry for entry in self._tape.read_entries() if entry.kind == "anchor"]
        results: list[AnchorSummary] = []
        for entry in entries[-limit:]:
            name = str(entry.payload.get("name", "-"))
            state = entry.payload.get("state")
            state_dict: dict[str, object] = dict(state) if isinstance(state, dict) else {}
            results.append(AnchorSummary(name=name, state=state_dict))
        return results

    def between_anchors(self, start: str, end: str, *, kinds: tuple[str, ...] = ()) -> list[TapeEntry]:
        query = self.tape.query().between_anchors(start, end)
        if kinds:
            query = query.kinds(*kinds)
        return cast(list[TapeEntry], query.all())

    def after_anchor(self, anchor: str, *, kinds: tuple[str, ...] = ()) -> list[TapeEntry]:
        query = self.tape.query().after_anchor(anchor)
        if kinds:
            query = query.kinds(*kinds)
        return cast(list[TapeEntry], query.all())

    def from_last_anchor(self, *, kinds: tuple[str, ...] = ()) -> list[TapeEntry]:
        query = self.tape.query().last_anchor()
        if kinds:
            query = query.kinds(*kinds)
        return cast(list[TapeEntry], query.all())

    def search(self, query: str, *, limit: int = 20, all_tapes: bool = False) -> list[TapeEntry]:
        normalized_query = query.strip().lower()
        if not normalized_query:
            return []
        results: list[TapeEntry] = []
        tapes = [self.tape]
        if all_tapes:
            tapes = [self._llm.tape(name) for name in self._store.list_tapes()]

        for tape in tapes:
            count = 0
            for entry in reversed(tape.read_entries()):
                payload_text = json.dumps(entry.payload, ensure_ascii=False)
                entry_meta = getattr(entry, "meta", {})
                meta_text = json.dumps(entry_meta, ensure_ascii=False)

                if (
                    normalized_query in payload_text.lower() or normalized_query in meta_text.lower()
                ) or self._is_fuzzy_match(normalized_query, payload_text, meta_text):
                    results.append(entry)
                    count += 1
                    if count >= limit:
                        break
        return results

    @staticmethod
    def _is_fuzzy_match(normalized_query: str, payload_text: str, meta_text: str) -> bool:
        if len(normalized_query) < MIN_FUZZY_QUERY_LENGTH:
            return False

        query_tokens = WORD_PATTERN.findall(normalized_query)
        if not query_tokens:
            return False
        query_phrase = " ".join(query_tokens)
        window_size = len(query_tokens)

        source_tokens = WORD_PATTERN.findall(payload_text.lower()) + WORD_PATTERN.findall(meta_text.lower())
        if not source_tokens:
            return False

        candidates: list[str] = []
        for token in source_tokens:
            candidates.append(token)
            if len(candidates) >= MAX_FUZZY_CANDIDATES:
                break

        if window_size > 1:
            max_window_start = len(source_tokens) - window_size + 1
            for idx in range(max(0, max_window_start)):
                candidates.append(" ".join(source_tokens[idx : idx + window_size]))
                if len(candidates) >= MAX_FUZZY_CANDIDATES:
                    break

        best_match = process.extractOne(
            query_phrase,
            candidates,
            scorer=fuzz.WRatio,
            score_cutoff=MIN_FUZZY_SCORE,
        )
        return best_match is not None
