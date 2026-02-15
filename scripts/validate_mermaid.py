#!/usr/bin/env python3
"""Extract and validate mermaid diagrams from markdown."""

import re
import subprocess
import sys
from pathlib import Path


def extract_diagrams_from_dir(diagram_dir: Path) -> list[tuple[str, str]]:
    """Extract mermaid diagrams from architecture directory.

    Returns list of (title, diagram_content) tuples.
    """
    diagrams = []

    for md_file in sorted(diagram_dir.glob("*.md")):
        if md_file.name == "index.md":
            continue

        content = md_file.read_text()

        # Extract title (first # line)
        title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
        title = title_match.group(1) if title_match else md_file.stem

        # Extract mermaid diagram
        pattern = r"```mermaid\n(.*?)```"
        matches = re.findall(pattern, content, re.DOTALL)

        for match in matches:
            diagrams.append((title, match))

    return diagrams


def validate_diagram(diagram_content: str, output_file: Path) -> bool:
    """Validate a mermaid diagram by rendering it.

    Returns True if successful, False otherwise.
    """
    # Write diagram to temp file
    temp_file = output_file.with_suffix(".mmd")
    temp_file.write_text(diagram_content.strip())

    try:
        # Try to render with mermaid-cli
        result = subprocess.run(
            ["mmdc", "-i", str(temp_file), "-o", str(output_file), "-b", "transparent"],
            capture_output=True,
            text=True,
            timeout=30,
        )

        if result.returncode == 0:
            print(f"✓ Valid: {output_file.name}")
            return True
        else:
            print(f"✗ Invalid: {output_file.name}")
            print(f"  Error: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"✗ Timeout: {output_file.name}")
        return False
    except FileNotFoundError:
        print("✗ mmdc not found. Install with: npm install -g @mermaid-js/mermaid-cli")
        return False
    finally:
        # Clean up temp file
        if temp_file.exists():
            temp_file.unlink()


def main():
    diagram_dir = Path(__file__).parent.parent / "docs" / "architecture"
    output_dir = Path(__file__).parent.parent / "docs" / "mermaid-output"

    print(f"Extracting diagrams from: {diagram_dir}")
    print(f"Output directory: {output_dir}")
    print()

    diagrams = extract_diagrams_from_dir(diagram_dir)
    print(f"Found {len(diagrams)} diagrams\n")

    output_dir.mkdir(exist_ok=True)

    success_count = 0
    for i, (title, content) in enumerate(diagrams, 1):
        safe_title = re.sub(r"[^\w\-]", "_", title.lower())[:50]
        output_file = output_dir / f"{i:02d}_{safe_title}.svg"

        print(f"{i}. {title}")
        if validate_diagram(content, output_file):
            success_count += 1
        print()

    print(f"Results: {success_count}/{len(diagrams)} diagrams valid")

    if success_count < len(diagrams):
        sys.exit(1)


if __name__ == "__main__":
    main()
