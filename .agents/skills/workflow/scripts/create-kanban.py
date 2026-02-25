#!/usr/bin/env -S uv run --script
# /// script
# dependencies = []
# requires-python = ">=3.12"
# ///
"""Create a new kanban file with validated YAML header.

Usage:
    .agents/skills/workflow/scripts/create-kanban.py --title "API Refactor" --request "Refactor the API layer"
    .agents/skills/workflow/scripts/create-kanban.py -t "Bug Fix" -r "Fix critical authentication bug"

The script will:
1. Validate required fields
2. Generate the next sequential ID
3. Create the kanban file with proper YAML header
4. Optionally create initial exploration task
5. Return the file path
"""

import argparse
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def slugify(text: str) -> str:
    """Convert text to URL-friendly slug."""
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[-\s]+", "-", slug)
    return slug.strip("-")


def get_next_id(tasks_dir: Path) -> int:
    """Get the next sequential ID from existing files."""
    if not tasks_dir.exists():
        return 0

    max_id = -1
    for f in tasks_dir.iterdir():
        if f.is_file() and f.suffix == ".md":
            match = re.match(r"^(\d+)-", f.name)
            if match:
                file_id = int(match.group(1))
                max_id = max(max_id, file_id)

    return max_id + 1


def generate_kanban_header(title: str, request: str, tasks: list[str]) -> str:
    """Generate the YAML header for a kanban file."""
    header = "---\n"
    header += f"type: kanban\n"
    header += f"title: {title}\n"
    header += f"request: {request}\n"
    header += f"created: {datetime.now().isoformat()}\n"
    header += f"phase: exploration\n"
    header += f"current: null\n"
    header += f"tasks: {tasks}\n"
    header += "---\n"
    return header


def generate_kanban_content() -> str:
    """Generate the kanban body content."""
    content = "\n# Kanban: Workflow Tracking\n\n"
    content += "## Plan Adjustment Log\n"
    content += "<!-- Manager logs plan adjustments here -->\n\n"
    return content


def create_exploration_task(tasks_dir: Path, kanban_path: Path, kanban_request: str) -> str:
    """Create initial exploration task using create-task.py."""
    try:
        result = subprocess.run(
            [
                "python3",
                ".agents/skills/workflow/scripts/create-task.py",
                "--role",
                "Architect",
                "--expertise",
                "System Design,Domain Analysis,Code Exploration",
                "--skills",
                "code-reading",
                "--title",
                "Explore Request",
                "--type",
                "exploration",
                "--priority",
                "high",
                "--kanban",
                str(kanban_path),
                "--creator-role",
                "manager",
                "--description",
                f"Explore and analyze: {kanban_request}",
            ],
            capture_output=True,
            text=True,
            cwd=Path.cwd(),
        )
        if result.returncode == 0:
            return result.stdout.strip()
        else:
            print(f"Warning: Failed to create exploration task: {result.stderr}", file=sys.stderr)
            return ""
    except Exception as e:
        print(f"Warning: Could not create exploration task: {e}", file=sys.stderr)
        return ""


def main():
    parser = argparse.ArgumentParser(
        description="Create a new kanban file with validated YAML header",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  .agents/skills/workflow/scripts/create-kanban.py --title "API Refactor" --request "Refactor the API layer"
  .agents/skills/workflow/scripts/create-kanban.py -t "Bug Fix" -r "Fix critical authentication bug"
        """,
    )

    parser.add_argument("--title", "-t", required=True, help="Kanban title (used for filename)")
    parser.add_argument("--request", "-r", required=True, help="Original user request/description")
    parser.add_argument("--no-exploration", action="store_true", help="Skip creating initial exploration task")
    parser.add_argument("--tasks-dir", default="./tasks", help="Directory for task files (default: ./tasks)")

    args = parser.parse_args()

    # Ensure tasks directory exists
    tasks_dir = Path(args.tasks_dir)
    tasks_dir.mkdir(parents=True, exist_ok=True)

    # Calculate what the kanban ID will be
    # If we create an exploration task first, kanban will be ID+1
    next_id = get_next_id(tasks_dir)
    kanban_id = next_id if args.no_exploration else next_id + 1
    slug = slugify(args.title)
    filename = f"{kanban_id}-kanban-{slug}.md"
    kanban_path = tasks_dir / filename

    # Create exploration task first (to get proper ID sequencing)
    exploration_task = ""
    if not args.no_exploration:
        exploration_task = create_exploration_task(tasks_dir, kanban_path, args.request)

    # Generate kanban ID and filename
    kanban_id = get_next_id(tasks_dir)
    filename = f"{kanban_id}-kanban-{slug}.md"
    filepath = tasks_dir / filename

    # Tasks list (exploration task if created)
    tasks = [exploration_task] if exploration_task else []

    # Generate file content
    header = generate_kanban_header(title=args.title, request=args.request, tasks=tasks)
    body = generate_kanban_content()

    # Write file
    filepath.write_text(header + body, encoding="utf-8")

    # Update exploration task with kanban reference if created
    if exploration_task:
        try:
            # Read exploration task and add 'refers' to kanban
            exp_path = Path(exploration_task)
            if exp_path.exists():
                content = exp_path.read_text(encoding="utf-8")
                # Update refers field to include kanban
                content = content.replace("refers: []", f"refers: [{filename}]")
                exp_path.write_text(content, encoding="utf-8")

                # Update kanban to point to current task
                kb_content = filepath.read_text(encoding="utf-8")
                kb_content = kb_content.replace("current: null", f"current: {exploration_task.split('/')[-1]}")
                filepath.write_text(kb_content, encoding="utf-8")
        except Exception as e:
            print(f"Warning: Could not update task references: {e}", file=sys.stderr)

    # Output the filepath
    print(filepath)


if __name__ == "__main__":
    main()
