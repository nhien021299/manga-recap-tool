from __future__ import annotations

import asyncio

import pytest

from app.services.gemini_request_gate import GeminiRequestGate


@pytest.mark.asyncio
async def test_request_gate_serializes_parallel_requests():
    gate = GeminiRequestGate(
        max_concurrent_requests=1,
        min_request_interval_ms=0,
        cooldown_on_429_ms=0,
    )
    entered_first = asyncio.Event()
    release_first = asyncio.Event()
    order: list[str] = []

    async def first() -> None:
        async with gate.request_slot(model="gemini-test") as reservation:
            order.append(f"enter-first:{reservation.waited_ms}")
            entered_first.set()
            await release_first.wait()
            order.append("exit-first")

    async def second() -> None:
        await entered_first.wait()
        async with gate.request_slot(model="gemini-test") as reservation:
            order.append(f"enter-second:{reservation.waited_ms}")
            order.append("exit-second")

    task_one = asyncio.create_task(first())
    task_two = asyncio.create_task(second())
    await entered_first.wait()
    await asyncio.sleep(0)
    assert order == ["enter-first:0"]

    release_first.set()
    await asyncio.gather(task_one, task_two)
    assert order == ["enter-first:0", "exit-first", "enter-second:0", "exit-second"]


@pytest.mark.asyncio
async def test_request_gate_waits_for_interval_and_cooldown():
    clock = {"now": 0.0}
    sleep_calls: list[float] = []

    async def fake_sleep(duration: float) -> None:
        sleep_calls.append(duration)
        clock["now"] += duration

    gate = GeminiRequestGate(
        max_concurrent_requests=1,
        min_request_interval_ms=50,
        cooldown_on_429_ms=200,
        sleep_fn=fake_sleep,
        monotonic_fn=lambda: clock["now"],
    )

    async with gate.request_slot(model="gemini-test") as first:
        assert first.waited_ms == 0

    await gate.apply_cooldown(wait_ms=200, reason="429", model="gemini-test")

    async with gate.request_slot(model="gemini-test") as second:
        assert second.waited_ms == 200

    assert sleep_calls == [0.2]
