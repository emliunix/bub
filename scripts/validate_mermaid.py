#!/usr/bin/env python3
"""Extract and validate mermaid diagrams from markdown.

Usage:
    validate_mermaid.py [file]

If no file is provided, validates all diagrams in docs/architecture/.
"""

import argparse
import re
import subprocess
import sys
from pathlib import Path


def extract_diagrams_from_file(md_file: Path) -> list[tuple[str, str, str]]:
    """Extract mermaid diagrams from a markdown file.

    Returns list of (source, title, diagram_content) tuples.
    """
    diagrams = []

    if not md_file.exists():
        print(f"Error: File not found: {md_file}")
        return diagrams

    content = md_file.read_text()

    # Extract title (first # line)
    title_match = re.search(r"^# (.+)$", content, re.MULTILINE)
    title = title_match.group(1) if title_match else md_file.stem

    # Extract mermaid diagram
    pattern = r"```mermaid\n(.*?)```"
    matches = re.findall(pattern, content, re.DOTALL)

    for match in matches:
        diagrams.append((str(md_file), title, match))

    return diagrams


def extract_diagrams_from_dir(diagram_dir: Path) -> list[tuple[str, str, str]]:
    """Extract mermaid diagrams from architecture directory.

    Returns list of (source, title, diagram_content) tuples.
    """
    diagrams = []

    for md_file in sorted(diagram_dir.glob("*.md")):
        if md_file.name == "index.md":
            continue

        diagrams.extend(extract_diagrams_from_file(md_file))

    return diagrams


def validate_diagram(diagram_content: str, output_file: Path) -> tuple[bool, str]:
    """Validate a mermaid diagram by rendering it.

    Returns (success, error_message) tuple.
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
            return True, ""
        else:
            return False, result.stderr
    except subprocess.TimeoutExpired:
        return False, "Timeout after 30s"
    except FileNotFoundError:
        return False, "mmdc not found. Install with: npm install -g @mermaid-js/mermaid-cli"
    finally:
        # Clean up temp file
        if temp_file.exists():
            temp_file.unlink()


def main():
    parser = argparse.ArgumentParser(description="Validate mermaid diagrams in markdown files")
    parser.add_argument("file", nargs="?", help="Specific markdown file to validate (optional)")
    parser.add_argument("-o", "--output", type=Path, help="Output directory for rendered SVGs")
    args = parser.parse_args()

    if args.file:
        # Validate specific file
        md_file = Path(args.file)
        diagrams = extract_diagrams_from_file(md_file)
        source_desc = str(md_file)
    else:
        # Validate all files in architecture directory
        diagram_dir = Path(__file__).parent.parent / "docs" / "architecture"
        diagrams = extract_diagrams_from_dir(diagram_dir)
        source_desc = str(diagram_dir)

    if args.output:
        output_dir = args.output
    else:
        output_dir = Path(__file__).parent.parent / "docs" / "mermaid-output"

    print(f"Extracting diagrams from: {source_desc}")
    print(f"Output directory: {output_dir}")
    print()

    if not diagrams:
        print("No mermaid diagrams found")
        return

    print(f"Found {len(diagrams)} diagrams\n")

    output_dir.mkdir(exist_ok=True, parents=True)

    success_count = 0
    for i, (source, title, content) in enumerate(diagrams, 1):
        # Create a unique filename based on source and index
        source_name = Path(source).stem
        safe_title = re.sub(r"[^\w\-]", "_", f"{source_name}_{title}".lower())[:50]
        output_file = output_dir / f"{i:02d}_{safe_title}.svg"

        print(f"{i}. [{source_name}] {title}")
        success, error = validate_diagram(content, output_file)
        if success:
            print(f"   ✓ Valid: {output_file.name}")
            success_count += 1
        else:
            print(f"   ✗ Invalid: {error}")
        print()

    print(f"Results: {success_count}/{len(diagrams)} diagrams valid")

    if success_count < len(diagrams):
        sys.exit(1)


if __name__ == "__main__":
    main()
