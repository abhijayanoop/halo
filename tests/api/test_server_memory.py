"""Approving or rejecting a proposed memory from the HUD, and catching a late HUD up."""

from pathlib import Path

from starlette.testclient import TestClient

from halo.api.server import create_app
from halo.core.contracts import MemoryCandidate
from halo.memory.events import proposed_event

BASE = "http://127.0.0.1:8000"


def _ws(client: TestClient):
    return client.websocket_connect("/events", headers={"Host": "127.0.0.1:8000"})


def _until(ws, wanted: str, limit: int = 60) -> dict:
    for _ in range(limit):
        event = ws.receive_json()
        if event["type"] == wanted:
            return event
    raise AssertionError(f"never saw {wanted}")


def _candidate(fact="Prefers pytest over unittest") -> MemoryCandidate:
    return MemoryCandidate(fact=fact, subject="halo", source="agent", trust="medium")


def _propose(client: TestClient, candidate: MemoryCandidate | None = None) -> str:
    """Propose through the store and announce it, as the extractor does."""
    halo = client.app.state.halo  # type: ignore[attr-defined]
    candidate = candidate or _candidate()
    pid = halo.memory.propose(candidate)
    assert pid
    halo.bus.publish(proposed_event(pid, candidate))
    return pid


def test_approving_writes_the_memory_and_tells_the_hud(halo_cm_factory) -> None:
    client = TestClient(create_app(halo_cm_factory()), BASE)
    with client, _ws(client) as ws:
        pid = _propose(client)
        _until(ws, "memory.proposed")
        response = client.post("/memory/approve", json={"candidate_id": pid})
        saved = _until(ws, "memory.saved")
        assert response.status_code == 200
        assert saved["payload"]["candidate_id"] == pid
        assert saved["payload"]["fact"] == "Prefers pytest over unittest"
        memory = client.app.state.halo.memory  # type: ignore[attr-defined]
        assert memory.recall("pytest")
        assert memory.proposals() == []


def test_approving_can_pick_the_note(halo_cm_factory) -> None:
    client = TestClient(create_app(halo_cm_factory()), BASE)
    with client, _ws(client) as ws:
        pid = _propose(client)
        _until(ws, "memory.proposed")
        client.post(
            "/memory/approve", json={"candidate_id": pid, "note": "People/sam.md"}
        )
        assert _until(ws, "memory.saved")["payload"]["note"] == "People/sam.md"


def test_an_unsafe_note_path_is_refused(halo_cm_factory) -> None:
    client = TestClient(create_app(halo_cm_factory()), BASE)
    with client:
        pid = _propose(client)
        response = client.post(
            "/memory/approve", json={"candidate_id": pid, "note": "../outside.md"}
        )
        assert response.status_code == 422
        assert client.app.state.halo.memory.proposals()  # type: ignore[attr-defined]


def test_rejecting_discards_it_and_tells_the_hud(halo_cm_factory) -> None:
    client = TestClient(create_app(halo_cm_factory()), BASE)
    with client, _ws(client) as ws:
        pid = _propose(client)
        _until(ws, "memory.proposed")
        assert (
            client.post("/memory/reject", json={"candidate_id": pid}).status_code == 200
        )
        gone = _until(ws, "memory.forgotten")
        assert gone["payload"] == {"candidate_id": pid, "rejected": True}
        assert client.app.state.halo.memory.proposals() == []  # type: ignore[attr-defined]


def test_unknown_proposals_are_a_404(halo_cm_factory) -> None:
    client = TestClient(create_app(halo_cm_factory()), BASE)
    with client:
        assert (
            client.post("/memory/approve", json={"candidate_id": "^p-no"}).status_code
            == 404
        )
        assert (
            client.post("/memory/reject", json={"candidate_id": "^p-no"}).status_code
            == 404
        )


def test_a_late_hud_is_told_about_open_proposals_but_not_settled_ones(
    halo_cm_factory,
) -> None:
    client = TestClient(create_app(halo_cm_factory()), BASE)
    with client:
        open_pid = _propose(client, _candidate("Uses ruff for linting"))
        done_pid = _propose(client, _candidate("Likes dark mode"))
        client.post("/memory/reject", json={"candidate_id": done_pid})
        with _ws(client) as ws:
            seen = _until(ws, "memory.proposed")
    assert seen["payload"]["candidate_id"] == open_pid


def test_proposals_waiting_when_halo_quit_are_shown_after_a_restart(
    halo_cm_factory, tmp_path: Path
) -> None:
    home = tmp_path / "restart-memory"
    first = TestClient(create_app(halo_cm_factory(home=home)), BASE)
    with first:
        pid = _propose(first)

    second = TestClient(create_app(halo_cm_factory(home=home)), BASE)
    with second, _ws(second) as ws:
        seen = _until(ws, "memory.proposed")
    assert seen["payload"]["candidate_id"] == pid
    assert seen["payload"]["fact"] == "Prefers pytest over unittest"
