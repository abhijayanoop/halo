"""Day 3's "done when", end to end and offline: type "open Notepad" (not on the
allowlist), Halo thinks and asks, Enter allows it, Notepad opens, Halo is
delighted for 2 seconds, then goes back to idle. A scripted model stands in for
Nemotron; everything else is the real server, bus, runner and mood director."""

import json
import time
from datetime import datetime

from conftest import reply
from starlette.testclient import TestClient

from halo.api.server import create_app

TOKEN = "demo-token"


def _seconds(ts: str) -> float:
    return datetime.fromisoformat(ts).timestamp()


def _intent() -> str:
    return json.dumps(
        {"skill": "app.open", "args": {"app": "Notepad"}, "confidence": 0.95}
    )


def test_open_notepad_asks_then_opens_then_delights_then_rests(halo_cm_factory) -> None:
    app = create_app(halo_cm_factory(reply(_intent())), token=TOKEN)
    headers = {"X-Halo-Token": TOKEN}
    with (
        TestClient(app, base_url="http://127.0.0.1:8000") as client,
        client.websocket_connect(
            f"/events?token={TOKEN}", headers={"Host": "127.0.0.1:8000"}
        ) as ws,
    ):
        run_id = client.post(
            "/run", json={"request": "open Notepad"}, headers=headers
        ).json()["run_id"]

        moods: list[tuple[str, float]] = []
        asked = None
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            event = ws.receive_json()
            if event["type"] == "mood" and not event["payload"].get("refined"):
                moods.append((event["payload"]["mood"], _seconds(event["ts"])))
                if event["payload"]["mood"] == "idle" and len(moods) > 2:
                    break
            if event["type"] == "approval.requested":
                asked = event
                # Enter on the card: allow once, with the id the card showed.
                body = {
                    "run_id": run_id,
                    "approval_id": event["payload"]["approval_id"],
                    "grant": "allow_once",
                }
                assert (
                    client.post("/approve", json=body, headers=headers).status_code
                    == 200
                )

    names = [name for name, _ in moods]
    assert asked is not None and asked["payload"]["risk"] == "medium"
    assert "thinking" in names
    assert names.index("thinking") < names.index("asking")
    assert names.index("asking") < names.index("delighted")
    assert names[-1] == "idle"
    # Notepad was launched exactly once, only after the approval.
    assert len(halo_cm_factory.spawned) == 1
    # Delighted lasts about 2 seconds before idle (the dwell can only stretch it).
    at = dict(reversed(moods))
    delighted_for = at["idle"] - dict(moods)["delighted"]
    assert 1.9 <= delighted_for < 4.0
