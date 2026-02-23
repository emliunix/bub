# NanoClaw Research: Agent Loop & Chat History Management

## Overview

NanoClaw is a minimal AI assistant framework that runs Claude Code in isolated containers. It uses the **Claude Agent SDK** (`@anthropic-ai/claude-agent-sdk`) for the agent loop.

**Architecture**: `WhatsApp (baileys) --> SQLite --> Polling loop --> Container (Claude Agent SDK) --> Response`

---

## 1. Agent Loop Implementation

### 1.1 Main Orchestrator (`src/index.ts`)

The agent loop operates at **two levels**:

#### Level 1: Host Message Loop (`startMessageLoop()`)
- Polls SQLite database every `POLL_INTERVAL` (default: 1 second)
- Retrieves new messages via `getNewMessages()`
- Groups messages by chat JID
- For non-main groups, only processes messages containing trigger word (default: `@Andy`)
- Enqueues messages to `GroupQueue` for processing

```typescript
// Key flow:
while (true) {
  const { messages, newTimestamp } = getNewMessages(jids, lastTimestamp, ASSISTANT_NAME);
  // Advance cursor immediately
  lastTimestamp = newTimestamp;
  saveState();
  
  // Group by chat and enqueue
  for (const [chatJid, groupMessages] of messagesByGroup) {
    if (queue.sendMessage(chatJid, formatted)) {
      // Piped to active container
    } else {
      queue.enqueueMessageCheck(chatJid); // Start new container
    }
  }
  await sleep(POLL_INTERVAL);
}
```

#### Level 2: Container Agent Loop (`container/agent-runner/src/index.ts`)

The container runs a **query loop** that:

1. Receives initial prompt via stdin
2. Runs `query()` from Claude Agent SDK with streaming output
3. Waits for IPC messages or `_close` sentinel
4. Repeats with new prompts until close signal

```typescript
// Container query loop:
while (true) {
  const result = await runQuery(prompt, sessionId, ...);
  
  // Update session tracking
  if (result.newSessionId) sessionId = result.newSessionId;
  if (result.lastAssistantUuid) resumeAt = result.lastAssistantUuid;
  
  // Check for close signal
  if (result.closedDuringQuery) break;
  
  // Emit session update marker
  writeOutput({ status: 'success', result: null, newSessionId: sessionId });
  
  // Wait for next message
  const nextMessage = await waitForIpcMessage();
  if (nextMessage === null) break;
  
  prompt = nextMessage;
}
```

### 1.2 MessageStream Class

Uses a **push-based async iterable** to feed messages to the SDK:

```typescript
class MessageStream {
  private queue: SDKUserMessage[] = [];
  private waiting: (() => void) | null = null;
  private done = false;

  push(text: string): void {
    this.queue.push({
      type: 'user',
      message: { role: 'user', content: text },
      parent_tool_use_id: null,
      session_id: '',
    });
    this.waiting?.();
  }

  async *[Symbol.asyncIterator](): AsyncGenerator<SDKUserMessage> {
    while (true) {
      while (this.queue.length > 0) yield this.queue.shift()!;
      if (this.done) return;
      await new Promise<void>(r => { this.waiting = r; });
    }
  }
}
```

This design:
- Keeps `isSingleUserTurn=false` (allows agent teams/subagents to complete)
- Supports streaming follow-up messages during an active query
- Enables real-time IPC communication

### 1.3 Group Queue Management (`src/group-queue.ts`)

Manages **per-group concurrency** with global limits:

```typescript
export class GroupQueue {
  private groups = new Map<string, GroupState>();
  private activeCount = 0;
  private waitingGroups: string[] = [];
}
```

**Key features:**
- `MAX_CONCURRENT_CONTAINERS` (default: 3) limits global parallelism
- Each group gets a `GroupState` tracking active status, pending messages, and tasks
- Exponential backoff retry on errors (max 5 retries)
- Tasks take priority over messages during draining

**State machine per group:**
```
Inactive → Active (processing) → Idle-waiting → Closed → Inactive
                ↓
         (on error) → Retry with backoff
```

