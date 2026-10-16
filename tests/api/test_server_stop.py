"""POST /stop ends a run from the HUD's Stop button."""

import json

from conftest import reply
from starlette.testclient import TestClient

from halo.api.server import create_app


def _intent() -> str:
    return json.dumps(
        {"skill": "app.open", "args": {"app": "Notepad"}, "confidence": 0.95}
    )


def _ws(client: TestClient):
    return client.websocket_connect("/events", headers={"Host": "127.0.0.1:8000"})


def _until(ws, wanted: str, limit: int = 60) -> dict:
    for _ in range(limit):
        event = ws.receive_json()
        if event["type"] == wanted:
            return event
    raise AssertionError(f"never saw {wanted}")


def test_stop_ends_a_run_that_is_waiting_for_approval(halo_cm_factory) -> None:
    app = create_app(halo_cm_factory(reply(_intent())))
    client = TestClient(app, base_url="http://127.0.0.1:8000")
    with client, _ws(client) as ws:
        run_id = client.post("/run", json={"request": "open Notepad"}).json()["run_id"]
        _until(ws, "approval.requested")
        response = client.post("/stop", json={"run_id": run_id})
        finished = _until(ws, "run.finished")

    assert response.status_code == 200
    assert finished["run_id"] == run_id
    assert finished["payload"]["status"] == "denied"


def test_stop_on_an_unknown_run_is_a_404(halo_cm_factory) -> None:
    app = create_app(halo_cm_factory())
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        response = client.post("/stop", json={"run_id": "nope"})
    assert response.status_code == 404


def test_stop_needs_a_run_id(halo_cm_factory) -> None:
    app = create_app(halo_cm_factory())
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        assert client.post("/stop", json={}).status_code == 422
