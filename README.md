# Bub

[![Release](https://img.shields.io/github/v/release/psiace/bub)](https://github.com/psiace/bub/releases)
[![Build status](https://img.shields.io/github/actions/workflow/status/psiace/bub/main.yml?branch=main)](https://github.com/psiace/bub/actions/workflows/main.yml?query=branch%3Amain)
[![Commit activity](https://img.shields.io/github/commit-activity/m/psiace/bub)](https://github.com/psiace/bub/graphs/commit-activity)
[![License](https://img.shields.io/github/license/psiace/bub)](LICENSE)

> Bub it. Build it.

Bub is a coding agent CLI built on `republic`.
It is designed for real engineering workflows where execution must be predictable, inspectable, and recoverable.

**Features:**
- Command-based workflow with natural language fallback
- Session tape with anchor/handoff transitions
- LLM function integration for System F

## Four Things To Know

1. Command boundary is strict: only lines starting with `,` are treated as commands.
2. The same routing model is applied to both user input and assistant output.
3. Successful commands return directly; failed commands fall back to the model with structured context.
4. Session context is append-only tape with explicit `anchor/handoff` transitions.

## Quick Start

```bash
git clone https://github.com/psiace/bub.git
cd bub
uv sync
cp env.example .env
```

Minimal `.env`:

```bash
BUB_AGENT_MODEL=openrouter:qwen/qwen3-coder-next
OPENROUTER_API_KEY=your_key_here
```

Start interactive CLI:

```bash
uv run bub
```

## Interaction Rules

- `hello`: natural language routed to model.
- `,help`: internal command.
- `,git status`: shell command.
- `, ls -la`: shell command (space after comma is optional).

Common commands:

```text
,help
,tools
,tool.describe name=fs.read
,skills.list
,skills.describe name=friendly-python
,handoff name=phase-1 summary="bootstrap done"
,anchors
,tape.info
,tape.search query=error
,tape.reset archive=true
,quit
```

## Telegram (Optional)

```bash
BUB_TELEGRAM_ENABLED=true
BUB_TELEGRAM_TOKEN=123456:token
BUB_TELEGRAM_ALLOW_FROM='["123456789","your_username"]'
uv run bub message
```

## Discord (Optional)

```bash
BUB_DISCORD_ENABLED=true
BUB_DISCORD_TOKEN=discord_bot_token
BUB_DISCORD_ALLOW_FROM='["123456789012345678","your_discord_name"]'
BUB_DISCORD_ALLOW_CHANNELS='["123456789012345678"]'
uv run bub message
```

## WebSocket (Optional)

```bash
BUB_BUS_WEBSOCKET_ENABLED=true
BUB_BUS_WEBSOCKET_URL=ws://localhost:7892
uv run bub websocket
```

## System F LLM Integration

System F supports LLM functions using the `prim_op` syntax:

```systemf
{-# LLM model=gpt-4 temperature=0.7 #-}
-- | Translate English to French
prim_op translate : String
  -- ^ The English text to translate
  -> String
  -- The French translation
```

**Quick example:**
```bash
# Start System F REPL
uv run python -m systemf.repl

# Load LLM examples
> :load systemf/tests/llm_examples.sf

# List LLM functions
> :llm

# Show function details
> :llm translate
```

See `docs/user-manual.md` for complete LLM documentation.

## Documentation

- `docs/index.md`: getting started and usage overview
- `docs/deployment.md`: local + Docker deployment playbook
- `docs/features.md`: key capabilities and why they matter
- `docs/cli.md`: interactive CLI workflow and troubleshooting
- `docs/architecture.md`: agent loop, tape, anchor, and tool/skill design
- `docs/telegram.md`: Telegram integration and operations
- `docs/discord.md`: Discord integration and operations
- `docs/user-manual.md`: System F LLM integration guide

## Development

```bash
uv run ruff check .
uv run mypy
uv run pytest -q
just docs-test
```

## License

[Apache 2.0](./LICENSE)
