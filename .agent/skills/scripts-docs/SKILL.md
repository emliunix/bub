---
name: scripts-docs
description: Documentation maintenance for scripts/ folder - tracking all debug/integration scripts with last modified dates
---

# Scripts Documentation

This skill tracks all scripts in `scripts/` directory. Each script has a documentation entry with last modified date.

## Maintenance Workflow

### Checking if Documentation is Outdated

**Single script check:**
```bash
git log -1 --format="%ai %s" -- scripts/SCRIPT_NAME.py
```

**Check all scripts at once:**
```bash
git log --name-only --pretty=format: scripts/ | grep -E '\.py$|\.sh$' | sort | uniq
```

**View recent changes to scripts folder:**
```bash
git log --oneline --name-only scripts/ | head -50
```

Compare the git log dates with the `last_modified` dates in this document. If they differ, update the documentation.

## Script Catalog

### Bus / RPC Testing

#### probe_bus.py
**Purpose**: Remote probe to test bus connectivity and spawn functionality.

**Last Modified**: 2026-02-18

**Usage**:
```bash
python scripts/probe_bus.py
```

**What it tests**: Bus connectivity, spawn requests, message flow

---

#### test_bus_client.py
**Purpose**: WebSocket bus test client simulating Telegram messages.

**Last Modified**: 2026-02-18

**Usage**:
```bash
python scripts/test_bus_client.py [message]
```

---

#### test_bus_concurrent.py
**Purpose**: Concurrent bus client testing.

**Last Modified**: 2026-02-18

**Usage**:
```bash
python scripts/test_bus_concurrent.py
```

---

#### test_bus_integration_3clients.py
**Purpose**: Integration test with 3 simultaneous clients.

**Last Modified**: 2026-02-18

**Usage**:
```bash
python scripts/test_bus_integration_3clients.py
```

### End-to-End Testing

#### test_e2e_clean.py
**Purpose**: Clean baseline E2E test following agent-protocol.md.

**Last Modified**: 2026-02-18

**Tests**:
1. Connect mock telegram bridge to bus
2. Request spawn from system agent
3. Receive spawn response with agent_id
4. Send configure to agent (set talkto)
5. Send tg_message to agent
6. Wait for tg_reply response

**Usage**:
```bash
python scripts/test_e2e_clean.py
```

---

#### test_e2e_automated.py
**Purpose**: Automated E2E checks.

**Last Modified**: 2026-02-19

**Usage**:
```bash
python scripts/test_e2e_automated.py
```

---

#### test_e2e_telegram.py
**Purpose**: Telegram-focused E2E tests.

**Last Modified**: 2026-02-18

**Usage**:
```bash
python scripts/test_e2e_telegram.py
```

### MiniMax / LLM Testing

#### test_minimax_tools.py
**Purpose**: Direct OpenAI SDK tests for MiniMax tool calling.

**Last Modified**: 2026-02-18

**Tests**: Basic chat, tool calls, tool results with OpenAI format

**Usage**:
```bash
python scripts/test_minimax_tools.py
```

---

#### test_minimax_format.py
**Purpose**: Check MiniMax response format details.

**Last Modified**: 2026-02-18

**Usage**:
```bash
python scripts/test_minimax_format.py [API_KEY]
```

---

#### test_republic_minimax.py
**Purpose**: Test MiniMax through Republic client.

**Last Modified**: 2026-02-18

**Validates**: tool_calls() and raw response parsing

**Usage**:
```bash
python scripts/test_republic_minimax.py
```

---

#### test_minimal_republic_minimax.py
**Purpose**: Minimal Republic+MiniMax reproduction.

**Last Modified**: 2026-02-18

**Usage**:
```bash
python scripts/test_minimal_republic_minimax.py
```

### Bub Stack Testing

#### test_bub_integration.py
**Purpose**: Bub integration test.

**Last Modified**: 2026-02-18

**Usage**:
```bash
python scripts/test_bub_integration.py
```

---

#### test_bub_minimax_flow.py
**Purpose**: Test Bub's LLM configuration flow.

**Last Modified**: 2026-02-18

**Tests**: Settings loading, tape store, LLM client setup

**Usage**:
```bash
python scripts/test_bub_minimax_flow.py
```

---

#### test_tape_tool_calls.py
**Purpose**: Debug tape recording of tool calls.

**Last Modified**: 2026-02-18

**Checks**: What's actually stored on tape after tool calls

**Usage**:
```bash
python scripts/test_tape_tool_calls.py
```

---

#### test_debug_messages.py
**Purpose**: Deep dive into message reconstruction and sequencing.

**Last Modified**: 2026-02-18

**Usage**:
```bash
python scripts/test_debug_messages.py
```

---

#### test_multi_turn.py
**Purpose**: Multi-turn behavior validation.

**Last Modified**: 2026-02-18

**Usage**:
```bash
python scripts/test_multi_turn.py
```

### Issue Reproduction

#### test_reproduce_issue.py
**Purpose**: Script for reproducing specific issues.

**Last Modified**: 2026-02-18

**Usage**:
```bash
python scripts/test_reproduce_issue.py
```

### Validation

#### validate_system.py
**Purpose**: End-to-end validation test for Bub system.

**Last Modified**: 2026-02-18

**Tests**: Bus connection, message flow

**Usage**:
```bash
python scripts/validate_system.py
```

---

#### validate_mermaid.py
**Purpose**: Validates Mermaid diagrams used in docs.

**Last Modified**: 2026-02-18

**Usage**:
```bash
# Validate all diagrams
python scripts/validate_mermaid.py

# Validate specific file
python scripts/validate_mermaid.py docs/architecture/my-diagram.md

# Output rendered SVGs
python scripts/validate_mermaid.py -o docs/mermaid-output/
```

### Shell Scripts

#### deploy-production.sh
**Purpose**: Production deployment script.

**Last Modified**: 2026-02-19

**Usage**:
```bash
./scripts/deploy-production.sh start bus
./scripts/deploy-production.sh start system-agent
./scripts/deploy-production.sh status
```

---

#### docs-server.sh
**Purpose**: MkDocs documentation server control.

**Last Modified**: 2026-02-18

**Usage**:
```bash
./scripts/docs-server.sh start [port]
./scripts/docs-server.sh stop
./scripts/docs-server.sh status
./scripts/docs-server.sh logs
```

---

#### docs-serve.sh
**Purpose**: Simple docs server (alternative).

**Last Modified**: 2026-02-18

**Usage**:
```bash
./scripts/docs-serve.sh
```

---

#### e2e_quick_check.sh
**Purpose**: Quick shell entrypoint for common E2E checks.

**Last Modified**: 2026-02-18

**Usage**:
```bash
./scripts/e2e_quick_check.sh
```

## Documentation Update Checklist

When maintaining this documentation:

- [ ] Run `git log --name-only --pretty=format: scripts/ | sort | uniq` to get all scripts
- [ ] Check each script's last modified date with `git log -1 --format="%ai" -- scripts/NAME`
- [ ] Compare with `last_modified` dates in this document
- [ ] Update any outdated dates
- [ ] Add new scripts if any are missing
- [ ] Remove entries for deleted scripts
- [ ] Update script descriptions if functionality changed

## Environment Requirements

Most scripts expect:
- `.env` file with required keys
- Python environment with dependencies installed
- Services running (for integration tests)

Common environment variables:
```bash
BUB_AGENT_API_KEY=          # For MiniMax tests
MINIMAX_API_KEY=            # Alternative MiniMax key
BUB_BUS_TELEGRAM_TOKEN=     # For Telegram tests
```
