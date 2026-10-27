"""The brief and result cards of a coding session are answered with POST /code/decision."""

import pytest
from starlette.testclient import TestClient

from halo.api.server import create_app

DID = "D" * 26


def _client(halo_cm_factory, **kw) -> TestClient:
    return TestClient(
        create_app(halo_cm_factory(), **kw), base_url="http://127.0.0.1:8000"
    )


def _ask(client: TestClient, allowed: frozenset[str], decision_id: str = DID):
    decisions = client.app.state.halo.code_decisions  # type: ignore[attr-defined]
    return client.portal.start_task_soon(  # type: ignore[union-attr]
        lambda: decisions.ask("run1", decision_id, allowed=allowed, timeout=5)
    )


def _wait_pending(client: TestClient) -> None:
    decisions = client.app.state.halo.code_decisions  # type: ignore[attr-defined]
    for _ in range(200):
        if decisions.has_pending("run1"):
            return
        client.portal.call(lambda: None)  # type: ignore[union-attr]
    raise AssertionError("the card never started waiting")


def _body(action: str, **extra) -> dict:
    return {"run_id": "run1", "approval_id": DID, "action": action, **extra}


def test_an_answer_reaches_the_waiting_session(halo_cm_factory) -> None:
    with _client(halo_cm_factory) as client:
        future = _ask(client, frozenset({"merge", "iterate", "discard"}))
        _wait_pending(client)
        r = client.post("/code/decision", json=_body("iterate", feedback="add a test"))
        assert r.status_code == 200
        answer = future.result(timeout=5)
        assert answer.action == "iterate" and answer.feedback == "add a test"


def test_an_edited_brief_is_carried_through(halo_cm_factory) -> None:
    brief = {"goal": "g", "acceptance_criteria": ["c"], "test_cmd": "t"}
    with _client(halo_cm_factory) as client:
        future = _ask(client, frozenset({"approve", "deny"}))
        _wait_pending(client)
        r = client.post("/code/decision", json=_body("approve", brief=brief))
        assert r.status_code == 200
        assert future.result(timeout=5).brief.goal == "g"


def test_an_action_the_card_does_not_offer_is_refused_and_the_card_keeps_waiting(
    halo_cm_factory,
) -> None:
    with _client(halo_cm_factory) as client:
        future = _ask(client, frozenset({"approve", "deny"}))
        _wait_pending(client)
        assert client.post("/code/decision", json=_body("merge")).status_code == 422
        assert not future.done()
        assert client.post("/code/decision", json=_body("deny")).status_code == 200
        assert future.result(timeout=5).action == "deny"


def test_a_stale_id_is_a_conflict_and_the_card_keeps_waiting(halo_cm_factory) -> None:
    with _client(halo_cm_factory) as client:
        future = _ask(client, frozenset({"approve", "deny"}))
        _wait_pending(client)
        stale = {**_body("approve"), "approval_id": "X" * 26}
        assert client.post("/code/decision", json=stale).status_code == 409
        assert not future.done()
        client.post("/code/decision", json=_body("deny"))
        future.result(timeout=5)


def test_nothing_waiting_is_a_conflict(halo_cm_factory) -> None:
    with _client(halo_cm_factory) as client:
        assert client.post("/code/decision", json=_body("approve")).status_code == 409


@pytest.mark.parametrize(
    "body",
    [
        {"run_id": "run1", "action": "approve"},
        {"run_id": "run1", "approval_id": DID, "action": "push"},
        {
            "run_id": "run1",
            "approval_id": DID,
            "action": "iterate",
            "feedback": "x" * 2001,
        },
    ],
)
def test_bad_bodies_are_rejected(halo_cm_factory, body: dict) -> None:
    with _client(halo_cm_factory) as client:
        assert client.post("/code/decision", json=body).status_code == 422
