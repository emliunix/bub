#!/usr/bin/env python3
"""Smoke-test the workflow helper scripts (no pytest).

This script exercises the workflow skill CLIs end-to-end in a temporary workspace:
- create-kanban.py
- create-task.py
- update-kanban.py
- check-task.py
- log-task.py (validation)

It prints PASS on success and exits non-zero on failure.

Usage:
  uv run python scripts/test_workflow_helper_scripts.py
"""

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_SCRIPTS_DIR = REPO_ROOT / ".agents" / "skills" / "workflow" / "scripts"

CREATE_TASK = WORKFLOW_SCRIPTS_DIR / "create-task.py"
CREATE_KANBAN = WORKFLOW_SCRIPTS_DIR / "create-kanban.py"
UPDATE_KANBAN = WORKFLOW_SCRIPTS_DIR / "update-kanban.py"
LOG_TASK = WORKFLOW_SCRIPTS_DIR / "log-task.py"
CHECK_TASK = WORKFLOW_SCRIPTS_DIR / "check-task.py"


class SmokeTestError(RuntimeError):
    pass


def run(cmd: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=str(cwd), text=True, capture_output=True, check=False)


def must_ok(result: subprocess.CompletedProcess[str], *, context: str) -> None:
    if result.returncode == 0:
        return
    raise SmokeTestError(
        "\n".join(
            [
                f"FAILED: {context}",
                f"cmd: {' '.join(result.args) if isinstance(result.args, list) else result.args}",
                f"exit: {result.returncode}",
                "--- stdout ---",
                result.stdout.rstrip(),
                "--- stderr ---",
                result.stderr.rstrip(),
            ]
        )
    )


def parse_frontmatter(md: str) -> dict:
    if not md.startswith("---"):
        raise SmokeTestError("Missing YAML frontmatter")

    parts = md.split("---", 2)
    if len(parts) < 3:
        raise SmokeTestError("Invalid YAML frontmatter block")

    data = yaml.safe_load(parts[1]) or {}
    if not isinstance(data, dict):
        raise SmokeTestError("Frontmatter YAML did not parse to a mapping")

    return data


def main() -> int:
    for script in [CREATE_TASK, CREATE_KANBAN, UPDATE_KANBAN, LOG_TASK, CHECK_TASK]:
        if not script.exists():
            print(f"Error: missing script: {script}", file=sys.stderr)
            return 2

    with tempfile.TemporaryDirectory(prefix="bub-workflow-smoke-") as tmp:
        ws = Path(tmp)
        (ws / "tasks").mkdir(parents=True, exist_ok=True)

        # 1) Create kanban
        kanban = run(
            [
                "uv",
                "run",
                str(CREATE_KANBAN),
                "--title",
                "API Refactor",
                "--request",
                "Refactor the API layer",
                "--tasks-dir",
                "tasks",
            ],
            cwd=ws,
        )
        must_ok(kanban, context="create-kanban")
        kanban_rel = Path(kanban.stdout.strip())
        kanban_file = ws / kanban_rel
        if not kanban_file.exists():
            raise SmokeTestError(f"create-kanban did not create file: {kanban_file}")

        # 2) Create design task (and ensure refers includes kanban)
        task = run(
            [
                "uv",
                "run",
                str(CREATE_TASK),
                "--assignee",
                "Architect",
                "--expertise",
                "System Design,Python",
                "--title",
                "Design API",
                "--type",
                "design",
                "--kanban",
                str(kanban_rel),
                "--creator-role",
                "manager",
                "--tasks-dir",
                "tasks",
            ],
            cwd=ws,
        )
        must_ok(task, context="create-task")
        task_rel = Path(task.stdout.strip())
        task_file = ws / task_rel
        if not task_file.exists():
            raise SmokeTestError(f"create-task did not create file: {task_file}")

        task_front = parse_frontmatter(task_file.read_text(encoding="utf-8"))
        if task_front.get("kanban") != str(kanban_rel):
            raise SmokeTestError("task frontmatter kanban field mismatch")
        refers = task_front.get("refers")
        if not isinstance(refers, list) or str(kanban_rel) not in refers:
            raise SmokeTestError("task frontmatter refers must include kanban pointer")

        # 3) check-task output shape
        briefing = run(["uv", "run", str(CHECK_TASK), "--task", str(task_rel)], cwd=ws)
        must_ok(briefing, context="check-task")
        out = briefing.stdout
        if "# Agent Briefing: Architect" not in out:
            raise SmokeTestError("check-task missing expected header")
        if "**Task Type:** design" not in out:
            raise SmokeTestError("check-task missing Task Type")
        if "**Role:**" in out:
            raise SmokeTestError("check-task should not emit a **Role:** line")

        # 4) update-kanban adds task and sets current
        upd = run(
            [
                "uv",
                "run",
                str(UPDATE_KANBAN),
                "--kanban",
                str(kanban_rel),
                "--add-task",
                str(task_rel),
                "--set-current",
                str(task_rel),
                "--set-phase",
                "execute",
            ],
            cwd=ws,
        )
        must_ok(upd, context="update-kanban")

        kb_front = parse_frontmatter(kanban_file.read_text(encoding="utf-8"))
        if kb_front.get("type") != "kanban":
            raise SmokeTestError("kanban frontmatter type mismatch")
        if kb_front.get("phase") != "execute":
            raise SmokeTestError("kanban frontmatter phase not updated")
        if kb_front.get("current") != str(task_rel):
            raise SmokeTestError("kanban current not set")
        tasks_list = kb_front.get("tasks")
        if not isinstance(tasks_list, list) or str(task_rel) not in tasks_list:
            raise SmokeTestError("kanban tasks list missing task")

        # 5) log-task validation: corrupt markers, then attempt publish to review
        corrupted = task_file.read_text(encoding="utf-8").replace(
            "<!-- start workitems -->", "<!-- start workitems X -->"
        )
        task_file.write_text(corrupted, encoding="utf-8")

        quick_fail = run(
            [
                "uv",
                "run",
                str(LOG_TASK),
                "quick",
                str(task_rel),
                "Try publish",
                "Some content",
                "--role",
                "Architect",
                "--new-state",
                "review",
            ],
            cwd=ws,
        )
        if quick_fail.returncode == 0:
            raise SmokeTestError("log-task should have failed validation but succeeded")
        if "Missing Work Items block markers" not in (quick_fail.stderr + quick_fail.stdout):
            raise SmokeTestError("log-task validation did not emit expected error")

    print("PASS: workflow helper scripts smoke-test")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SmokeTestError as e:
        print(str(e), file=sys.stderr)
        raise SystemExit(1)
