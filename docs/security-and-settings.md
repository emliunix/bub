# Security & Configuration

## Security

- Use `.env` for secrets; never commit keys.
- Validate Telegram allowlists before enabling production bots.
- Never log sensitive data.

## Settings (Env Prefixes)

| Prefix | Settings | Examples |
|--------|----------|----------|
| `BUB_TAPE_` | Tape settings | `BUB_TAPE_HOME`, `BUB_TAPE_NAME` |
| `BUB_BUS_` | Bus settings | `BUB_BUS_PORT`, `BUB_BUS_TELEGRAM_TOKEN` |
| `BUB_` | Chat settings | `BUB_MODEL`, `BUB_MAX_STEPS` |