---

## 2. Chat History Management

### 2.1 Storage Architecture

#### SQLite Database (`src/db.ts`)

Stores conversation history in **three main tables**:

```sql
-- Messages table
CREATE TABLE messages (
  id TEXT,
  chat_jid TEXT,
  sender TEXT,
  sender_name TEXT,
  content TEXT,
  timestamp TEXT,
  is_from_me INTEGER,
  is_bot_message INTEGER DEFAULT 0,
  PRIMARY KEY (id, chat_jid)
);
CREATE INDEX idx_timestamp ON messages(timestamp);

-- Chat metadata (no content)
CREATE TABLE chats (
  jid TEXT PRIMARY KEY,
  name TEXT,
  last_message_time TEXT,
  channel TEXT,
  is_group INTEGER DEFAULT 0
);

-- Sessions for resuming conversations
CREATE TABLE sessions (
  group_folder TEXT PRIMARY KEY,
  session_id TEXT NOT NULL
);
```

#### Retrieval Methods

**`getNewMessages()`**: Gets all messages newer than `lastTimestamp`
```typescript
export function getNewMessages(
  jids: string[],
  lastTimestamp: string,
  botPrefix: string,
): { messages: NewMessage[]; newTimestamp: string }
```

**`getMessagesSince()`**: Gets messages for a specific chat since a timestamp
```typescript
export function getMessagesSince(
  chatJid: string,
  sinceTimestamp: string,
  botPrefix: string,
): NewMessage[]
```

### 2.2 Session Persistence

**Session tracking** enables conversation continuity:

1. **Host tracks sessions** in SQLite:
   ```typescript
   // In src/index.ts
   let sessions: Record<string, string> = {}; // groupFolder -> sessionId
   
   // Loaded from DB on startup
   sessions = getAllSessions();
   
   // Updated when container returns newSessionId
   sessions[group.folder] = output.newSessionId;
   setSession(group.folder, output.newSessionId);
   ```

2. **Container resumes sessions** via SDK:
   ```typescript
   for await (const message of query({
     prompt: stream,
     options: {
       resume: sessionId,  // Previous session ID
       resumeSessionAt: resumeAt,  // Last assistant UUID
       // ...
     }
   })) { ... }
   ```

3. **Session files** in container:
   - Mounted at `/home/node/.claude/` (per-group isolation)
   - Contains `.claude/settings.json` with experimental features
   - Transcripts stored here by SDK automatically

### 2.3 Context Management

#### Cursor-Based Tracking

**Two-level cursor system** prevents message loss:

1. **`lastTimestamp`**: Global cursor for message polling
   - Advanced immediately when messages are retrieved
   - Stored in `router_state` table

2. **`lastAgentTimestamp`**: Per-group cursor for agent processing
   - Advanced after successful agent processing
   - Rolled back on error (enables retry)
   - Stored as JSON in `router_state`

```typescript
// On successful processing:
lastAgentTimestamp[chatJid] = missedMessages[missedMessages.length - 1].timestamp;
saveState();

// On error:
lastAgentTimestamp[chatJid] = previousCursor; // Rollback
saveState();
```

#### Context Window & Compaction

**Pre-compaction hook** archives conversations before SDK compacts:

```typescript
function createPreCompactHook(): HookCallback {
  return async (input, _toolUseId, _context) => {
    const preCompact = input as PreCompactHookInput;
    const transcriptPath = preCompact.transcript_path;
    const sessionId = preCompact.session_id;
    
    // Archive to /workspace/group/conversations/
    const markdown = formatTranscriptMarkdown(messages, summary);
    fs.writeFileSync(filePath, markdown);
  };
}
```

Archives saved as: `{date}-{sanitized-summary}.md`

### 2.4 Group Isolation

**Filesystem isolation** per group:

```typescript
// Main group gets full project access
mounts.push({
  hostPath: projectRoot,
  containerPath: '/workspace/project',
  readonly: false,
});

// All groups get their isolated folder
mounts.push({
  hostPath: path.join(GROUPS_DIR, group.folder),
  containerPath: '/workspace/group',
  readonly: false,
});

// Per-group sessions directory
mounts.push({
  hostPath: groupSessionsDir,  // DATA_DIR/sessions/{group.folder}/.claude
  containerPath: '/home/node/.claude',
  readonly: false,
});
```

