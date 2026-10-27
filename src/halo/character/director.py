"""Runs the MoodEngine against the live event bus.

Subscribes to every event, feeds the engine, and publishes the resulting
`mood` events back onto the bus, so the flight recorder and the HUD receive
them like any other event. A ticker applies time-based moods (dwell, timed
moods, sleep) when no events arrive.

Every mood event carries a status `line` in its payload: a template at once,
and, when `lines` is given, Nano's line as a second ("refined") mood event if it
arrives in time and nothing newer has happened.
"""

import asyncio
import contextlib
import time
from collections.abc import Callable
from types import TracebackType
from typing import Self

from halo.api.events import EventBus
from halo.character.lines import StatusLines, template_line
from halo.character.mood import Mood, MoodEngine
from halo.core.contracts import HaloEvent
from halo.core.events import make_event

# Lines for moods that no event caused (a timer did).
_MOOD_LINES = {"idle": "Ready", "asleep": "Asleep for now", "waking": "Waking up"}


class MoodDirector:
    def __init__(
        self,
        bus: EventBus,
        *,
        tick_s: float = 0.1,
        clock: Callable[[], float] = time.monotonic,
        lines: StatusLines | None = None,
    ) -> None:
        self._bus = bus
        self._tick_s = tick_s
        self._engine = MoodEngine(clock)
        self._subscription = bus.subscribe()
        self._tasks: list[asyncio.Task[None]] = []
        self._lines = lines
        self._generation = 0  # bumped per event, so a late line can tell it is stale
        self._refining: set[asyncio.Task[None]] = set()

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
        for task in [*self._tasks, *self._refining]:
            task.cancel()
        for task in [*self._tasks, *self._refining]:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        await self._subscription.__aexit__(exc_type, exc, tb)

    async def _consume(self, queue: asyncio.Queue[HaloEvent]) -> None:
        while True:
            event = await queue.get()
            if event.type != "mood":
                self._generation += 1
            self._publish(self._engine.feed(event), trigger=event)

    async def _tick(self) -> None:
        while True:
            await asyncio.sleep(self._tick_s)
            self._publish(self._engine.tick())

    def _publish(
        self, events: list[HaloEvent], trigger: HaloEvent | None = None
    ) -> None:
        for mood in events:
            # A mood the dwell held back arrives on a tick: its line is still the
            # line of the event that asked for it, not a generic one.
            cause = self._engine.cause(Mood(mood.payload["mood"]))
            about = cause or trigger
            line = (
                template_line(about)
                if about
                else _MOOD_LINES.get(mood.payload["mood"], "Ready")
            )
            self._bus.publish(
                mood.model_copy(update={"payload": {**mood.payload, "line": line}})
            )
            if self._lines and about:
                task = asyncio.create_task(
                    self._refine(about, mood, line, self._generation)
                )
                self._refining.add(task)
                task.add_done_callback(self._refining.discard)

    async def _refine(
        self, trigger: HaloEvent, mood: HaloEvent, template: str, generation: int
    ) -> None:
        assert self._lines is not None
        line = await self._lines.line(trigger)
        if line == template or generation != self._generation:
            return  # nothing better, or the moment has passed
        self._bus.publish(
            make_event(
                mood.run_id,
                "mood",
                mood.title,
                payload={
                    **mood.payload,
                    "previous": mood.payload["mood"],
                    "line": line,
                    "refined": True,
                },
            )
        )
