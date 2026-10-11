"""Runs the MoodEngine against the live event bus.

Subscribes to every event, feeds the engine, and publishes the resulting
`mood` events back onto the bus, so the flight recorder and the HUD receive
them like any other event. A ticker applies time-based moods (dwell, timed
moods, sleep) when no events arrive.
"""

import asyncio
import contextlib
import time
from collections.abc import Callable
from types import TracebackType
from typing import Self

from halo.api.events import EventBus
from halo.character.mood import MoodEngine
from halo.core.contracts import HaloEvent


class MoodDirector:
    def __init__(
        self,
        bus: EventBus,
        *,
        tick_s: float = 0.1,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._bus = bus
        self._tick_s = tick_s
        self._engine = MoodEngine(clock)
        self._subscription = bus.subscribe()
        self._tasks: list[asyncio.Task[None]] = []

    async def __aenter__(self) -> Self:
        queue = await self._subscription.__aenter__()
        self._tasks = [
            asyncio.create_task(self._consume(queue)),
            asyncio.create_task(self._tick()),
        ]
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await self._subscription.__aexit__(exc_type, exc, tb)

    async def _consume(self, queue: asyncio.Queue[HaloEvent]) -> None:
        while True:
            event = await queue.get()
            self._publish(self._engine.feed(event))

    async def _tick(self) -> None:
        while True:
            await asyncio.sleep(self._tick_s)
            self._publish(self._engine.tick())

    def _publish(self, events: list[HaloEvent]) -> None:
        for event in events:
            self._bus.publish(event)
