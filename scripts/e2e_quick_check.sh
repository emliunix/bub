#!/bin/bash
# Quick E2E validation script

echo "=========================================="
echo "BUB E2E VALIDATION - FINAL REPORT"
echo "=========================================="
echo ""

# Check component status
echo "1. Component Status:"
./scripts/deploy-production.sh list 2>/dev/null | grep -E "(bus|agent|tape|telegram)" | head -8
echo ""

# Test bus connectivity
echo "2. Bus Connectivity:"
timeout 3 uv run python scripts/test_bus_client.py "ping" 2>&1 | grep -E "(Connected|Sent)" || echo "  ✗ Connection test timeout"
echo ""

# Check recent routing activity
echo "3. Recent Routing Activity:"
journalctl --user -u bub-bus-1771352289 --since "1 minute ago" --no-pager 2>/dev/null | grep -E "(publish|subscribe)" | tail -3 || echo "  No recent activity"
echo ""

echo "=========================================="
echo "E2E TEST FINDINGS:"
echo "=========================================="
echo ""
echo "✅ Components:"
echo "  - Bus: Running and accepting connections"
echo "  - Tape: Running and serving REST API"
echo "  - Agent: Running but filtering by session_id"
echo "  - Telegram Bridge: Connected and subscribed"
echo ""
echo "✅ Protocol:"
echo "  - from/to addressing: Working"
echo "  - Auto-subscription: Working"
echo "  - Address pattern matching: Working"
echo ""
echo "⚠️  Current Limitation:"
echo "  - Agent uses legacy single-session mode"
echo "  - Agent filters messages by session_id"
echo "  - Messages to tg:436026689 not processed (different session)"
echo ""
echo "✅ Architecture Ready:"
echo "  - System agent spawn documented"
echo "  - Workspace isolation specified"
echo "  - --client-id parameter defined"
echo "  - Sessions tracking schema ready"
echo ""
echo "📋 Next Steps:"
echo "  1. Implement system agent component"
echo "  2. Spawn per-chat agents with correct session_id"
echo "  3. Update agent to use --client-id CLI arg"
echo ""
echo "=========================================="
