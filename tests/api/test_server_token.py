"""The local API needs a per-launch token on /run, /approve and /events."""

from pathlib import Path

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from halo.api.server import create_app, resolve_token

TOKEN = "s3cret-token-for-tests"


def _client(halo_cm_factory) -> TestClient:
    app = create_app(halo_cm_factory(), token=TOKEN)
    return TestClient(app, base_url="http://127.0.0.1:8000")


def _ws(client: TestClient, query: str = ""):
    return client.websocket_connect(
        f"/events{query}", headers={"Host": "127.0.0.1:8000"}
    )


def test_health_needs_no_token(halo_cm_factory) -> None:
    with _client(halo_cm_factory) as client:
        assert client.get("/health").status_code == 200


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/run", {"request": "open vscode"}),
        ("/approve", {"run_id": "x", "approval_id": "x", "grant": "deny"}),
    ],
)
def test_http_calls_without_the_token_are_refused(
    halo_cm_factory, path: str, body: dict
) -> None:
    with _client(halo_cm_factory) as client:
        assert client.post(path, json=body).status_code == 401
        wrong = {"X-Halo-Token": "not-the-token"}
        assert client.post(path, json=body, headers=wrong).status_code == 401


def test_a_call_with_the_token_gets_through_to_validation(halo_cm_factory) -> None:
    with _client(halo_cm_factory) as client:
        ok = {"X-Halo-Token": TOKEN}
        # 422 (empty body) proves the request passed authentication.
        assert client.post("/run", json={}, headers=ok).status_code == 422
        # 409: authenticated, but no run is waiting.
        body = {"run_id": "nope", "approval_id": "x", "grant": "deny"}
        assert client.post("/approve", json=body, headers=ok).status_code == 409


@pytest.mark.parametrize("query", ["", "?token=wrong"])
def test_the_event_stream_refuses_a_missing_or_wrong_token(
    halo_cm_factory, query: str
) -> None:
    with (
        _client(halo_cm_factory) as client,
        pytest.raises(WebSocketDisconnect),
        _ws(client, query),
    ):
        pass


def test_the_event_stream_accepts_the_token(halo_cm_factory) -> None:
    with _client(halo_cm_factory) as client, _ws(client, f"?token={TOKEN}"):
        pass


def test_the_token_is_not_accepted_as_a_query_parameter_over_http(
    halo_cm_factory,
) -> None:
    with _client(halo_cm_factory) as client:
        r = client.post("/run", params={"token": TOKEN}, json={"request": "x"})
    assert r.status_code == 401


def test_resolve_token_prefers_the_environment(tmp_path: Path) -> None:
    assert resolve_token(tmp_path, {"HALO_API_TOKEN": "from-env"}) == "from-env"
    assert not (tmp_path / "api-token").exists()


def test_resolve_token_generates_and_stores_a_random_token(tmp_path: Path) -> None:
    first = resolve_token(tmp_path, {})
    assert len(first) >= 32
    assert (tmp_path / "api-token").read_text(encoding="utf-8").strip() == first

    second = resolve_token(tmp_path, {})
    assert second != first  # a fresh token for every launch
