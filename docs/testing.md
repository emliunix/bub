# Scripts, Testing, and Debugging

This page documents Bub’s testing facilities and the curated debug scripts under `scripts/`.

> Note: Some scripts are one-off reproductions for past issues. Prefer the newest journal entry in `journal/` when choosing what to run, and treat older scripts as historical unless they still apply.

## What Exists Where

- **Unit tests**: `tests/` (pytest)
- **Debug / integration scripts**: `scripts/`
- **End-to-end checks**: typically `scripts/test_e2e_*.py` and helper shell scripts
- **Architecture + protocol docs**: `docs/agent-protocol.md`, `docs/agent-messages.md`, and `docs/components.md`

## Test Layers

### 1) Unit Tests (pytest)

- Fast feedback for core logic.
- Look in `tests/` for coverage of routing, stop conditions, channels, and CLI behaviors.

### 2) Integration / Repro Scripts (`scripts/`)

- Used to validate specific subsystems or provider integrations.
- Often expect a correctly configured `.env`.

### 3) End-to-End (E2E)

- Exercises multi-component flows.
- Use when validating “a real message goes in and a reply comes out”.

## Script Catalog (Curated)

> **Documentation Status**: Each script entry includes a "Last Modified" date. To check if documentation is current, run: `git log -1 --format="%ai" -- scripts/SCRIPT_NAME.py`

### Bus / RPC / Connectivity

#### test_bus_client.py
**Purpose**: WebSocket bus client simulation.

**Last Modified**: 2026-02-18

**Usage**:
```bash
python scripts/test_bus_client.py [message]
```

---

#### probe_bus.py
**Purpose**: Quick probe utility for bus connectivity.

**Last Modified**: 2026-02-18

**Usage**:
```bash
python scripts/probe_bus.py
```

### End-to-End Suites

#### test_e2e_clean.py
**Purpose**: Baseline E2E flow following agent-protocol.md.

**Last Modified**: 2026-02-19

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

### Operational / Validation Helpers

#### validate_system.py
**Purpose**: Validates the system-level wiring.

**Last Modified**: 2026-02-18

**Usage**:
```bash
python scripts/validate_system.py
```

---

#### validate_mermaid.py
**Purpose**: Validates Mermaid diagrams used in docs.

**Last Modified**: 2026-02-17

**Usage**:
```bash
python scripts/validate_mermaid.py
```

---

#### e2e_quick_check.sh
**Purpose**: Quick shell entrypoint for common E2E checks.

**Last Modified**: 2026-02-18

**Usage**:
```bash
./scripts/e2e_quick_check.sh
```

---

#### deploy-production.sh
**Purpose**: Production deployment script for starting/stopping services.

**Last Modified**: 2026-02-19

**Usage**:
```bash
./scripts/deploy-production.sh start bus
./scripts/deploy-production.sh start system-agent
./scripts/deploy-production.sh status
./scripts/deploy-production.sh stop
```

---

#### docs-server.sh
**Purpose**: MkDocs documentation server with daemon management.

**Last Modified**: 2026-02-16

**Usage**:
```bash
./scripts/docs-server.sh start [port]  # Default: 8000
./scripts/docs-server.sh stop
./scripts/docs-server.sh status
./scripts/docs-server.sh logs
```

---

## Environment Setup Expectations

Many scripts load `.env` and expect provider keys / tokens.

Common examples:

- MiniMax / model provider:
  - `BUB_AGENT_API_KEY` or `MINIMAX_API_KEY`
- Telegram-related:
  - `BUB_BUS_TELEGRAM_TOKEN`

If a script fails immediately, check:
- `.env` exists and is being loaded
- required env vars are set
- the target services (if any) are running

## Related Docs

- Component relationships: `docs/components.md`
- Protocol (transport): `docs/agent-protocol.md`
- Message payload types (application): `docs/agent-messages.md`
- Deployment overview: `docs/deployment.md`
- Interactive CLI usage: `docs/cli.md`
