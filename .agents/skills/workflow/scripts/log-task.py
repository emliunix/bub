#!/usr/bin/env -S uv run --script
# /// script
# dependencies = []
# requires-python = ">=3.12"
# ///
"""Log work to a task file using two-phase commit.

Two-phase logging separates writing from formatting:
1. generate: Creates temp file for agent to write work log
2. commit: Reads temp file, formats, appends to task, cleans up

Usage:
    # Generate temp file (Phase 1)
    .agents/skills/workflow/scripts/log-task.py generate ./tasks/0-explore.md "Initial Analysis"
    # Returns: ./tmp-abc12345-log-content.md

    # Agent edits the temp file...

    # Commit log (Phase 2)
    .agents/skills/workflow/scripts/log-task.py commit ./tasks/0-explore.md "Initial Analysis" ./tmp-abc12345-log-content.md

Single-phase mode for quick logs:
    .agents/skills/workflow/scripts/log-task.py quick ./tasks/0-explore.md "Quick Log" "Fixed the bug"
"""

import argparse
import re
import sys
import uuid
from datetime import datetime
from pathlib import Path


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug.strip("-")


def generate_temp_template(title: str) -> str:
    """Generate the template for the temporary work log file."""
    return f"""# Work Log: {title}

## Facts
<!-- What was actually done (files modified, code written, tests run, etc.) -->
-

## Analysis
<!-- What problems were encountered, what approaches were tried, key decisions made -->
-

## Conclusion
<!-- Pass/fail/escalate status and why, next steps, blockers if any -->
Status: <!-- ok / blocked / escalate -->

<!-- Additional notes -->
"""


def format_work_log(title: str, content: str) -> str:
    """Format the work log entry with proper structure."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Extract sections from content
    facts_match = re.search(r"## Facts\s*(.*?)(?=## Analysis|$)", content, re.DOTALL)
    analysis_match = re.search(r"## Analysis\s*(.*?)(?=## Conclusion|$)", content, re.DOTALL)
    conclusion_match = re.search(r"## Conclusion\s*(.*?)(?=## |$)", content, re.DOTALL)

    facts = facts_match.group(1).strip() if facts_match else "<!-- No facts recorded -->"
    analysis = analysis_match.group(1).strip() if analysis_match else "<!-- No analysis recorded -->"
    conclusion = conclusion_match.group(1).strip() if conclusion_match else "<!-- No conclusion recorded -->"

    return f"""### [{timestamp}] {title}

**Facts:**
{facts}

**Analysis:**
{analysis}

**Conclusion:**
{conclusion}

---

