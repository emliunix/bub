## File & Directory Reference

### Repository Layout

- Core code: `src/bub/`
- Tests: `tests/`
- Docs: `docs/`
- Journals: `journal/`
- Scripts: `scripts/`
- Change plans: `changes/`

For a component-wise view (bus/tape/agents/channels/CLI), see `docs/components.md`.

### Docs & Styles Index

See `docs/index.md` for documentation and style guide index.

### Build/Test Commands

Repo uses `uv` + Ruff + mypy + pytest. `uv` is at `~/.local/bin/uv`.

Always use `uv run` to execute Python commands. **Never set `PYTHONPATH` manually.**

### Operations Guide

See `docs/deployment.md` and `.agents/skills/deployment/SKILL.md`.

## Core Principles

### Skill-First Checking

**Before starting any work**, check relevant skills and read them.

Skills are **compositional**. A single task often requires combining multiple perspectives — e.g., writing docs needs the `docs` skill (formatting, mermaid) *and* the `scripts-docs` skill (last-modified tracking). Construct a multi-perspective view by loading all relevant skills before proceeding.

**Entry point**: `.agents/skills/skill-management/SKILL.md`

**Relevance**:

| Criterion | Examples |
|-----------|----------|
| **Domain** | docs, testing, deployment, bus |
| **Technology** | mkdocs, pytest, systemd, websockets |
| **File type** | .md → docs skill, .py tests → testing skill |
| **Operation** | serving docs → docs skill, deploying → deployment skill |
| **Project Lifecycle** | code change → change-plan skill, things changed → journal skill |

**Mandate**: If a skill exists for your domain/tech/operation, read it first. Skills contain authoritative conventions that prevent errors.
