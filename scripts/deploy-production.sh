#!/bin/bash
# Production deployment example for Telegram + WebSocket architecture

set -e

echo "🚀 Bub Production Architecture Test"
echo "===================================="
echo ""

# Configuration
export BUB_BUS_HOST=${BUB_BUS_HOST:-localhost}
export BUB_BUS_PORT=${BUB_BUS_PORT:-7892}
export BUB_BUS_URL="ws://${BUB_BUS_HOST}:${BUB_BUS_PORT}"

echo "📋 Configuration:"
echo "   Bus Host: $BUB_BUS_HOST"
echo "   Bus Port: $BUB_BUS_PORT"
echo "   Bus URL: $BUB_BUS_URL"
echo ""

# Check if we have Telegram token
if [ -z "$BUB_BUS_TELEGRAM_TOKEN" ]; then
    echo "⚠️  Warning: BUB_BUS_TELEGRAM_TOKEN not set"
    echo "   Telegram integration will be disabled"
    echo "   To enable: export BUB_BUS_TELEGRAM_TOKEN=your_token"
    echo ""
fi

# Function to cleanup on exit
cleanup() {
    echo ""
    echo "🧹 Cleaning up..."
    if [ -n "$BUS_PID" ]; then
        echo "   Stopping bus server (PID: $BUS_PID)"
        kill $BUS_PID 2>/dev/null || true
        wait $BUS_PID 2>/dev/null || true
    fi
    if [ -n "$AGENT_PID" ]; then
        echo "   Stopping agent (PID: $AGENT_PID)"
        kill $AGENT_PID 2>/dev/null || true
        wait $AGENT_PID 2>/dev/null || true
    fi
    echo "✅ Cleanup complete"
}
trap cleanup EXIT

echo "🔧 Starting components..."
echo ""

# Terminal 1: Start WebSocket bus server (with Telegram if configured)
echo "🌐 Terminal 1: Starting WebSocket bus server..."
if [ -n "$BUB_BUS_TELEGRAM_TOKEN" ]; then
    echo "   With Telegram integration enabled"
    bub bus serve &
else
    echo "   Without Telegram (mock mode)"
    bub bus serve &
fi
BUS_PID=$!
echo "   PID: $BUS_PID"
echo ""

# Wait for server to start
sleep 3

# Check if server is running
if ! kill -0 $BUS_PID 2>/dev/null; then
    echo "❌ Bus server failed to start"
    exit 1
fi

echo "✅ Bus server is running"
echo ""

# Terminal 2: Start agent client
echo "🤖 Terminal 2: Starting agent client..."
BUB_BUS_URL="$BUB_BUS_URL" bub agent &
AGENT_PID=$!
echo "   PID: $AGENT_PID"
echo ""

# Wait for agent to connect
sleep 2

# Check if agent is running
if ! kill -0 $AGENT_PID 2>/dev/null; then
    echo "❌ Agent failed to start"
    exit 1
fi

echo "✅ Agent is running"
echo ""

echo "🎉 Production architecture is ready!"
echo ""
echo "Architecture:"
echo "   Telegram Users → bub bus serve → WebSocket → bub agent"
echo ""

if [ -n "$BUB_BUS_TELEGRAM_TOKEN" ]; then
    echo "📱 Send a message to your Telegram bot to test"
else
    echo "🧪 Running in mock mode (no Telegram)"
    echo "   Use: python tests/mock_telegram.py $BUB_BUS_URL"
    echo "   to simulate Telegram messages"
fi

echo ""
echo "Press Ctrl+C to stop all components"
echo ""

# Wait for Ctrl+C
wait
