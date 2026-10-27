import asyncio

from halo.api.events import EventBus
from halo.character.director import MoodDirector
from halo.core.contracts import HaloEvent
from halo.core.events import make_event


async def _next_mood(queue: asyncio.Queue[HaloEvent]) -> HaloEvent:
    async with asyncio.timeout(2):
        while True:
            event = await queue.get()
            if event.type == "mood":
                return event


async def test_mood_events_are_published_back_onto_the_bus() -> None:
    bus = EventBus()
    async with bus.subscribe() as queue, MoodDirector(bus, tick_s=0.01):
        bus.publish(make_event("run-1", "approval.requested", "Can I open Spotify?"))

        mood = await _next_mood(queue)

    assert mood.payload["mood"] == "asking"
    assert mood.run_id == "run-1"


async def test_timed_moods_expire_without_further_events() -> None:
    bus = EventBus()
    clock_value = {"t": 0.0}

    def clock() -> float:
        return clock_value["t"]

    async with bus.subscribe() as queue, MoodDirector(bus, tick_s=0.01, clock=clock):
        bus.publish(
            make_event("run-1", "run.finished", "done", payload={"status": "ok"})
        )
        assert (await _next_mood(queue)).payload["mood"] == "delighted"

        clock_value["t"] += 2.0
        assert (await _next_mood(queue)).payload["mood"] == "idle"


async def test_closing_the_director_stops_it_cleanly() -> None:
    bus = EventBus()
    async with MoodDirector(bus, tick_s=0.01):
        assert bus.subscriber_count == 1
    await asyncio.sleep(0)
    assert bus.subscriber_count == 0
