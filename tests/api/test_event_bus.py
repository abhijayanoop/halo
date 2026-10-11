import asyncio

from halo.api.events import EventBus
from halo.core.events import make_event


def _ev(n: int):
    return make_event("run1", "step.started", f"step {n}")


async def test_subscriber_receives_events_in_publish_order() -> None:
    bus = EventBus()
    async with bus.subscribe() as queue:
        sent = [_ev(i) for i in range(3)]
        for event in sent:
            bus.publish(event)
        got = [await asyncio.wait_for(queue.get(), 1) for _ in sent]
    assert got == sent


async def test_every_subscriber_gets_every_event() -> None:
    bus = EventBus()
    async with bus.subscribe() as a, bus.subscribe() as b:
        event = _ev(1)
        bus.publish(event)
        assert await asyncio.wait_for(a.get(), 1) == event
        assert await asyncio.wait_for(b.get(), 1) == event


async def test_subscriber_stops_receiving_after_it_leaves() -> None:
    bus = EventBus()
    async with bus.subscribe() as queue:
        assert bus.subscriber_count == 1
    assert bus.subscriber_count == 0
    bus.publish(_ev(1))
    assert queue.empty()


async def test_publish_without_subscribers_is_a_noop() -> None:
    EventBus().publish(_ev(1))


async def test_event_published_before_subscribing_is_not_replayed() -> None:
    bus = EventBus()
    bus.publish(_ev(1))
    async with bus.subscribe() as queue:
        assert queue.empty()


async def test_subscriber_removed_even_if_its_body_raises() -> None:
    bus = EventBus()
    try:
        async with bus.subscribe():
            raise RuntimeError("boom")
    except RuntimeError:
        pass
    assert bus.subscriber_count == 0
