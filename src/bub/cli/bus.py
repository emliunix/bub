"""Bus CLI commands."""

from __future__ import annotations

import asyncio

import typer
from loguru import logger

from bub.channels.wsbus import AgentBusServer
from bub.config import BusSettings
from bub.logging_utils import configure_logging

bus_app = typer.Typer(help="Bus operations")


@bus_app.command("serve")
def bus_serve() -> None:
    """Start the WebSocket bus server."""
    configure_logging(profile="chat")
    bus_settings = BusSettings()

    logger.info(
        "bus.serve starting host={} port={} telegram={}",
        bus_settings.host,
        bus_settings.port,
        bus_settings.telegram_enabled,
    )

    server = AgentBusServer(host=bus_settings.host, port=bus_settings.port)

    async def _run() -> None:
        await server.start_server()

        if bus_settings.telegram_enabled and bus_settings.telegram_token:
            telegram_token = bus_settings.telegram_token
            await server.start_with_telegram(
                token=telegram_token,
                allow_from=set(bus_settings.telegram_allow_from),
                allow_chats=set(bus_settings.telegram_allow_chats),
                proxy=bus_settings.telegram_proxy,
            )

        try:
            await asyncio.Event().wait()
        except KeyboardInterrupt:
            logger.info("bus.serve stopped")
        finally:
            if bus_settings.telegram_enabled:
                await server.stop_with_telegram()
            await server.stop_server()

    asyncio.run(_run())
