"""Forward-only agent loop."""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from bub.core.model_runner import ModelRunner, ModelTurnResult
from bub.core.router import InputRouter
from bub.tape.service import TapeService


@dataclass(frozen=True)
class LoopResult:
    """Loop output for one input turn."""

    immediate_output: str
    assistant_output: str
    exit_requested: bool
    steps: int
    error: str | None = None
    trigger_next: str | None = None


class AgentLoop:
    """Deterministic single-session loop built on an endless tape."""

    def __init__(
        self,
        *,
        router: InputRouter,
        model_runner: ModelRunner,
        tape: TapeService,
        session_id: str,
    ) -> None:
        self._router = router
        self._model_runner = model_runner
        self._tape = tape
        self._session_id = session_id

    async def handle_input(self, raw: str) -> LoopResult:
        """Process user input through the agent loop."""
        logger.info("agent.loop.input session_id={} raw={}", self._session_id, raw[:100])
        route = await self._router.route_user(raw)
        logger.info(
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

        logger.info("agent.loop.model session_id={} prompt={}", self._session_id, route.model_prompt[:100])
        model_result = await self._model_runner.run(route.model_prompt)
        self._record_result(model_result)
        logger.debug(
            "agent.loop.complete session_id={} steps={} exit={}",
            self._session_id,
            model_result.steps,
            model_result.exit_requested,
        )

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