"""


def cmd_generate(task_file: Path, title: str) -> None:
    """Generate subcommand: Create temp file for agent to write to."""
    if not task_file.exists():
        print(f"Error: Task file not found: {task_file}", file=sys.stderr)
        sys.exit(1)

    # Create temp file in workspace with UUID
    temp_filename = f"./tmp-{uuid.uuid4().hex[:8]}-log-content.md"
    temp_path = Path(temp_filename)

    template = generate_temp_template(title)
    temp_path.write_text(template, encoding="utf-8")

    # Print only the path (for scripting)
    print(temp_path)


def cmd_commit(task_file: Path, title: str, temp_file: Path) -> None:
    """Commit subcommand: Read temp file and append formatted log to task."""
    if not task_file.exists():
        print(f"Error: Task file not found: {task_file}", file=sys.stderr)
        sys.exit(1)

    if not temp_file.exists():
        print(f"Error: Temp file not found: {temp_file}", file=sys.stderr)
        sys.exit(1)

    # Read temp file content
    content = temp_file.read_text(encoding="utf-8")

    # Remove the title line since we'll use it in the formatted log
    content = re.sub(r"^# Work Log:.*?\n", "", content, count=1)

    # Format the log entry
    log_entry = format_work_log(title, content)

    # Read task file
    task_content = task_file.read_text(encoding="utf-8")

    # Check if Work Log section exists
    if "## Work Log" not in task_content:
        task_content += "\n\n## Work Log\n\n"

    # Append log entry
    task_content = task_content.rstrip() + "\n\n" + log_entry

    # Write back
    task_file.write_text(task_content, encoding="utf-8")

    # Clean up temp file
    temp_file.unlink()

    print(f"Work log committed to: {task_file}")


def cmd_quick(task_file: Path, title: str, content: str) -> None:
    """Quick subcommand: Directly log content without temp file."""
    if not task_file.exists():
        print(f"Error: Task file not found: {task_file}", file=sys.stderr)
        sys.exit(1)

    # Create minimal content
    temp_content = f"# Work Log\n\n## Facts\n{content}\n\n## Analysis\n-\n\n## Conclusion\nStatus: ok\n"

    # Format and commit directly
    log_entry = format_work_log(title, temp_content)

    task_content = task_file.read_text(encoding="utf-8")
    if "## Work Log" not in task_content:
        task_content += "\n\n## Work Log\n\n"

    task_content = task_content.rstrip() + "\n\n" + log_entry
    task_file.write_text(task_content, encoding="utf-8")

    print(f"Work log committed to: {task_file}")


def main():
    parser = argparse.ArgumentParser(
        description="Log work to a task file using two-phase commit",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
SUBCOMMANDS:

  generate TASK TITLE
    Creates a temp markdown file for you to write your work log.
    The temp file is created in the workspace (./tmp-{uuid}-log-content.md).
    Output: Path to temp file (print only).
    
    Example:
      .agents/skills/workflow/scripts/log-task.py generate ./tasks/0-explore.md "Analysis"

  commit TASK TITLE TEMP_FILE
    Reads the temp file, formats with timestamp, appends to task, deletes temp.
    This is Phase 2 - call after editing the temp file.
    
    Example:
      .agents/skills/workflow/scripts/log-task.py commit ./tasks/0-explore.md "Analysis" ./tmp-abc12345-log-content.md

  quick TASK TITLE CONTENT
    For simple logs, bypass temp file and commit directly.
    
    Example:
      .agents/skills/workflow/scripts/log-task.py quick ./tasks/0-explore.md "Fix" "Fixed the auth bug"

WORK LOG FORMAT:
  Each log entry includes:
  - Timestamp
  - Facts (what was done)
  - Analysis (decisions, problems)
  - Conclusion (status: ok/blocked/escalate)
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Subcommand to run")

    # generate subcommand
    gen_parser = subparsers.add_parser(
        "generate",
        help="Create temp file for writing work log",
        description="Creates a temp markdown file (./tmp-{uuid}-log-content.md) for agent to write work log. Prints path only.",
    )
    gen_parser.add_argument("task", help="Path to the task file")
    gen_parser.add_argument("title", help="Title for this work log entry")

    # commit subcommand
    commit_parser = subparsers.add_parser(
        "commit",
        help="Commit temp file to task",
        description="Reads temp file, formats with timestamp, appends to task, deletes temp file.",
    )
    commit_parser.add_argument("task", help="Path to the task file")
    commit_parser.add_argument("title", help="Title for this work log entry")
    commit_parser.add_argument("temp_file", help="Path to temp file from generate command")

    # quick subcommand
    quick_parser = subparsers.add_parser(
        "quick",
        help="Quick log without temp file",
        description="Directly log content without creating temp file. For simple one-line logs.",
    )
    quick_parser.add_argument("task", help="Path to the task file")
    quick_parser.add_argument("title", help="Title for this work log entry")
    quick_parser.add_argument("content", help="Content for Facts section")

    args = parser.parse_args()

    if args.command == "generate":
        cmd_generate(Path(args.task), args.title)
    elif args.command == "commit":
        cmd_commit(Path(args.task), args.title, Path(args.temp_file))
    elif args.command == "quick":
        cmd_quick(Path(args.task), args.title, args.content)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
