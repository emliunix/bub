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

### MiniMax / LLM Tool Calling

- `scripts/test_minimax_tools.py`: direct OpenAI-SDK style tool calling tests.
- `scripts/test_minimax_format.py`: dumps raw response format details.
- `scripts/test_republic_minimax.py`: validates tool calling through the Republic client.
- `scripts/test_minimal_republic_minimax.py`: minimal Republic+MiniMax reproduction.

### Bub Stack / Tape / Message Reconstruction

- `scripts/test_bub_minimax_flow.py`: Bub LLM configuration + end-to-end tool calling through Bub’s stack.
- `scripts/test_tape_tool_calls.py`: verifies what gets recorded to tape for tool calls.
- `scripts/test_debug_messages.py`: deep dive into message reconstruction and sequencing.
- `scripts/test_multi_turn.py`: multi-turn behavior validation.

### Bus / RPC / Connectivity

- `scripts/test_bus_client.py`: WebSocket bus client simulation.
- `scripts/probe_bus.py`: quick probe utility for bus connectivity.

### End-to-End Suites

- `scripts/test_e2e_clean.py`: baseline E2E flow.
- `scripts/test_e2e_automated.py`: more automated E2E checks.
- `scripts/test_e2e_telegram.py`: Telegram-focused E2E checks.

### Operational / Validation Helpers

- `scripts/validate_system.py`: validates the system-level wiring.
- `scripts/validate_mermaid.py`: validates Mermaid diagrams used in docs.
- `scripts/e2e_quick_check.sh`: quick shell entrypoint for common E2E checks (if present/used in your workflow).

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
