from pathlib import Path

from republic import TapeEntry

from bub.tape.store import FileTapeStore, TapeFile


def test_store_isolated_by_tape_name(tmp_path: Path) -> None:
    home = tmp_path / "home"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    store = FileTapeStore(home, workspace)

    store.append("a", TapeEntry.message({"role": "user", "content": "one"}))
    store.append("b", TapeEntry.message({"role": "user", "content": "two"}))

    a_entries = store.read("a")
    b_entries = store.read("b")
    assert a_entries is not None
    assert b_entries is not None
    assert a_entries[0].payload["content"] == "one"
    assert b_entries[0].payload["content"] == "two"
    assert sorted(store.list_tapes()) == ["a", "b"]


def test_archive_then_reset(tmp_path: Path) -> None:
    home = tmp_path / "home"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    store = FileTapeStore(home, workspace)

    store.append("session", TapeEntry.event("command", {"raw": "echo hi"}))
    archive = store.archive("session")
    assert archive is not None
    assert archive.exists()
    assert store.read("session") is None


def test_tape_file_read_is_incremental(tmp_path: Path) -> None:
    tape_path = tmp_path / "tape.jsonl"
    tape_file = TapeFile(tape_path)

    tape_path.write_text(
        '{"id":1,"kind":"message","payload":{"content":"one"},"meta":{}}\n',
        encoding="utf-8",
    )
    first = tape_file.read()
    assert [entry.id for entry in first] == [1]

    with tape_path.open("a", encoding="utf-8") as handle:
        handle.write('{"id":2,"kind":"message","payload":{"content":"two"},"meta":{}}\n')
    second = tape_file.read()
    assert [entry.id for entry in second] == [1, 2]


def test_tape_file_read_handles_truncated_file(tmp_path: Path) -> None:
    tape_path = tmp_path / "tape.jsonl"
    tape_file = TapeFile(tape_path)

    tape_path.write_text(
        '{"id":1,"kind":"message","payload":{"content":"one"},"meta":{}}\n',
        encoding="utf-8",
    )
    assert [entry.id for entry in tape_file.read()] == [1]

    tape_path.write_text("", encoding="utf-8")
    assert tape_file.read() == []

    with tape_path.open("a", encoding="utf-8") as handle:
        handle.write('{"id":1,"kind":"message","payload":{"content":"reset"},"meta":{}}\n')
    after_truncate = tape_file.read()
    assert [entry.payload["content"] for entry in after_truncate] == ["reset"]


def test_tape_file_append_increments_ids_without_intermediate_read(tmp_path: Path) -> None:
    tape_path = tmp_path / "tape.jsonl"
    tape_file = TapeFile(tape_path)

    tape_file.append(TapeEntry.message({"role": "user", "content": "one"}))
    tape_file.append(TapeEntry.message({"role": "assistant", "content": "two"}))
    tape_file.append(TapeEntry.message({"role": "assistant", "content": "three"}))

    entries = tape_file.read()
    assert [entry.id for entry in entries] == [1, 2, 3]


def test_tape_file_append_uses_existing_tail_id(tmp_path: Path) -> None:
    tape_path = tmp_path / "tape.jsonl"
    tape_path.write_text(
        '{"id":3,"kind":"message","payload":{"role":"user","content":"existing"},"meta":{}}\n',
        encoding="utf-8",
    )
    tape_file = TapeFile(tape_path)

    tape_file.append(TapeEntry.message({"role": "assistant", "content": "new"}))

    entries = tape_file.read()
    assert [entry.id for entry in entries] == [3, 4]


def test_multi_forks_merge_keeps_entries_ordered(tmp_path: Path) -> None:
    home = tmp_path / "home"
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    store = FileTapeStore(home, workspace)

    root_tape = "session"
    store.append(root_tape, TapeEntry.message({"role": "user", "content": "root-1"}))

    fork_a = store.fork(root_tape)
    fork_b = store.fork(root_tape)

    store.append(fork_a, TapeEntry.message({"role": "assistant", "content": "fork-a-1"}))
    store.append(fork_a, TapeEntry.message({"role": "assistant", "content": "fork-a-2"}))
    store.append(fork_b, TapeEntry.message({"role": "assistant", "content": "fork-b-1"}))
    store.append(fork_b, TapeEntry.message({"role": "assistant", "content": "fork-b-2"}))

    store.merge(fork_b, root_tape)
    store.merge(fork_a, root_tape)

    merged = store.read(root_tape)
    assert merged is not None

    assert [entry.payload["content"] for entry in merged] == [
        "root-1",
        "fork-b-1",
        "fork-b-2",
        "fork-a-1",
        "fork-a-2",
    ]
    assert [entry.id for entry in merged] == [1, 2, 3, 4, 5]
    assert store.read(fork_a) is None
    assert store.read(fork_b) is None


class TestTapeReadRange:
    def test_read_all(self, tmp_path):
        home = tmp_path / "home"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        store = FileTapeStore(home, workspace)

        for i in range(5):
            store.append("test", TapeEntry(id=i + 1, kind="message", payload={"n": i}, meta={}))

        entries = store.read("test")
        assert len(entries) == 5

    def test_read_from(self, tmp_path):
        home = tmp_path / "home"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        store = FileTapeStore(home, workspace)

        for i in range(5):
            store.append("test", TapeEntry(id=i + 1, kind="message", payload={"n": i}, meta={}))

        entries = store.read("test", from_entry_id=3)
        assert len(entries) == 3
        assert entries[0].id == 3

    def test_read_to(self, tmp_path):
        home = tmp_path / "home"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        store = FileTapeStore(home, workspace)

        for i in range(5):
            store.append("test", TapeEntry(id=i + 1, kind="message", payload={"n": i}, meta={}))

        entries = store.read("test", to_entry_id=3)
        assert len(entries) == 3

    def test_read_range(self, tmp_path):
        home = tmp_path / "home"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        store = FileTapeStore(home, workspace)

        for i in range(5):
            store.append("test", TapeEntry(id=i + 1, kind="message", payload={"n": i}, meta={}))

        entries = store.read("test", from_entry_id=2, to_entry_id=4)
        assert len(entries) == 3
        assert entries[0].id == 2
        assert entries[-1].id == 4

    def test_read_nonexistent(self, tmp_path):
        home = tmp_path / "home"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        store = FileTapeStore(home, workspace)

        entries = store.read("nonexistent")
        assert entries is None


class TestTapeTitle:
    def test_create_tape_with_title(self, tmp_path):
        home = tmp_path / "home"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        store = FileTapeStore(home, workspace)

        store.create_tape("main", title="My Session")

        assert store.get_title("main") == "My Session"

    def test_set_title(self, tmp_path):
        home = tmp_path / "home"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        store = FileTapeStore(home, workspace)

        store.create_tape("main")
        store.set_title("main", "Updated Title")

        assert store.get_title("main") == "Updated Title"

    def test_get_title_none(self, tmp_path):
        home = tmp_path / "home"
        workspace = tmp_path / "workspace"
        workspace.mkdir()
        store = FileTapeStore(home, workspace)

        store.create_tape("main")

        assert store.get_title("main") is None


class TestManifestPersistence:
    def test_anchor_ops_persist_after_save(self, tmp_path):
        home = tmp_path / "home"
        workspace = tmp_path / "workspace"
        workspace.mkdir()

        store = FileTapeStore(home, workspace)
        store.create_anchor("phase1", "main", 50, {"summary": "done"})
        store.save_manifest()

        loaded = FileTapeStore(home, workspace)
        anchor = loaded.get_anchor("phase1")
        assert anchor is not None
        assert anchor.entry_id == 50