**IPC isolation**: Each group has separate IPC namespace at `/workspace/ipc/{group.folder}/`

---

## 3. Key Implementation Patterns

### 3.1 Streaming Output Protocol

Uses **marker-based streaming** for robust parsing:

```typescript
const OUTPUT_START_MARKER = '---NANOCLAW_OUTPUT_START---';
const OUTPUT_END_MARKER = '---NANOCLAW_OUTPUT_END---';

function writeOutput(output: ContainerOutput): void {
  console.log(OUTPUT_START_MARKER);
  console.log(JSON.stringify(output));
  console.log(OUTPUT_END_MARKER);
}
```

Host parses markers from stdout to stream results to users in real-time.

### 3.2 IPC Communication

**File-based IPC** between host and containers:

```
Host writes: /data/ipc/{group.folder}/input/{timestamp}-{random}.json
Container polls: /workspace/ipc/input/ (mounted directory)
```

Close signaled by `_close` sentinel file.

### 3.3 Error Handling & Recovery

**Automatic retry with exponential backoff**:
```typescript
private scheduleRetry(groupJid: string, state: GroupState): void {
  state.retryCount++;
  if (state.retryCount > MAX_RETRIES) {
    // Drop messages, will retry on next incoming message
    state.retryCount = 0;
    return;
  }
  
  const delayMs = BASE_RETRY_MS * Math.pow(2, state.retryCount - 1);
  setTimeout(() => this.enqueueMessageCheck(groupJid), delayMs);
}
```

**Startup recovery**: Checks for unprocessed messages on restart
```typescript
function recoverPendingMessages(): void {
  for (const [chatJid, group] of Object.entries(registeredGroups)) {
    const pending = getMessagesSince(chatJid, sinceTimestamp, ASSISTANT_NAME);
    if (pending.length > 0) {
      queue.enqueueMessageCheck(chatJid);
    }
  }
}
```

---

## 4. Comparison with Bub

| Aspect | NanoClaw | Bub |
|--------|----------|-----|
| **Agent SDK** | Claude Agent SDK (`@anthropic-ai/claude-agent-sdk`) | Custom implementation |
| **Isolation** | Linux containers (Docker/Apple Container) | Process-based |
| **Session Storage** | Filesystem (`/home/node/.claude/`) | SQLite |
| **Message Queue** | Per-group with global concurrency limit | Bus-based routing |
| **History** | SQLite + archived Markdown files | Tape system |
| **Streaming** | Marker-based stdout streaming | Custom protocol |
| **Context** | Per-group isolated | Thread-based |

---

## 5. Key Files Reference

| File | Purpose |
|------|---------|
| `src/index.ts` | Orchestrator: state, message loop, agent invocation |
| `src/container-runner.ts` | Spawns agent containers, handles IPC |
| `src/db.ts` | SQLite operations (messages, sessions, groups) |
| `src/group-queue.ts` | Per-group queue with concurrency control |
| `src/ipc.ts` | IPC watcher and task processing |
| `container/agent-runner/src/index.ts` | Container agent loop using Claude Agent SDK |
| `groups/{name}/CLAUDE.md` | Per-group memory |
| `groups/{name}/conversations/` | Archived conversation history |

---

## Summary

NanoClaw's agent loop is **SDK-driven** with the Claude Agent SDK handling the core LLM interaction loop. The host manages:

1. **Message polling** from WhatsApp → SQLite
2. **Queue orchestration** with per-group isolation
3. **Container lifecycle** (spawn, IPC, teardown)
4. **Session persistence** across container restarts

Chat history uses a **dual-storage approach**:
- **SQLite** for active message retrieval and cursor tracking
- **Filesystem** for SDK session state and archived conversations

The design prioritizes **isolation** (per-group containers), **reliability** (cursor rollback on errors), and **simplicity** (minimal codebase).