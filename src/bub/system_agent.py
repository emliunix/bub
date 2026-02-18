#!/usr/bin/env python3
"""System Agent - Spawns conversation agents via systemd.

This agent runs as a system service and handles spawn requests from
the telegram bridge or other clients to create new conversation agents.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import subprocess
import uuid
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from loguru import logger

from bub.bus.bus import AgentBusClient
from bub.config.settings import AgentSettings

# Load environment variables from .env file
# Try to find .env file in project root (3 levels up from this file)
project_root = Path(__file__).parent.parent.parent
env_file = project_root / ".env"
if env_file.exists():
    load_dotenv(dotenv_path=env_file)
    logger.debug("system.agent.loaded_env file={}".format(env_file))
else:
    load_dotenv()  # Fallback to default behavior
    logger.debug("system.agent.loaded_env default")


class SystemAgent:
    """System agent that spawns conversation agents."""

    def __init__(self, bus_url: str = "ws://localhost:7892") -> None:
        self.bus_url = bus_url
        self.client: AgentBusClient | None = None
        # Use project-local run directory for permissions
        self.run_dir = Path(__file__).parent.parent.parent / "run"
        self.sessions_path = self.run_dir / "sessions.json"
        self.workspaces_root = self.run_dir / "workspaces"
        self._running = False
        # Track background tasks to prevent garbage collection
        self._background_tasks: set[asyncio.Task[Any]] = set()
        # Lock to protect sessions data from race conditions between concurrent spawn tasks
        self._sessions_lock = asyncio.Lock()

    async def start(self) -> None:
        """Start the system agent."""
        logger.info("system.agent.starting bus_url={}", self.bus_url)

        # Ensure directories exist
        self.workspaces_root.mkdir(parents=True, exist_ok=True)

        # Initialize sessions file
        await self._load_sessions()

        # Connect to bus
        self.client = AgentBusClient(self.bus_url, auto_reconnect=True)
        await self.client.connect()
        await self.client.initialize("agent:system")

        # Subscribe to spawn requests with handler
        await self.client.subscribe("system:*", self._handle_message)

        self._running = True
        logger.info("system.agent.started")

        # Keep running
        while self._running:
            await asyncio.sleep(1)

    async def stop(self) -> None:
        """Stop the system agent."""
        logger.info("system.agent.stopping")
        self._running = False
        if self.client:
            await self.client.disconnect()
        logger.info("system.agent.stopped")

    async def _load_sessions(self) -> dict[str, Any]:
        """Load sessions from file (acquires lock)."""
        async with self._sessions_lock:
            return await self._load_sessions_internal()

    async def _load_sessions_internal(self) -> dict[str, Any]:
        """Load sessions from file (internal, assumes lock is held)."""
        if self.sessions_path.exists():
            try:
                # Use asyncio.to_thread to avoid blocking
                def _load():
                    with open(self.sessions_path) as f:
                        return json.load(f)

                data: dict[str, Any] = await asyncio.to_thread(_load)
                logger.debug("system.agent.sessions_loaded count={}", len(data.get("sessions", {})))
                return data
            except Exception as e:
                logger.error("system.agent.sessions_load_failed error={}", e)

        # Initialize empty sessions
        data = {"version": "1.0", "updated_at": self._now(), "sessions": {}}
        await self._save_sessions_internal(data)
        return data

    async def _save_sessions(self, data: dict[str, Any]) -> None:
        """Save sessions to file (acquires lock)."""
        async with self._sessions_lock:
            await self._save_sessions_internal(data)

    async def _save_sessions_internal(self, data: dict[str, Any]) -> None:
        """Save sessions to file (internal, assumes lock is held)."""
        data["updated_at"] = self._now()
        try:
            # Use asyncio.to_thread to avoid blocking
            def _save():
                with open(self.sessions_path, "w") as f:
                    json.dump(data, f, indent=2)

            await asyncio.to_thread(_save)
        except Exception as e:
            logger.error("system.agent.sessions_save_failed error={}", e)

    def _now(self) -> str:
        """Get current timestamp."""
        from datetime import UTC, datetime

        return datetime.now(UTC).isoformat()

    async def _handle_message(self, topic: str, payload: dict[str, Any]) -> None:
        """Handle incoming messages."""
        msg_type = payload.get("type", "")

        if msg_type == "spawn_request":
            # Spawn the request processing as a background task so we don't block
            # other requests while waiting for systemd to start the agent
            task = asyncio.create_task(self._handle_spawn_agent(topic, payload))
            self._background_tasks.add(task)
            task.add_done_callback(self._background_tasks.discard)
        else:
            logger.debug("system.agent.unknown_message_type type={}", msg_type)

    def _generate_agent_id(self, workspace: Path) -> str:
        """Generate deterministic agent ID from workspace path.

        Uses SHA256 hash of workspace path to ensure:
        1. Same workspace always gets same agent ID
        2. Only one agent per workspace at a time
        3. Predictable naming for systemd unit management
        """
        workspace_str = str(workspace)
        hash_digest = hashlib.sha256(workspace_str.encode()).hexdigest()[:12]
        return f"agent:worker-{hash_digest}"

    async def _is_agent_running(self, client_id: str) -> bool:
        """Check if agent systemd unit is active."""
        # Extract worker_id from client_id (agent:worker-xxxx -> worker-xxxx)
        worker_id = client_id.replace("agent:", "")
        unit_name = f"bub-agent-{worker_id}"

        try:
            # Use asyncio.to_thread to avoid blocking
            def _check():
                return subprocess.run(
                    ["systemctl", "--user", "is-active", unit_name], capture_output=True, text=True, timeout=5
                )

            result: subprocess.CompletedProcess[str] = await asyncio.to_thread(_check)
            is_active: bool = result.returncode == 0 and result.stdout.strip() == "active"
            logger.debug("system.agent.systemd_check unit={} active={}", unit_name, is_active)
            return is_active
        except Exception as e:
            logger.error("system.agent.systemd_check_error unit={} error={}", unit_name, e)
            return False

    async def _handle_spawn_agent(self, topic: str, payload: dict[str, Any]) -> None:
        """Handle spawn agent request."""
        content = payload.get("content", {})
        chat_id = content.get("chat_id", "")
        channel = content.get("channel", "telegram")
        channel_type = content.get("channel_type", channel)  # Fallback to channel for backward compatibility
        requester = payload.get("from", "")

        # Construct talkto from channel and chat_id
        talkto = f"{channel}:{chat_id}"

        logger.info("system.agent.spawn_request talkto={} chat_id={} channel={}", talkto, chat_id, channel)

        try:
            # Create workspace (deterministic path) - outside lock as it's filesystem operation
            workspace = self.workspaces_root / f"{channel}:{chat_id}"
            workspace.mkdir(parents=True, exist_ok=True)

            # Generate deterministic client_id from workspace
            client_id = self._generate_agent_id(workspace)
            logger.info("system.agent.generated_id workspace={} client_id={}", workspace, client_id)

            logger.debug("system.agent.waiting_for_sessions_lock client_id={}", client_id)
            # Acquire lock for the entire check-update-spawn sequence to prevent race conditions
            async with self._sessions_lock:
                logger.debug("system.agent.acquired_sessions_lock client_id={}", client_id)
                # Check if agent already exists and is running
                logger.debug("system.agent.loading_sessions client_id={}", client_id)
                sessions_data = await self._load_sessions_internal()
                logger.debug("system.agent.sessions_loaded_data client_id={}", client_id)

                if client_id in sessions_data.get("sessions", {}):
                    session = sessions_data["sessions"][client_id]

                    # Proactively check systemd status
                    if await self._is_agent_running(client_id):
                        logger.info("system.agent.already_running client_id={}", client_id)
                        # Update last_activity
                        session["last_activity"] = self._now()
                        await self._save_sessions_internal(sessions_data)
                        # Send success response with existing agent
                        await self._send_spawn_response(requester, client_id, True)
                        return
                    else:
                        # Agent in sessions but not running - clean up and respawn
                        logger.warning("system.agent.stale_session client_id={} - will respawn", client_id)
                        # Remove stale session entry
                        del sessions_data["sessions"][client_id]

                # Extract worker_id from client_id (agent:worker-xxxx -> worker-xxxx)
                worker_id = client_id.replace("agent:", "")

                # Update sessions with new agent
                sessions_data["sessions"][client_id] = {
                    "client_id": client_id,
                    "chat_id": chat_id,
                    "channel": channel,
                    "channel_type": channel_type,
                    "talkto": talkto,
                    "workspace": str(workspace),
                    "systemd_unit": f"bub-agent-{worker_id}",
                    "status": "spawning",
                    "created_at": self._now(),
                    "last_activity": self._now(),
                }
                await self._save_sessions_internal(sessions_data)

            # Release lock during the long-running systemd spawn operation
            # Spawn agent via systemd
            await self._spawn_agent_process(worker_id, client_id, talkto, workspace, channel_type)
            logger.debug("system.agent.spawn_process_completed client_id={}", client_id)

            # Re-acquire lock to update status
            logger.debug("system.agent.reacquiring_lock_for_status client_id={}", client_id)
            async with self._sessions_lock:
                logger.debug("system.agent.acquired_lock_for_status client_id={}", client_id)
                sessions_data = await self._load_sessions_internal()
                if client_id in sessions_data.get("sessions", {}):
                    sessions_data["sessions"][client_id]["status"] = "running"
                    await self._save_sessions_internal(sessions_data)
                    logger.debug("system.agent.status_updated_to_running client_id={}", client_id)

            # Send response back to requester
            await self._send_spawn_response(requester, client_id, True)

            logger.info("system.agent.spawned client_id={} talkto={}", client_id, talkto)

        except Exception as e:
            logger.exception("system.agent.spawn_failed")
            await self._send_spawn_response(requester, "", False, str(e))

    async def _spawn_agent_process(
        self, worker_id: str, client_id: str, talkto: str, workspace: Path, channel_type: str = "telegram"
    ) -> None:
        """Spawn agent process via systemd."""
        unit_name = f"bub-agent-{worker_id}"

        # Load settings to get API key and other config
        # Settings are loaded from env vars with BUB_ prefix
        settings = AgentSettings()

        # Build environment variables to pass via --setenv
        # AgentSettings uses BUB_AGENT_ prefix
        env_vars: dict[str, str] = {
            "BUB_BUS_URL": self.bus_url,
            "BUB_AGENT_BUS_URL": self.bus_url,  # For AgentSettings
        }

        # Pass API key from settings if available
        api_key = settings.api_key or settings.resolved_api_key
        if api_key:
            env_vars["BUB_AGENT_API_KEY"] = api_key
            logger.debug("system.agent.passing_api_key")
        else:
            logger.warning("system.agent.no_api_key_configured")

        # Pass other agent settings if they differ from defaults
        if settings.model:
            env_vars["BUB_AGENT_MODEL"] = settings.model
        if settings.api_base:
            env_vars["BUB_AGENT_API_BASE"] = settings.api_base
        if settings.max_tokens != 1024:  # Only pass if not default
            env_vars["BUB_AGENT_MAX_TOKENS"] = str(settings.max_tokens)
        if settings.max_steps != 20:  # Only pass if not default
            env_vars["BUB_AGENT_MAX_STEPS"] = str(settings.max_steps)

        # Build systemd-run command with --setenv for each var
        cmd = [
            "systemd-run",
            "--user",
            "--unit",
            unit_name,
            "--property",
            f"WorkingDirectory={workspace}",
        ]

        # Add --setenv for each environment variable
        for var, value in env_vars.items():
            cmd.extend(["--setenv", f"{var}={value}"])

        cmd.extend([
            "bub",
            "agent",
            "--client-id",
            client_id,
            "--talkto",
            talkto,
            "--workspace",
            str(workspace),
            "--reply-type",
            channel_type,
        ])

        logger.info("system.agent.spawning_process cmd={}", " ".join(cmd))

        # Use async subprocess to avoid blocking the event loop
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        try:
            stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=30.0)
        except asyncio.TimeoutError:
            process.kill()
            await process.wait()
            raise RuntimeError("Timeout waiting for systemd-run to complete")

        if process.returncode != 0:
            stderr_str = stderr.decode("utf-8") if stderr else ""

            # Handle case where unit already exists - stop it and retry once
            if "already loaded" in stderr_str.lower() or "already exists" in stderr_str.lower():
                logger.warning("system.agent.unit_already_exists unit={} - stopping and retrying", unit_name)
                try:
                    # Stop the existing unit
                    stop_result = await asyncio.to_thread(
                        lambda: subprocess.run(
                            ["systemctl", "--user", "stop", unit_name], capture_output=True, text=True, timeout=10
                        )
                    )
                    if stop_result.returncode == 0:
                        logger.info("system.agent.stopped_existing_unit unit={}", unit_name)
                        # Wait a moment for the unit to fully stop
                        await asyncio.sleep(0.5)
                        # Retry spawn once
                        return await self._spawn_agent_process(worker_id, client_id, talkto, workspace, channel_type)
                    else:
                        logger.error(
                            "system.agent.failed_to_stop_existing_unit unit={} stderr={}", unit_name, stop_result.stderr
                        )
                except Exception as e:
                    logger.error("system.agent.error_stopping_existing_unit unit={} error={}", unit_name, e)

            logger.error("system.agent.spawn_failed stderr={}", stderr_str)
            raise RuntimeError(f"Failed to spawn agent: {stderr_str}")

        stdout_str = stdout.decode("utf-8") if stdout else ""
        logger.info("system.agent.spawned_process unit={} output={}", unit_name, stdout_str.strip())

    async def _send_spawn_response(self, to: str, client_id: str, success: bool, error: str | None = None) -> None:
        """Send spawn response back to requester."""
        if not self.client:
            return

        payload: dict[str, Any] = {
            "messageId": f"msg_{uuid.uuid4().hex}",
            "type": "spawn_result",
            "from": "agent:system",
            "timestamp": self._now(),
            "content": {
                "success": success,
                "client_id": client_id,
            },
        }

        if error:
            payload["content"]["error"] = error

        # Send via bus
        if self.client is None:
            logger.error("system.agent.spawn_response_failed error=client_not_initialized")
            return

        try:
            await self.client.send_message(to=to, payload=payload)
            logger.info("system.agent.spawn_response_sent to={} success={}", to, success)
        except Exception as e:
            logger.error("system.agent.spawn_response_failed error={}", e)


async def main() -> None:
    """Main entry point."""
    agent = SystemAgent()

    try:
        await agent.start()
    except KeyboardInterrupt:
        logger.info("system.agent.interrupted")
    finally:
        await agent.stop()


if __name__ == "__main__":
    asyncio.run(main())

if __name__ == "__main__":
    asyncio.run(main())
