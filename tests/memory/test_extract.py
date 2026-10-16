"""After a run, Nano may propose facts worth remembering. Proposals wait for the user."""

import asyncio
import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import reply

from halo.api.events import EventBus
from halo.core.events import make_event
from halo.memory.extract import MemoryExtractor, extract_candidates, extractor_for
from halo.memory.store import MemoryStore
from halo.models.transport import ModelRequestError

NOW = datetime(2026, 10, 17, tzinfo=UTC)


def _facts(*facts: str, source="you", trust="high") -> str:
    return json.dumps(
        {
            "candidates": [
                {"fact": f, "subject": "halo", "source": source, "trust": trust}
                for f in facts
            ]
        }
    )


@pytest.fixture
def store(tmp_path: Path):
    s = MemoryStore(tmp_path / "vault", tmp_path / "memory.db", clock=lambda: NOW)
    s.start()
    yield s
    s.close()


async def test_candidates_come_from_what_the_user_said(make_client) -> None:
    client, transport, _ = make_client(reply(_facts("Prefers pytest over unittest")))
    got = await extract_candidates(client, "I always use pytest, never unittest", "r1")
    assert [c.fact for c in got] == ["Prefers pytest over unittest"]
    sent = str(transport.calls[0]["messages"])
    assert "I always use pytest, never unittest" in sent


async def test_a_proposal_is_always_marked_as_agent_proposed_and_medium_trust(
    make_client,
) -> None:
    """Whatever the model claims, a proposal is an inference, not the user's own line."""
    client, _, _ = make_client(reply(_facts("x fact", source="you", trust="high")))
    (cand,) = await extract_candidates(client, "some request", "r1")
    assert (cand.source, cand.trust) == ("agent", "medium")


async def test_at_most_three_and_no_blank_or_enormous_facts(make_client) -> None:
    client, _, _ = make_client(
        reply(_facts("a one", "", "b two", "c " * 400, "d three", "e four"))
    )
    got = await extract_candidates(client, "request", "r1")
    assert [c.fact for c in got] == ["a one", "b two", "d three"]


async def test_a_model_failure_proposes_nothing_instead_of_raising(
    make_client,
) -> None:
    client, _, _ = make_client(ModelRequestError("HTTP 400"))
    assert await extract_candidates(client, "request", "r1") == []


async def test_nothing_to_extract_for_a_blank_request(make_client) -> None:
    client, transport, _ = make_client()
    assert await extract_candidates(client, "   ", "r1") == []
    assert transport.calls == []


# --- the extractor that listens to the bus ----------------------------------------------


async def _settle(bus: EventBus, seconds: float = 0.2) -> None:
    await asyncio.sleep(seconds)


def _finished(run_id="r1", status="ok"):
    return make_event(run_id, "run.finished", "Done", payload={"status": status})


def _started(run_id="r1", request="I always use pytest"):
    return make_event(run_id, "run.started", request, payload={"request": request})


def _routed(skill: str, run_id="r1"):
    return make_event(
        run_id,
        "step.finished",
        f"Understood: {skill}",
        payload={"stage": "route", "skill": skill},
    )


async def test_a_finished_run_leads_to_proposals_and_events(
    make_client, store: MemoryStore
) -> None:
    bus = EventBus()
    client, _, _ = make_client(reply(_facts("Prefers pytest over unittest")))
    async with bus.subscribe() as watch, MemoryExtractor(bus, client, store):
        bus.publish(_started())
        bus.publish(_routed("chat"))
        bus.publish(_finished())
        await _settle(bus)
        events = []
        while not watch.empty():
            events.append(watch.get_nowait())
    proposed = [e for e in events if e.type == "memory.proposed"]
    assert len(proposed) == 1
    assert proposed[0].payload["fact"] == "Prefers pytest over unittest"
    assert proposed[0].payload["candidate_id"]
    assert [p.candidate.fact for p in store.proposals()] == [
        "Prefers pytest over unittest"
    ]


@pytest.mark.parametrize("skill", ["memory.remember", "memory.recall", "memory.forget"])
async def test_memory_runs_are_not_mined_for_more_memories(
    make_client, store: MemoryStore, skill: str
) -> None:
    bus = EventBus()
    client, transport, _ = make_client(reply(_facts("x fact")))
    async with MemoryExtractor(bus, client, store):
        bus.publish(_started())
        bus.publish(_routed(skill))
        bus.publish(_finished())
        await _settle(bus)
    assert transport.calls == []
    assert store.proposals() == []


@pytest.mark.parametrize("status", ["denied", "error"])
async def test_runs_that_did_not_succeed_are_not_mined(
    make_client, store: MemoryStore, status: str
) -> None:
    bus = EventBus()
    client, transport, _ = make_client(reply(_facts("x fact")))
    async with MemoryExtractor(bus, client, store):
        bus.publish(_started())
        bus.publish(_finished(status=status))
        await _settle(bus)
    assert transport.calls == []


async def test_a_failed_run_is_not_mined(make_client, store: MemoryStore) -> None:
    bus = EventBus()
    client, transport, _ = make_client(reply(_facts("x fact")))
    async with MemoryExtractor(bus, client, store):
        bus.publish(_started())
        bus.publish(make_event("r1", "run.failed", "no", payload={"reason": "x"}))
        await _settle(bus)
    assert transport.calls == []


async def test_a_fact_already_known_is_not_proposed_twice(
    make_client, store: MemoryStore
) -> None:
    store.remember("Prefers pytest over unittest")
    bus = EventBus()
    client, _, _ = make_client(reply(_facts("Prefers pytest over unittest")))
    async with bus.subscribe() as watch, MemoryExtractor(bus, client, store):
        bus.publish(_started())
        bus.publish(_finished())
        await _settle(bus)
        types = []
        while not watch.empty():
            types.append(watch.get_nowait().type)
    assert "memory.proposed" not in types
    assert store.proposals() == []


# --- opt-in --------------------------------------------------------------------------------


def test_extraction_is_off_unless_asked_for(make_client, store: MemoryStore) -> None:
    client, _, _ = make_client()
    bus = EventBus()
    assert extractor_for(bus, client, store, {}) is None
    assert extractor_for(bus, client, store, {"HALO_MEMORY_EXTRACT": "0"}) is None
    assert extractor_for(bus, client, store, {"HALO_MEMORY_EXTRACT": "1"}) is not None
