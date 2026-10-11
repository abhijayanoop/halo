from datetime import UTC

from halo.core.events import make_event, new_event_id


def test_event_ids_are_26_char_ulids() -> None:
    event_id = new_event_id()
    assert len(event_id) == 26
    assert set(event_id) <= set("0123456789ABCDEFGHJKMNPQRSTVWXYZ")


def test_event_ids_are_unique() -> None:
    assert len({new_event_id() for _ in range(1000)}) == 1000


def test_event_ids_sort_by_creation_time(monkeypatch) -> None:
    from halo.core import events

    monkeypatch.setattr(events, "_now_ms", lambda: 1_000)
    earlier = new_event_id()
    monkeypatch.setattr(events, "_now_ms", lambda: 2_000)
    later = new_event_id()
    assert earlier < later


def test_make_event_stamps_id_and_utc_timestamp() -> None:
    event = make_event("run1", "run.started", "Started", payload={"k": 1})
    assert event.run_id == "run1"
    assert event.type == "run.started"
    assert event.payload == {"k": 1}
    assert event.ts.tzinfo == UTC
    assert len(event.id) == 26


def test_make_event_carries_agent_ids() -> None:
    event = make_event("r", "agent.spawned", "x", agent_id="a1", parent_agent_id="a0")
    assert (event.agent_id, event.parent_agent_id) == ("a1", "a0")
