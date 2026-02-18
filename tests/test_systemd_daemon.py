"""Test WebSocket bus pub/sub with mock Telegram client using systemd."""

import asyncio
import os
import subprocess
import sys
import time

from bub.channels.events import InboundMessage, OutboundMessage
from bub.bus.bus import AgentBusClient


def disable_proxy_env():
    """Disable proxy environment variables."""
    for key in list(os.environ.keys()):
        if key.lower() in ("http_proxy", "https_proxy", "all_proxy", "no_proxy"):
            del os.environ[key]


# Disable proxy at module load time
disable_proxy_env()


def run_systemd_daemon():
    """Run WebSocket server as systemd daemon."""
    print("🚀 Starting WebSocket bus server via systemd-run\n")

    # Create systemd unit for WebSocket bus server
    unit_name = "bub-test-wsbus.service"
    # Get the bub command from the virtual environment
    venv_path = os.path.dirname(os.path.dirname(sys.executable))
    bub_cmd = os.path.join(venv_path, "bin", "bub")
    if not os.path.exists(bub_cmd):
        # Try venv's bin directory structure
        bub_cmd = os.path.join(os.path.dirname(sys.executable), "bub")

    cmd = [
        bub_cmd,
        "bus",
        "serve",
    ]

    print(f"📝 Unit name: {unit_name}")
    print(f"🔧 Command: {bub_cmd} bus serve\n")

    # Run as systemd daemon
    result = subprocess.run(
        ["systemd-run", "--user", "--unit", unit_name, "--collect", *cmd],
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        print("❌ Failed to start systemd daemon:")
        print(f"   stdout: {result.stdout}")
        print(f"   stderr: {result.stderr}")
        return None

    # Extract unit name from output (format: "Running as unit: <name>; invocation ID: <id>")
    output = result.stdout.strip()
    if "Running as unit:" in output:
        unit_name = output.split("Running as unit:")[1].split(";")[0].strip()
    else:
        unit_name = "bub-test-wsbus.service"

    print("✅ Systemd daemon started")
    print(f"   Unit: {unit_name}\n")

    return unit_name


async def test_pubsub(unit_name: str):
    """Test pub/sub with mock Telegram client."""
    print("🧪 Starting WebSocket bus pub/sub test\n")

    # Connect test client
    print("1️⃣ Connecting test client...")
    server_url = "ws://localhost:7892"
    test_client = AgentBusClient(server_url)
    await test_client.connect()
    await test_client.initialize("test-client")
    print(f"✅ Test client connected to {server_url}")

    # Subscribe to inbound messages
    received_messages = []

    async def on_inbound(message: InboundMessage):
        received_messages.append(message)
        print(f"📨 Received: {message.channel} - {message.chat_id} - {message.content}")

    unsub_inbound = await test_client.on_inbound(on_inbound)

    # Subscribe to outbound messages
    received_outbound = []

    async def on_outbound(message: OutboundMessage):
        received_outbound.append(message)
        content_preview = message.content[:50] + "..." if len(message.content) > 50 else message.content
        print(f"📤 Outbound: {message.channel} - {message.chat_id} - {content_preview}")

    unsub_outbound = await test_client.on_outbound(on_outbound)

    print("👂 Listening for messages...")
    print("⏱️  Waiting 15 seconds for messages...\n")

    # Start mock Telegram client
    print("2️⃣ Starting mock Telegram client...")
    mock_telegram_proc = subprocess.Popen(
        [sys.executable, "tests/mock_telegram.py", server_url, "1.5"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    print("✅ Mock Telegram client started\n")

    # Wait for messages
    await asyncio.sleep(15)

    # Send test message to validate communication
    print("\n3️⃣ Sending test message to validate communication...")
    await test_client.publish_inbound(
        InboundMessage(
            channel="test",
            sender_id="test_user",
            chat_id="test_chat",
            content=",help",
        )
    )

    await asyncio.sleep(2)

    # Check results
    print("\n📊 Test Results:")
    print(f"   Inbound messages received: {len(received_messages)}")
    print(f"   Outbound messages received: {len(received_outbound)}")

    # Cleanup
    print("\n🧹 Cleaning up...")
    unsub_inbound()
    unsub_outbound()
    await test_client.disconnect()
    mock_telegram_proc.terminate()
    mock_telegram_proc.wait()

    return len(received_messages), len(received_outbound)


async def restart_and_validate(unit_name: str):
    """Restart systemd daemon and validate communication."""
    print(f"\n🔄 Restarting systemd unit: {unit_name}")

    # Stop the unit
    result = subprocess.run(
        ["systemctl", "--user", "stop", unit_name],
        capture_output=True,
        text=True,
    )
    time.sleep(1)

    # Start the unit again
    result = subprocess.run(
        ["systemctl", "--user", "start", unit_name],
        capture_output=True,
        text=True,
    )
    time.sleep(2)

    # Check status
    result = subprocess.run(
        ["systemctl", "--user", "is-active", unit_name],
        capture_output=True,
        text=True,
    )

    status = result.stdout.strip()
    print(f"✅ Unit status after restart: {status}")

    if status == "active":
        print("\n✅ Daemon restarted successfully, communication validated")
        return True
    else:
        print(f"\n❌ Daemon failed to restart, status: {status}")
        return False


async def main():
    """Main test function."""
    # Start systemd daemon
    unit_name = run_systemd_daemon()
    if not unit_name:
        print("❌ Failed to start systemd daemon")
        return

    # Wait for server to be ready
    time.sleep(3)

    # Run pub/sub test
    inbound_count, outbound_count = await test_pubsub(unit_name)

    # Restart and validate
    success = await restart_and_validate(unit_name)

    # Stop daemon
    print(f"\n🛑 Stopping systemd unit: {unit_name}")
    subprocess.run(
        ["systemctl", "--user", "stop", unit_name],
        capture_output=True,
    )

    print("\n✅ All tests complete")
    print(f"   Inbound messages: {inbound_count}")
    print(f"   Outbound messages: {outbound_count}")
    print(f"   Restart validation: {'PASS' if success else 'FAIL'}")


if __name__ == "__main__":
    asyncio.run(main())
