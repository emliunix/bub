# Tape Service Test Plan

## Focus: Code-Level Unit Tests Only

No REST API, no CLI, no integration between components.

---

## 1. Manifest Tests

### 1.1 Manifest Model

```python
# tests/test_tape_manifest.py

def test_manifest_create():
    manifest = Manifest()
    assert manifest.version == 1
    assert manifest.tapes == {}
    assert manifest.anchors == {}

def test_manifest_save_and_load(tmp_path):
    manifest = Manifest(home=tmp_path)
    manifest.create_tape("main", head_id=100)
    manifest.save()
    
    loaded = Manifest.load(tmp_path)
    assert "main" in loaded.tapes
    assert loaded.tapes["main"].head_id == 100
```

### 1.2 Tape CRUD

```python
def test_create_tape():
    manifest = Manifest()
    manifest.create_tape("main")
    
    assert "main" in manifest.tapes
    assert manifest.tapes["main"].id == "main"
    assert manifest.tapes["main"].head_id == 0

def test_update_tape():
    manifest = Manifest()
    manifest.create_tape("main")
    manifest.update_tape("main", head_id=50)
    
    assert manifest.tapes["main"].head_id == 50

def test_delete_tape():
    manifest = Manifest()
    manifest.create_tape("main")
    manifest.delete_tape("main")
    
    assert "main" not in manifest.tapes

def test_fork_tape():
    manifest = Manifest()
    manifest.create_tape("main", head_id=100)
    manifest.fork_tape("main", "fork")
    
    assert "fork" in manifest.tapes
    assert manifest.tapes["fork"].parent_id == "main"
    assert manifest.tapes["fork"].file == "main.jsonl"
```

### 1.3 Anchor CRUD

```python
def test_create_anchor():
    manifest = Manifest()
    manifest.create_anchor("phase1", "main", 50, {"summary": "done"})
    
    assert "phase1" in manifest.anchors
    assert manifest.anchors["phase1"].entry_id == 50
    assert manifest.anchors["phase1"].state == {"summary": "done"}

def test_update_anchor():
    manifest = Manifest()
    manifest.create_anchor("phase1", "main", 50)
    manifest.update_anchor("phase1", entry_id=75)
    
    assert manifest.anchors["phase1"].entry_id == 75

def test_delete_anchor():
    manifest = Manifest()
    manifest.create_anchor("phase1", "main", 50)
    manifest.delete_anchor("phase1")
    
    assert "phase1" not in manifest.anchors

def test_list_anchors():
    manifest = Manifest()
    manifest.create_anchor("phase1", "main", 50)
    manifest.create_anchor("phase2", "main", 100)
    
    anchors = list(manifest.anchors.values())
    assert len(anchors) == 2
```

---

## 2. Tape Store Tests

### 2.1 Read with Range

```python
# tests/test_tape_store.py

def test_read_all(tmp_path):
    store = FileTapeStore(home=tmp_path, workspace=Path("."))
    
    for i in range(5):
        store.append("test", TapeEntry(id=i+1, kind="message", payload={"n": i}))
    
    entries = store.read("test")
    assert len(entries) == 5

def test_read_from(tmp_path):
    store = FileTapeStore(home=tmp_path, workspace=Path("."))
    
    for i in range(5):
        store.append("test", TapeEntry(id=i+1, kind="message", payload={"n": i}))
    
    entries = store.read("test", from_entry_id=3)
    assert len(entries) == 3
    assert entries[0].id == 3

def test_read_to(tmp_path):
    store = FileTapeStore(home=tmp_path, workspace=Path("."))
    
    for i in range(5):
        store.append("test", TapeEntry(id=i+1, kind="message", payload={"n": i}))
    
    entries = store.read("test", to_entry_id=3)
    assert len(entries) == 3

def test_read_range(tmp_path):
    store = FileTapeStore(home=tmp_path, workspace=Path("."))
    
    for i in range(5):
        store.append("test", TapeEntry(id=i+1, kind="message", payload={"n": i}))
    
    entries = store.read("test", from_entry_id=2, to_entry_id=4)
    assert len(entries) == 3
    assert entries[0].id == 2
    assert entries[-1].id == 4
```

### 2.2 List Tapes

```python
def test_list_tapes(tmp_path):
    store = FileTapeStore(home=tmp_path, workspace=Path("."))
    
    store.append("tape1", TapeEntry(id=1, kind="message", payload={}))
    store.append("tape2", TapeEntry(id=1, kind="message", payload={}))
    
    tapes = store.list_tapes()
    assert "tape1" in tapes
    assert "tape2" in tapes
```

---

## 3. Anchor Resolution Tests

```python
# tests/test_anchor_resolution.py

def test_resolve_anchor():
    manifest = Manifest()
    manifest.create_anchor("phase1", "main", 50)
    
    entry_id = manifest.resolve_anchor("phase1")
    assert entry_id == 50

def test_resolve_nonexistent():
    manifest = Manifest()
    
    with pytest.raises(KeyError):
        manifest.resolve_anchor("nonexistent")
```

---

## Run Commands

```bash
pytest tests/test_tape_manifest.py -v
pytest tests/test_tape_store.py -v
pytest tests/test_anchor_resolution.py -v

# Specific
pytest tests/test_tape_store.py::test_read_range -v
```
