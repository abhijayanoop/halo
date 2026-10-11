"""POST /approve must name the approval it answers."""

import json

from conftest import reply
from starlette.testclient import TestClient

from halo.api.server import create_app


def _intent() -> str:
    return json.dumps(
        {"skill": "app.open", "args": {"app": "Spotify"}, "confidence": 0.95}
    )


def _client(halo_cm_factory, *script) -> TestClient:
    return TestClient(
        create_app(halo_cm_factory(*script)), base_url="http://127.0.0.1:8000"
    )


def _ws(client: TestClient):
    return client.websocket_connect("/events", headers={"Host": "127.0.0.1:8000"})


def _until(ws, wanted: str, limit: int = 60) -> list[dict]:
    seen = []
    for _ in range(limit):
        event = ws.receive_json()
        seen.append(event)
        if event["type"] == wanted:
            return seen
    raise AssertionError(f"never saw {wanted}")


def test_approve_without_an_approval_id_is_rejected(halo_cm_factory) -> None:
    with _client(halo_cm_factory) as client:
        r = client.post("/approve", json={"run_id": "x", "grant": "allow_once"})
    assert r.status_code == 422


def test_a_stale_approval_id_is_a_conflict_and_the_run_keeps_waiting(
    halo_cm_factory,
) -> None:
    with _client(halo_cm_factory, reply(_intent())) as client, _ws(client) as ws:
        run_id = client.post("/run", json={"request": "open Spotify"}).json()["run_id"]
        asked = _until(ws, "approval.requested")[-1]

        stale = {"run_id": run_id, "approval_id": "X" * 26, "grant": "allow_once"}
        assert client.post("/approve", json=stale).status_code == 409

        good = {
            "run_id": run_id,
            "approval_id": asked["payload"]["approval_id"],
            "grant": "allow_once",
        }
        assert client.post("/approve", json=good).status_code == 200
        rest = _until(ws, "run.finished")
    resolved = [e for e in rest if e["type"] == "approval.resolved"]
    assert resolved[0]["payload"]["approval_id"] == good["approval_id"]
