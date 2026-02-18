"""Forward-only agent loop."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import Any

from loguru import logger

from bub.channels.events import InboundMessage
from bub.core.model_runner import ModelRunner, ModelTurnResult
from bub.core.router import InputRouter
from bub.tape.service import TapeService
from bub.bub_types import MessageBus


@dataclass(frozen=True)
class LoopResult:
    """Loop output for one input turn."""

    immediate_output: str
    assistant_output: str
    exit_requested: bool
    steps: int
    error: str | None = None
    trigger_next: str | None = None


CompleteCallback = Callable[[ModelTurnResult], Coroutine[Any, Any, None]]


class AgentLoop:
    """Deterministic single-session loop built on an endless tape."""

    def __init__(
        self,
        *,
        router: InputRouter,
        model_runner: ModelRunner,
        tape: TapeService,
        session_id: str,
        bus: MessageBus,
    ) -> None:
        if bus is None:
            raise ValueError("bus is required for AgentLoop")
        self._router = router
        self._model_runner = model_runner
        self._tape = tape
        self._session_id = session_id
        self._bus = bus
        self._on_complete: CompleteCallback | None = None
        self._unsub_inbound: Callable[[], None] | None = None
        self._running = False

    def set_complete_callback(self, callback: CompleteCallback) -> None:
        self._on_complete = callback

    async def start(self) -> None:
        """Start listening to inbound messages from the bus."""
        # TODO: Update for new bus API - on_inbound removed, need subscribe pattern
        # For now, disabled - requires architectural changes
        self._unsub_inbound = None

        self._running = True
        logger.info("agent.loop.start session_id={}", self._session_id)

    async def stop(self) -> None:
        """Stop listening to the bus."""
        self._running = False
        if self._unsub_inbound is not None:
            self._unsub_inbound()
            self._unsub_inbound = None
        logger.info("agent.loop.stop session_id={}", self._session_id)

    async def _handle_inbound(self, message: InboundMessage) -> None:
        """Handle inbound message from the bus."""
        if not self._running:
            return

        session_id = message.session_id
        if session_id != self._session_id:
            return

        logger.debug(
            "agent.loop.receive session_id={} channel={} chat_id={} content={}",
            session_id,
            message.channel,
            message.chat_id,
            message.content[:100],
        )

        try:
            result = await self.handle_input(message.render())
            parts = [part for part in (result.immediate_output, result.assistant_output) if part]
            if result.error:
                parts.append(f"error: {result.error}")
            output = "\n\n".join(parts).strip()

            if output and self._bus:
                # TODO: Update for new bus API - publish_outbound removed
                # For now, just log that we would send a message
                logger.debug(
                    "agent.loop.send.disabled session_id={} channel={} chat_id={} content={}",
                    session_id,
                    message.channel,
                    message.chat_id,
                    output[:100],
                )
        except Exception:
            logger.exception("agent.loop.error session_id={}", session_id)

    async def handle_input(self, raw: str) -> LoopResult:
        logger.debug("agent.loop.input session_id={} raw={}", self._session_id, raw[:100])
        route = await self._router.route_user(raw)
        logger.debug(
            "agent.loop.route session_id={} enter_model={} exit_requested={}",
            self._session_id,
            route.enter_model,
            route.exit_requested,
        )

        if route.exit_requested:
            logger.debug("agent.loop.exit session_id={}", self._session_id)
            return LoopResult(
                immediate_output=route.immediate_output,
                assistant_output="",
                exit_requested=True,
                steps=0,
                error=None,
            )

        if not route.enter_model:
            logger.debug("agent.loop.command session_id={}", self._session_id)
            return LoopResult(
                immediate_output=route.immediate_output,
                assistant_output="",
                exit_requested=False,
                steps=0,
                error=None,
            )

        logger.debug("agent.loop.model session_id={} prompt={}", self._session_id, route.model_prompt[:100])
        model_result = await self._model_runner.run(route.model_prompt)
        self._record_result(model_result)
        logger.debug(
            "agent.loop.complete session_id={} steps={} exit={}",
            self._session_id,
            model_result.steps,
            model_result.exit_requested,
        )

        if self._on_complete and model_result.trigger_next:
            logger.debug(
                "agent.loop.trigger_next session_id={} trigger={}", self._session_id, model_result.trigger_next
            )
            await self._on_complete(model_result)
        return LoopResult(
            immediate_output=route.immediate_output,
            assistant_output=model_result.visible_text,
            exit_requested=model_result.exit_requested,
            steps=model_result.steps,
            error=model_result.error,
            trigger_next=model_result.trigger_next,
        )

    def _record_result(self, result: ModelTurnResult) -> None:
        self._tape.append_event(
            "loop.result",
            {
                "steps": result.steps,
                "followups": result.command_followups,
                "exit_requested": result.exit_requested,
                "error": result.error,
                "trigger_next": result.trigger_next,
            },
        )
