from __future__ import annotations

import asyncio
import json
from contextlib import asynccontextmanager
from dataclasses import dataclass
from time import monotonic
from typing import Awaitable, Callable

from app.models.jobs import JobLogger


@dataclass(frozen=True)
class GeminiGateReservation:
    waited_ms: int = 0


class GeminiRequestGate:
    def __init__(
        self,
        *,
        max_concurrent_requests: int,
        min_request_interval_ms: int,
        cooldown_on_429_ms: int,
        sleep_fn: Callable[[float], Awaitable[None]] = asyncio.sleep,
        monotonic_fn: Callable[[], float] = monotonic,
    ) -> None:
        self.max_concurrent_requests = max(1, max_concurrent_requests)
        self.min_request_interval_ms = max(0, min_request_interval_ms)
        self.cooldown_on_429_ms = max(0, cooldown_on_429_ms)
        self._sleep = sleep_fn
        self._monotonic = monotonic_fn
        self._semaphore = asyncio.Semaphore(self.max_concurrent_requests)
        self._timeline_lock = asyncio.Lock()
        self._next_request_at = 0.0
        self._cooldown_until = 0.0

    @asynccontextmanager
    async def request_slot(
        self,
        *,
        model: str,
        on_log: JobLogger | None = None,
    ):
        await self._semaphore.acquire()
        try:
            waited_ms = await self._wait_for_window(model=model, on_log=on_log)
            yield GeminiGateReservation(waited_ms=waited_ms)
        finally:
            self._semaphore.release()

    async def apply_cooldown(
        self,
        *,
        wait_ms: int,
        reason: str,
        model: str,
        on_log: JobLogger | None = None,
        status_code: int | None = None,
    ) -> int:
        duration_ms = max(0, wait_ms)
        if duration_ms <= 0:
            return 0

        async with self._timeline_lock:
            now = self._monotonic()
            target = now + (duration_ms / 1000)
            if target > self._cooldown_until:
                self._cooldown_until = target
            remaining_ms = int(max(0.0, self._cooldown_until - now) * 1000)

        if on_log is not None:
            on_log(
                "request",
                "Gemini cooldown scheduled.",
                json.dumps(
                    {
                        "model": model,
                        "reason": reason,
                        "statusCode": status_code,
                        "cooldownMs": remaining_ms,
                    },
                    ensure_ascii=False,
                    indent=2,
                ),
            )

        return remaining_ms

    async def _wait_for_window(self, *, model: str, on_log: JobLogger | None) -> int:
        async with self._timeline_lock:
            now = self._monotonic()
            ready_at = max(now, self._cooldown_until, self._next_request_at)
            wait_seconds = max(0.0, ready_at - now)
            self._next_request_at = ready_at + (self.min_request_interval_ms / 1000)

        wait_ms = int(wait_seconds * 1000)
        if wait_ms > 0:
            if on_log is not None:
                on_log(
                    "request",
                    "Gemini request gate waiting.",
                    json.dumps(
                        {
                            "model": model,
                            "waitMs": wait_ms,
                            "maxConcurrentRequests": self.max_concurrent_requests,
                            "minRequestIntervalMs": self.min_request_interval_ms,
                        },
                        ensure_ascii=False,
                        indent=2,
                    ),
                )
            await self._sleep(wait_seconds)

        return wait_ms
