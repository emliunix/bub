# Deployment Guide

This page covers production-oriented setups for Bub, including local process management and Docker Compose.

## 1) Prerequisites

- Python 3.12+
- `uv` installed
- A valid model provider key (for example `OPENROUTER_API_KEY` or `LLM_API_KEY`)

Quick bootstrap:

```bash
git clone https://github.com/psiace/bub.git
cd bub
uv sync
cp env.example .env
```

Minimum `.env`:

```bash
BUB_MODEL=openrouter:qwen/qwen3-coder-next
OPENROUTER_API_KEY=sk-or-...
```

## 2) Deployment Modes

Choose one mode based on your operation target:

1. Interactive local operator:
   `uv run bub chat`
2. Channel service (Telegram/Discord):
   `uv run bub message`
3. Scheduler-only autonomous runtime:
   `uv run bub idle`

One-shot operation:

```bash
uv run bub run "summarize changes in this repo"
```

## 3) Message Channel Deployment

Enable channels in `.env` first.

Telegram:

```bash
BUB_TELEGRAM_ENABLED=true
BUB_TELEGRAM_TOKEN=123456:token
BUB_TELEGRAM_ALLOW_FROM='["123456789","your_username"]'
BUB_TELEGRAM_ALLOW_CHATS='["123456789","-1001234567890"]'
```

Discord:

```bash
BUB_DISCORD_ENABLED=true
BUB_DISCORD_TOKEN=discord_bot_token
BUB_DISCORD_ALLOW_FROM='["123456789012345678","your_discord_name"]'
BUB_DISCORD_ALLOW_CHANNELS='["123456789012345678"]'
```

Start channel service:

```bash
uv run bub message
```

## 4) Systemd Production Deployment

Use `./scripts/deploy-production.sh` for systemd-based process management.

**Why systemd**: journalctl log aggregation, auto-restart on failure, consistent dev/prod config.

```bash
./scripts/deploy-production.sh start bus                # Start bus
./scripts/deploy-production.sh start all                # Start all
./scripts/deploy-production.sh logs bus                 # Follow logs
./scripts/deploy-production.sh logs all                 # All component logs
./scripts/deploy-production.sh logs bus -n 50           # Last 50 lines
./scripts/deploy-production.sh status bus               # Check status
./scripts/deploy-production.sh stop bus                 # Stop cleanly
./scripts/deploy-production.sh stop all                 # Stop everything
./scripts/deploy-production.sh list                     # List running components
```

Features:
- Uses `systemd-run` with automatic cleanup
- Auto-restart on failure (`Restart=always`, 5s delay, max 3 restarts/min)
- Unit names persisted in `run/` directory
- Logs via `journalctl --user -u <unit-name>`

Do not run `uv run bub bus serve` directly — bypasses deployment, no journalctl logs. One-shot CLI commands (like `bub bus status`) are fine.

See `.agents/skills/deployment/SKILL.md` for full command reference.

## 5) Docker Compose Deployment

The repository already provides `Dockerfile`, `docker-compose.yml`, and `entrypoint.sh`.

Build and run:

```bash
docker compose up -d --build
docker compose logs -f app
```

Behavior in container:

- If `/workspace/startup.sh` exists, container starts `bub idle` in background, then executes `startup.sh`.
- Otherwise, container starts `bub message`.

Default mounts in `docker-compose.yml`:

- `${BUB_WORKSPACE_PATH:-.}:/workspace`
- `${BUB_HOME:-${HOME}/.bub}:/data`
- `${BUB_AGENT_HOME:-${HOME}/.agent}:/root/.agent`

## 6) Operational Checks

Health checklist:

1. Process is running:
   `ps aux | rg "bub (chat|message|idle)"`
2. Model key is loaded:
   `rg -n "BUB_MODEL|OPENROUTER_API_KEY|LLM_API_KEY" .env`
3. Channel flags are correct:
   `rg -n "BUB_TELEGRAM_ENABLED|BUB_DISCORD_ENABLED" .env`
4. Logs show channel startup:
   `uv run bub message` and confirm `channel.manager.start` output.

## 7) Safe Upgrade Procedure

```bash
git fetch --all --tags
git pull
uv sync
uv run ruff check .
uv run mypy
uv run pytest -q
```

Then restart your runtime (`chat`, `message`, or container service).
