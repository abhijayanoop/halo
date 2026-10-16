"""A run that was waiting for approval when Halo quit is offered to the next HUD."""

import json

from conftest import reply
from starlette.testclient import TestClient

from halo.api.server import create_app

BASE = "http://127.0.0.1:8000"


def _intent() -> str:
    return json.dumps(
        {"skill": "app.open", "args": {"app": "Notepad"}, "confidence": 0.95}
    )


def _ws(client: TestClient):
    return client.websocket_connect("/events", headers={"Host": "127.0.0.1:8000"})


def _until(ws, wanted: str, limit: int = 40) -> dict:
    for _ in range(limit):
        event = ws.receive_json()
        if event["type"] == wanted:
            return event
    raise AssertionError(f"never saw {wanted}")


def test_a_paused_run_restored_after_a_restart_is_shown_to_a_new_hud(
    halo_cm_factory, tmp_path
) -> None:
    home = tmp_path / "restart-home"
    first = TestClient(create_app(halo_cm_factory(reply(_intent()), home=home)), BASE)
    with first, _ws(first) as ws:
        run_id = first.post("/run", json={"request": "open Notepad"}).json()["run_id"]
        asked = _until(ws, "approval.requested")

    # A new process: new app, new bus, same folder on disk.
    second = TestClient(create_app(halo_cm_factory(home=home)), BASE)
    with second, _ws(second) as ws:
        restored = _until(ws, "approval.requested")

    assert restored["run_id"] == run_id
    assert restored["payload"]["approval_id"] == asked["payload"]["approval_id"]
    assert restored["payload"]["action"] == "app.open"


def test_a_restored_approval_can_still_be_answered(halo_cm_factory, tmp_path) -> None:
    home = tmp_path / "restart-home-2"
    first = TestClient(create_app(halo_cm_factory(reply(_intent()), home=home)), BASE)
    with first, _ws(first) as ws:
        first.post("/run", json={"request": "open Notepad"})
        _until(ws, "approval.requested")

    second = TestClient(create_app(halo_cm_factory(home=home)), BASE)
    with second, _ws(second) as ws:
        restored = _until(ws, "approval.requested")
        body = {
            "run_id": restored["run_id"],
            "approval_id": restored["payload"]["approval_id"],
            "grant": "deny",
        }
        assert second.post("/approve", json=body).status_code == 200
        finished = _until(ws, "run.finished")
    assert finished["run_id"] == restored["run_id"]
