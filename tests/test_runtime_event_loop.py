import asyncio

import pytest

from bub.app.runtime import Session, cancel_active_inputs, reset_session_context


class DummySession:
    def __init__(self) -> None:
        self.calls = 0

    def reset_context(self) -> None:
        self.calls += 1


def test_reset_session_context_ignores_missing_session() -> None:
    sessions: dict[str, Session] = {}
    reset_session_context(sessions, "missing")


def test_reset_session_context_resets_existing_session() -> None:
    session = DummySession()
    sessions: dict[str, Session] = {"telegram:1": session}
    reset_session_context(sessions, "telegram:1")
    assert session.calls == 1


@pytest.mark.asyncio
async def test_cancel_active_inputs_cancels_running_tasks() -> None:
    gate = asyncio.Event()
    cancelled = {"value": False}

    async def _pending() -> None:
        try:
            await gate.wait()
        finally:
            cancelled["value"] = True

    task = asyncio.create_task(_pending())
    active_inputs: set[asyncio.Task[None]] = {task}
    await asyncio.sleep(0)

    count = await cancel_active_inputs(active_inputs)
    assert count == 1

    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled["value"] is True
