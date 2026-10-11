import json
from pathlib import Path

from halo.api.events import EventBus
from halo.core.events import make_event
from halo.telemetry.recorder import FlightRecorder, read_events


def _ev(n: int, run_id: str = "run1"):
    return make_event(run_id, "step.finished", f"step {n}", payload={"n": n})


async def test_record_appends_one_json_line_per_event(tmp_path: Path) -> None:
    recorder = FlightRecorder(tmp_path)
    events = [_ev(i) for i in range(3)]
    for event in events:
        await recorder.record(event)
    files = list(tmp_path.glob("*.jsonl"))
    assert len(files) == 1
    lines = files[0].read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["id"] for line in lines] == [e.id for e in events]


async def test_file_is_named_for_the_events_local_date(tmp_path: Path) -> None:
    recorder = FlightRecorder(tmp_path)
    event = _ev(1)
    await recorder.record(event)
    expected = f"{event.ts.astimezone().date().isoformat()}.jsonl"
    assert [p.name for p in tmp_path.glob("*.jsonl")] == [expected]


async def test_runs_dir_is_created_when_missing(tmp_path: Path) -> None:
    nested = tmp_path / "a" / "b"
    await FlightRecorder(nested).record(_ev(1))
    assert any(nested.glob("*.jsonl"))


async def test_recorded_events_parse_back_identically(tmp_path: Path) -> None:
    recorder = FlightRecorder(tmp_path)
    events = [_ev(i) for i in range(5)]
    for event in events:
        await recorder.record(event)
    (path,) = tmp_path.glob("*.jsonl")
    assert read_events(path) == events


async def test_attached_recorder_saves_everything_published_on_the_bus(
    tmp_path: Path,
) -> None:
    bus = EventBus()
    recorder = FlightRecorder(tmp_path)
    events = [_ev(i) for i in range(4)]
    async with recorder.attached(bus):
        for event in events:
            bus.publish(event)
    (path,) = tmp_path.glob("*.jsonl")
    assert read_events(path) == events
    assert bus.subscriber_count == 0


async def test_unicode_titles_survive_the_round_trip(tmp_path: Path) -> None:
    recorder = FlightRecorder(tmp_path)
    event = make_event("run1", "mood", "Spent ₹450 — lunch ✓")
    await recorder.record(event)
    (path,) = tmp_path.glob("*.jsonl")
    assert read_events(path) == [event]


async def test_attached_recorder_survives_a_failed_write(tmp_path: Path) -> None:
    blocker = tmp_path / "not-a-dir"
    blocker.write_text("x")  # runs_dir sits under a file, so every write fails
    bus = EventBus()
    async with FlightRecorder(blocker / "runs").attached(bus):
        bus.publish(_ev(1))
        bus.publish(_ev(2))
    assert bus.subscriber_count == 0
