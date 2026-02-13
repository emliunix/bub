"""Forward-only agent loop."""

from __future__ import annotations

from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from bub.core.model_runner import ModelRunner, ModelTurnResult
from bub.core.router import InputRouter
from bub.tape.service import TapeService

if TYPE_CHECKING:
    from bub.channels.bus import MessageBus


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
        bus: MessageBus | None = None,
    ) -> None:
        self._router = router
        self._model_runner = model_runner
        self._tape = tape
        self._session_id = session_id
        self._bus = bus
        self._on_complete: CompleteCallback | None = None

    def set_complete_callback(self, callback: CompleteCallback) -> None:
        self._on_complete = callback

    async def handle_input(self, raw: str) -> LoopResult:
        with self._tape.fork_tape():
            route = await self._router.route_user(raw)
            if route.exit_requested:
                return LoopResult(
                    immediate_output=route.immediate_output,
                    assistant_output="",
                    exit_requested=True,
                    steps=0,
                    error=None,
                )

            if not route.enter_model:
                return LoopResult(
                    immediate_output=route.immediate_output,
                    assistant_output="",
                    exit_requested=False,
                    steps=0,
                    error=None,
                )

            model_result = await self._model_runner.run(route.model_prompt)
            self._record_result(model_result)
            if self._on_complete and model_result.trigger_next:
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
