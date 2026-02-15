#!/bin/bash
# Serve MkDocs with live reload
# Usage: ./scripts/docs-serve.sh [port]

PORT="${1:-8000}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

cd "$(dirname "$SCRIPT_DIR")"

echo "📚 Starting MkDocs server..."
echo "   URL: http://localhost:${PORT}"
echo "   Live reload: enabled"
echo "   Mermaid: enabled"
echo ""

uv run mkdocs serve --dev-addr "0.0.0.0:${PORT}"
