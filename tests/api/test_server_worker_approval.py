"""A permission card from inside a coding worker is answered through the same POST /approve."""

from conftest import reply  # noqa: F401  (shared fixtures live in conftest)
from starlette.testclient import TestClient

from halo.api.server import create_app
from halo.core.contracts import ApprovalRequest


def _client(halo_cm_factory) -> TestClient:
    return TestClient(create_app(halo_cm_factory()), base_url="http://127.0.0.1:8000")


def _request(approval_id: str = "A" * 26) -> ApprovalRequest:
    return ApprovalRequest(
        approval_id=approval_id, action="Claude Code: Bash", detail="make", risk="high"
    )


def _ask(client: TestClient, run_id: str, request: ApprovalRequest):
    approvals = client.app.state.halo.worker_approvals  # type: ignore[attr-defined]
    return client.portal.start_task_soon(  # type: ignore[union-attr]
        lambda: approvals.ask(run_id, request, timeout=5)
    )


def _wait_pending(client: TestClient, run_id: str) -> None:
    approvals = client.app.state.halo.worker_approvals  # type: ignore[attr-defined]
    for _ in range(200):
        if approvals.has_pending(run_id):
            return
        client.portal.call(lambda: None)  # type: ignore[union-attr]
    raise AssertionError("the worker request never started waiting")


def test_the_shared_approve_route_answers_a_worker_card(halo_cm_factory) -> None:
    with _client(halo_cm_factory) as client:
        future = _ask(client, "run1", _request())
        _wait_pending(client, "run1")
        body = {"run_id": "run1", "approval_id": "A" * 26, "grant": "allow_once"}
        assert client.post("/approve", json=body).status_code == 200
        assert future.result(timeout=5) == "allow_once"


def test_deny_reaches_the_worker(halo_cm_factory) -> None:
    with _client(halo_cm_factory) as client:
        future = _ask(client, "run1", _request())
        _wait_pending(client, "run1")
        body = {"run_id": "run1", "approval_id": "A" * 26, "grant": "deny"}
        assert client.post("/approve", json=body).status_code == 200
        assert future.result(timeout=5) == "deny"


def test_a_stale_id_is_a_conflict_and_the_worker_keeps_waiting(halo_cm_factory) -> None:
    with _client(halo_cm_factory) as client:
        future = _ask(client, "run1", _request())
        _wait_pending(client, "run1")
        stale = {"run_id": "run1", "approval_id": "B" * 26, "grant": "allow_once"}
        assert client.post("/approve", json=stale).status_code == 409
        assert not future.done()
        good = {"run_id": "run1", "approval_id": "A" * 26, "grant": "deny"}
        assert client.post("/approve", json=good).status_code == 200
        assert future.result(timeout=5) == "deny"


def test_nothing_waiting_still_gives_the_old_conflict(halo_cm_factory) -> None:
    with _client(halo_cm_factory) as client:
        body = {"run_id": "nope", "approval_id": "A" * 26, "grant": "allow_once"}
        assert client.post("/approve", json=body).status_code == 409
