# Class Hierarchy

## Session Management Classes

```mermaid
classDiagram
    class AgentRuntime {
        -workspace: Path
        -_agent_settings: AgentSettings
        -_sessions: dict~str, SessionRuntime~
        -scheduler: BackgroundScheduler
        -_llm: LLM
        -_active_inputs: set~asyncio.Task~
        +get_session(session_id) SessionRuntime
        +handle_input(session_id, text) LoopResult
        +reset_session_context(session_id) None
        +discover_skills() list~SkillMetadata~
        +load_skill_body(skill_name) str|None
        +graceful_shutdown() AsyncGenerator
    }

    class SessionRuntime {
        +session_id: str
        +loop: AgentLoop
        +tape: TapeService
        +model_runner: ModelRunner
        +tool_view: ProgressiveToolView
        +handle_input(text) LoopResult
        +reset_context() None
    }

    class SessionGraph {
        -_home: Path
        -_graph_file: Path
        -_sessions: dict~str, SessionMetadata~
        +fork(parent_session_id, from_anchor) str
        +get_parent(session_id) str|None
        +get_metadata(session_id) SessionMetadata|None
        +get_children(parent_session_id) list~str~
        +list_sessions() list~SessionMetadata~
        +set_status(session_id, status) None
    }

    class SessionMetadata {
        +session_id: str
        +parent_session_id: str|None
        +from_anchor: str|None
        +created_at: datetime
        +status: str
    }

    class AgentIntention {
        +next_steps: str
        +context_summary: str
        +trigger_on_complete: str|None
        +created_at: datetime
        +to_state() dict
        +from_state(state) AgentIntention
    }

    class SystemAgent {
        +bus_url: str
        +run_dir: Path
        +sessions_path: Path
        +workspaces_root: Path
        -_sessions_lock: asyncio.Lock
        +start() None
        +stop() None
        +process_message(params) ProcessMessageResult
        -_load_sessions() dict
        -_save_sessions(data) None
        -_handle_spawn_agent(to, payload) None
    }

    class Session~Protocol~ {
        <<interface>>
        +reset_context() None
    }

    class AgentSettings~Protocol~ {
        <<interface>>
        +model: str
        +max_tokens: int
        +max_steps: int
        +system_prompt: str
    }

    class TapeSettings~Protocol~ {
        <<interface>>
        +name: str
        +tape_name: str
        +resolve_home() Path
    }

    AgentRuntime --> SessionRuntime : creates/manages
    SessionRuntime ..|> Session : implements
    AgentRuntime ..|> AgentSettings : uses
    SessionGraph --> SessionMetadata : contains
    SessionGraph --> AgentIntention : tracks
    SystemAgent --> AgentRuntime : spawns
```

## Tape Management Classes

```mermaid
classDiagram
    class TapeStore~Protocol~ {
        <<interface>>
        +create_tape(tape, title, replace_if_exists) str
        +get_title(tape) str|None
        +list_tapes() list~str~
        +read(tape, from_entry_id, to_entry_id) list~TapeEntry~
        +append(tape, entry) None
        +fork(from_tape, new_tape_id, from_entry, from_anchor) str
        +archive(tape_id) Path|None
        +reset(tape) None
        +create_anchor(name, tape_id, entry_id, state) None
        +get_anchor(name) TapeEntry|None
        +list_anchors() list~TapeEntry~
        +resolve_anchor(name) int
    }

    class FileTapeStore {
        -_paths: TapePaths
        -_manifest: Manifest
        +create_tape(tape, title, replace_if_exists) str
        +list_tapes() list~str~
        +read(tape, from_entry_id, to_entry_id) list~TapeEntry~
        +append(tape, entry) None
        +fork(from_tape, new_tape_id, from_entry, from_anchor) str
        +archive(tape_id) Path|None
        +reset(tape_id) None
        +create_anchor(name, tape_id, entry_id, state) None
        +get_anchor(name) TapeEntry|None
        +list_anchors() list~TapeEntry~
        +resolve_anchor(name) int
    }

    class RemoteTapeStore {
        -_base_url: str
        -_workspace: Path
        +create_tape(tape, title, replace_if_exists) str
        +list_tapes() list~str~
        +read(tape, from_entry_id, to_entry_id) list~TapeEntry~
        +append(tape, entry) None
        +fork(from_tape, new_tape_id, from_entry, from_anchor) str
        +archive(tape_id) Path|None
        +reset(tape) None
    }

    class TapeService {
        -_llm: LLM
        -_store: TapeStore
        -_tape: Tape
        +__init__(llm, tape_name, store)
        +tape() Tape
        +fork_session(new_tape_name, from_anchor, intention) TapeService
        +ensure_bootstrap_anchor() None
        +handoff(name, state) list~TapeEntry~
        +read_entries() list~TapeEntry~
        +append_event(name, data) None
        +append_system(content) None
        +info() TapeInfo
        +reset(archive) str
        +anchors(limit) list~AnchorSummary~
        +between_anchors(start, end, kinds) list~TapeEntry~
        +search(query, limit, all_tapes) list~TapeEntry~
    }

    class Tape~republic~ {
        +name: str
        +chat(prompt, system_prompt, model) str
        +tool_calls(prompt, tools, model) list
        +read_entries() list~TapeEntry~
        +append(entry) None
        +handoff(name, state) list~TapeEntry~
        +reset() None
    }

    TapeStore <|.. FileTapeStore : implements
    TapeStore <|.. RemoteTapeStore : implements
    TapeService --> TapeStore : uses
    TapeService --> Tape : wraps
```

