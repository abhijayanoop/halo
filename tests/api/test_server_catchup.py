"""A HUD that connects late, or reconnects, must not miss an open approval."""

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


def _until(ws, wanted: str, limit: int = 80) -> list[dict]:
    seen = []
    for _ in range(limit):
        event = ws.receive_json()
        seen.append(event)
        if event["type"] == wanted:
            return seen
    raise AssertionError(f"never saw {wanted}: {[e['type'] for e in seen]}")


def test_a_late_hud_is_told_about_the_approval_that_is_still_open(
    halo_cm_factory,
) -> None:
    app = create_app(halo_cm_factory(reply(_intent())))
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        with _ws(client) as first:
            run_id = client.post("/run", json={"request": "open Notepad"}).json()[
                "run_id"
            ]
            asked = _until(first, "approval.requested")[-1]

        # The first HUD went away. A second one connects while Halo is still waiting.
        with _ws(client) as second:
            replayed = _until(second, "approval.requested")[-1]

    assert replayed["run_id"] == run_id
    assert replayed["payload"]["approval_id"] == asked["payload"]["approval_id"]


def test_a_late_hud_is_told_the_current_mood(halo_cm_factory) -> None:
    app = create_app(halo_cm_factory(reply(_intent())))
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        with _ws(client) as first:
            client.post("/run", json={"request": "open Notepad"})
            _until(first, "approval.requested")
            moods = [e for e in _until(first, "mood")[-1:]]
        with _ws(client) as second:
            seen = _until(second, "mood")[-1]

    assert moods and seen["payload"]["mood"] in {"thinking", "asking"}


def test_a_resolved_approval_is_not_replayed(halo_cm_factory) -> None:
    app = create_app(halo_cm_factory(reply(_intent())))
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        with _ws(client) as first:
            run_id = client.post("/run", json={"request": "open Notepad"}).json()[
                "run_id"
            ]
            asked = _until(first, "approval.requested")[-1]
            body = {
                "run_id": run_id,
                "approval_id": asked["payload"]["approval_id"],
                "grant": "deny",
            }
            assert client.post("/approve", json=body).status_code == 200
            _until(first, "run.finished")

        with _ws(client) as second:
            client.post("/run", json={"request": "open Notepad"})  # nothing scripted
            snapshot = []
            for _ in range(3):
                snapshot.append(second.receive_json())
                if snapshot[-1]["type"] == "run.started":
                    break

    assert "approval.requested" not in [e["type"] for e in snapshot]
