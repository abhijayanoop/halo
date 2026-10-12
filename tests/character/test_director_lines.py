"""The director puts a status line on every mood event: a template at once,
then Nano's better line if it arrives in time and is still current."""

import asyncio
from types import SimpleNamespace

from halo.api.events import EventBus
from halo.character.director import MoodDirector
from halo.character.lines import StatusLines, template_line
from halo.core.contracts import HaloEvent
from halo.core.events import make_event


class FakeClient:
    def __init__(
        self, text: str = "Opening Notepad", gate: asyncio.Event | None = None
    ) -> None:
        self.text = text
        self.gate = gate
        self.calls = 0

    async def call(self, tier, messages, *, run_id=None, **kwargs):
        self.calls += 1
        if self.gate:
            await self.gate.wait()
        return SimpleNamespace(text=self.text)


async def _moods(queue: asyncio.Queue[HaloEvent], count: int) -> list[HaloEvent]:
    found: list[HaloEvent] = []
    async with asyncio.timeout(2):
        while len(found) < count:
            event = await queue.get()
            if event.type == "mood":
                found.append(event)
    return found


async def test_a_mood_event_carries_the_template_line_immediately() -> None:
    bus = EventBus()
    trigger = make_event("run-1", "approval.requested", "Can I run app.open?")
    async with bus.subscribe() as queue, MoodDirector(bus, tick_s=0.01):
        bus.publish(trigger)
        (mood,) = await _moods(queue, 1)

    assert mood.payload["line"] == template_line(trigger)


async def test_a_mood_with_no_trigger_event_still_has_a_line() -> None:
    bus = EventBus()
    clock = {"t": 0.0}
    async with (
        bus.subscribe() as queue,
        MoodDirector(bus, tick_s=0.01, clock=lambda: clock["t"]),
    ):
        bus.publish(
            make_event("run-1", "run.finished", "Done", payload={"status": "ok"})
        )
        await _moods(queue, 1)  # delighted
        clock["t"] += 2.0
        (idle,) = await _moods(queue, 1)

    assert idle.payload["mood"] == "idle"
    assert idle.payload["line"] == "Ready"


async def test_nanos_line_follows_as_a_refined_mood_event() -> None:
    bus = EventBus()
    client = FakeClient("Opening Notepad")
    lines = StatusLines(client)  # type: ignore[arg-type]
    async with bus.subscribe() as queue, MoodDirector(bus, tick_s=0.01, lines=lines):
        bus.publish(make_event("run-1", "tool.called", "Opening app"))
        first, refined = await _moods(queue, 2)

    assert first.payload["mood"] == "focused"
    assert first.payload["line"] == "Opening app"
    assert refined.payload["mood"] == "focused"
    assert refined.payload["line"] == "Opening Notepad"
    assert refined.payload["refined"] is True


async def test_a_late_line_is_dropped_when_something_newer_has_happened() -> None:
    bus = EventBus()
    gate = asyncio.Event()
    lines = StatusLines(FakeClient("Opening Notepad", gate=gate), timeout_s=5)  # type: ignore[arg-type]
    async with bus.subscribe() as queue, MoodDirector(bus, tick_s=0.01, lines=lines):
        bus.publish(make_event("run-1", "tool.called", "Opening app"))
        await _moods(queue, 1)
        bus.publish(make_event("run-1", "approval.requested", "Can I run app.open?"))
        asking = (await _moods(queue, 1))[0]
        gate.set()
        await asyncio.sleep(0.1)

        leftovers = []
        while not queue.empty():
            event = queue.get_nowait()
            if event.type == "mood":
                leftovers.append(event)

    assert asking.payload["mood"] == "asking"
    assert [
        e
        for e in leftovers
        if e.payload.get("refined") and e.payload["mood"] == "focused"
    ] == []


async def test_without_a_client_no_model_is_ever_called() -> None:
    bus = EventBus()
    async with bus.subscribe() as queue, MoodDirector(bus, tick_s=0.01):
        bus.publish(make_event("run-1", "tool.called", "Opening app"))
        (mood,) = await _moods(queue, 1)
    assert "refined" not in mood.payload