## Tape Helper Classes

```mermaid
classDiagram
    class TapePaths {
        -_home: Path
        -_tape_id: str
        +home() Path
        +tape_dir() Path
        +entries_file() Path
        +anchors_file() Path
        +meta_file() Path
        +archive_dir() Path
    }

    class TapeFile {
        -_path: Path
        -_entries: list~TapeEntry~
        +read_all() list~TapeEntry~
        +append(entry) None
        +reset() None
        +_load() list~TapeEntry~
        +_save() None
    }

    class TapeInfo {
        +name: str
        +title: str|None
        +entry_count: int
        +anchor_count: int
    }

    class AnchorSummary {
        +name: str
        +entry_id: int
        +created_at: datetime
    }

    class TapeMeta {
        +title: str|None
        +created_at: datetime
        +updated_at: datetime
    }

    class Manifest {
        -_path: Path
        -_tapes: dict~str, TapeMeta~
        +list_tapes() list~str~
        +get_meta(tape_id) TapeMeta|None
        +set_meta(tape_id, meta) None
        +remove(tape_id) None
        +_load() dict
        +_save() None
    }

    class Anchor {
        +name: str
        +tape_id: str
        +entry_id: int
        +state: dict
        +created_at: datetime
    }

    TapePaths --> TapeFile : provides paths for
    Manifest --> TapeMeta : contains
    FileTapeStore --> TapePaths : uses
    FileTapeStore --> Manifest : uses
    TapeService --> TapeInfo : returns
```

## Channel Classes

```mermaid
classDiagram
    class ChannelManager {
        -runtime: AppRuntime
        -_channels: dict~str, BaseChannel~
        -_channel_tasks: list~asyncio.Task~
        +register(channel_cls: type~BaseChannel~) type~BaseChannel~
        +run() None
        +enabled_channels() list~str~
        +default_channels() list~type~BaseChannel~
    }

    class BaseChannel~T~ {
        +name: str
        -runtime: AppRuntime
        +__init__(runtime: AppRuntime)
        +start(on_receive: Callable~[T], Awaitable~None~~)*
        +run_prompt(message: T) None
        +get_session_prompt(message: T) tuple~str, str~*
        +process_output(session_id: str, output: LoopResult)*
    }

    class TelegramChannel {
        +name = "telegram"
        -_config: TelegramConfig
        -_app: Application
        +start(on_receive) None
        +get_session_prompt(message) tuple
        +process_output(session_id, output) None
        -_on_text(update, context) None
    }

    class DiscordChannel {
        +name = "discord"
        -_config: DiscordConfig
        -_bot: commands.Bot
        +start(on_receive) None
        +get_session_prompt(message) tuple
        +process_output(session_id, output) None
        -_on_message(message) None
    }

    ChannelManager --> BaseChannel : manages
    BaseChannel <|-- TelegramChannel
    BaseChannel <|-- DiscordChannel
    BaseChannel --> AgentRuntime : uses
    ChannelManager --> AgentRuntime : initializes with
```

## File Locations

| Class | File | Purpose |
|-------|------|---------|
| `SessionRuntime` | `src/bub/app/runtime.py:37` | Runtime state for one session |
| `AgentRuntime` | `src/bub/app/runtime.py:66` | Manages multiple session loops |
| `SessionGraph` | `src/bub/tape/session.py:54` | Tracks session lineage/forks |
| `SessionMetadata` | `src/bub/tape/session.py:44` | Metadata for session in graph |
| `AgentIntention` | `src/bub/tape/session.py:14` | Intention for forked sessions |
| `SystemAgent` | `src/bub/system_agent.py:37` | Spawns conversation agents |
| `Session` (Protocol) | `src/bub/app/types.py:55` | Protocol for session interface |
| `AgentSettings` (Protocol) | `src/bub/app/types.py:13` | Protocol for agent settings |
| `TapeSettings` (Protocol) | `src/bub/app/types.py:25` | Protocol for tape settings |
| `TapeStore` (Protocol) | `src/bub/app/types.py:61` | Persistence interface |
| `FileTapeStore` | `src/bub/tape/store.py:159` | Local file storage |
| `RemoteTapeStore` | `src/bub/tape/remote.py:14` | HTTP client storage |
| `TapeService` | `src/bub/tape/service.py:48` | High-level tape operations |
| `TapeInfo` | `src/bub/tape/service.py:23` | Tape runtime info |
| `TapePaths` | `src/bub/tape/store.py:25` | Path resolution helper |
| `TapeFile` | `src/bub/tape/store.py:33` | File I/O helper |
| `TapeMeta` | `src/bub/tape/types.py:11` | Tape metadata |
| `Manifest` | `src/bub/tape/types.py:32` | Tape registry |
| `Anchor` | `src/bub/tape/types.py:22` | Anchor entry type |
| `AnchorSummary` | `src/bub/tape/anchors.py:9` | Anchor info summary |

## Cross-References

- [Tape Architecture](09-tape-architecture.md) - Detailed tape system design
- [Session Lifecycle](06-session-lifecycle.md) - How sessions use tapes
