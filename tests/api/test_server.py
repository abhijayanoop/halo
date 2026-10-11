import json

import pytest
from conftest import reply
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from halo.api.server import create_app


def _intent(app: str) -> str:
    return json.dumps({"skill": "app.open", "args": {"app": app}, "confidence": 0.95})


def _client(halo_cm_factory, *script) -> TestClient:
    app = create_app(halo_cm_factory(*script))
    return TestClient(app, base_url="http://127.0.0.1:8000")


def _ws(client: TestClient, **headers: str):
    return client.websocket_connect(
        "/events", headers={"Host": "127.0.0.1:8000", **headers}
    )


def _collect(ws, until: str, limit: int = 60) -> list[dict]:
    seen = []
    for _ in range(limit):
        event = ws.receive_json()
        seen.append(event)
        if event["type"] == until:
            return seen
    raise AssertionError(f"never saw {until}: {[e['type'] for e in seen]}")


def test_health(halo_cm_factory) -> None:
    with _client(halo_cm_factory) as client:
        assert client.get("/health").json() == {"ok": True}


def test_a_run_streams_its_events_over_the_websocket(halo_cm_factory) -> None:
    with (
        _client(halo_cm_factory, reply(_intent("vscode"))) as client,
        _ws(client) as ws,
    ):
        run_id = client.post("/run", json={"request": "open vscode"}).json()["run_id"]
        events = _collect(ws, "run.finished")
    types = [e["type"] for e in events if e["type"] != "cost.updated"]
    assert types[0] == "run.started"
    assert types[-1] == "run.finished"
    assert {e["run_id"] for e in events} == {run_id}
    assert len(halo_cm_factory.spawned) == 1


def test_approval_round_trip_over_http(halo_cm_factory) -> None:
    with (
        _client(halo_cm_factory, reply(_intent("Spotify"))) as client,
        _ws(client) as ws,
    ):
        run_id = client.post("/run", json={"request": "open Spotify"}).json()["run_id"]
        asked = _collect(ws, "approval.requested")[-1]
        assert asked["payload"]["risk"] == "medium"
        assert asked["payload"]["action"] == "app.open"

        body = {
            "run_id": run_id,
            "approval_id": asked["payload"]["approval_id"],
            "grant": "allow_once",
        }
        r = client.post("/approve", json=body)
        assert r.status_code == 200
        rest = _collect(ws, "run.finished")
    assert "approval.resolved" in [e["type"] for e in rest]


def test_denying_over_http_ends_the_run_as_denied(halo_cm_factory) -> None:
    with (
        _client(halo_cm_factory, reply(_intent("Spotify"))) as client,
        _ws(client) as ws,
    ):
        run_id = client.post("/run", json={"request": "open Spotify"}).json()["run_id"]
        asked = _collect(ws, "approval.requested")[-1]
        deny = {
            "run_id": run_id,
            "approval_id": asked["payload"]["approval_id"],
            "grant": "deny",
        }
        client.post("/approve", json=deny)
        done = _collect(ws, "run.finished")[-1]
    assert done["payload"]["status"] == "denied"


def test_approving_a_run_that_is_not_waiting_is_a_conflict(halo_cm_factory) -> None:
    with _client(halo_cm_factory) as client:
        r = client.post(
            "/approve",
            json={"run_id": "nope", "approval_id": "x", "grant": "allow_once"},
        )
    assert r.status_code == 409


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/run", {"request": ""}),
        ("/run", {"request": "   "}),
        ("/run", {}),
        ("/approve", {"run_id": "x", "approval_id": "x", "grant": "sure"}),
        ("/approve", {"approval_id": "x", "grant": "allow_once"}),
    ],
)
def test_invalid_bodies_are_rejected(halo_cm_factory, path, body) -> None:
    with _client(halo_cm_factory) as client:
        assert client.post(path, json=body).status_code == 422


def test_a_foreign_web_page_cannot_start_runs_or_approve(halo_cm_factory) -> None:
    evil = {"Origin": "https://evil.example"}
    with _client(halo_cm_factory) as client:
        assert (
            client.post("/run", json={"request": "x"}, headers=evil).status_code == 403
        )
        approve = {"run_id": "x", "approval_id": "x", "grant": "allow_once"}
        assert client.post("/approve", json=approve, headers=evil).status_code == 403


def test_a_foreign_web_page_cannot_listen_to_events(halo_cm_factory) -> None:
    # Host is local here, so it is the foreign Origin alone that must be refused.
    with (
        _client(halo_cm_factory) as client,
        pytest.raises(WebSocketDisconnect),
        _ws(client, Origin="https://evil.example"),
    ):
        pass


@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://127.0.0.1:8000"])
def test_local_origins_are_allowed(halo_cm_factory, origin) -> None:
    with _client(halo_cm_factory) as client:
        assert client.get("/health", headers={"Origin": origin}).status_code == 200


def test_requests_for_other_hostnames_are_refused_against_dns_rebinding(
    halo_cm_factory,
) -> None:
    with _client(halo_cm_factory) as client:
        r = client.get("/health", headers={"Host": "evil.example:8000"})
    assert r.status_code == 403
