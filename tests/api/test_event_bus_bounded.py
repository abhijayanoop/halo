"""A client that stops reading must not make the server's memory grow."""

import asyncio

from halo.api.events import EventBus
from halo.core.events import make_event


def _ev(n: int):
    return make_event("run1", "step.started", f"step {n}")


async def test_a_stuck_subscriber_keeps_only_the_newest_events() -> None:
    bus = EventBus(max_queue=3)
    async with bus.subscribe() as queue:
        for n in range(5):
            bus.publish(_ev(n))
        titles = [queue.get_nowait().title for _ in range(queue.qsize())]
    assert titles == ["step 2", "step 3", "step 4"]


async def test_a_stuck_subscriber_never_blocks_or_hurts_another() -> None:
    bus = EventBus(max_queue=2)
    async with bus.subscribe() as stuck, bus.subscribe() as reader:
        seen = []
        for n in range(6):
            bus.publish(_ev(n))
            seen.append((await asyncio.wait_for(reader.get(), 1)).title)
        assert stuck.qsize() == 2
    assert seen == [f"step {n}" for n in range(6)]


async def test_the_default_bound_is_generous_but_finite() -> None:
    bus = EventBus()
    async with bus.subscribe() as queue:
        for n in range(5000):
            bus.publish(_ev(n))
        assert 100 <= queue.qsize() <= 2000
