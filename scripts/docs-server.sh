#!/bin/bash
# Serve MkDocs documentation with live reload via systemd-run
# Usage: ./scripts/docs-server.sh [start|stop|status|logs] [port]

set -e

PORT="${2:-8000}"
SERVICE_NAME="bub-docs"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

case "${1:-start}" in
    start)
        echo "📚 Starting MkDocs server..."
        echo "   URL: http://0.0.0.0:${PORT}"
        echo "   Live reload: enabled"
        echo "   Mermaid: enabled"
        echo ""

        cd "$(dirname "$SCRIPT_DIR")"

        systemd-run --user \
            --unit="${SERVICE_NAME}" \
            --description="Bub Documentation Server (MkDocs)" \
            --property=WorkingDirectory="$(pwd)" \
            --property=Environment="PYTHONUNBUFFERED=1" \
            --collect \
            uv run mkdocs serve --dev-addr "0.0.0.0:${PORT}" --watch docs

        echo ""
        echo "✅ Started! Open http://localhost:${PORT} in your browser"
        echo ""
        echo "Features:"
        echo "  • Live reload on file changes"
        echo "  • Mermaid diagram rendering"
        echo "  • Full-text search"
        echo "  • Auto-generated navigation"
        echo ""
        echo "Commands:"
        echo "  ./scripts/docs-server.sh status    # Check status"
        echo "  ./scripts/docs-server.sh logs      # View logs"
        echo "  ./scripts/docs-server.sh stop      # Stop"
        ;;

    stop)
        echo "🛑 Stopping documentation server..."
        systemctl --user stop "${SERVICE_NAME}" 2>/dev/null || true
        echo "✅ Stopped"
        ;;

    status)
        systemctl --user status "${SERVICE_NAME}" --no-pager
        ;;

    logs|log)
        journalctl --user -u "${SERVICE_NAME}" -f
        ;;

    *)
        echo "Bub Documentation Server (MkDocs)"
        echo ""
        echo "Usage: $0 [start|stop|status|logs] [port]"
        echo ""
        echo "Commands:"
        echo "  start [port]     - Start server (default: 8000)"
        echo "  stop             - Stop server"
        echo "  status           - Check service status"
        echo "  logs             - Follow logs"
        echo ""
        echo "Features:"
        echo "  • MkDocs Material with live reload"
        echo "  • Mermaid2 plugin for diagram rendering"
        echo "  • Directory-based navigation"
        echo "  • Full-text search"
        exit 1
        ;;
esac
