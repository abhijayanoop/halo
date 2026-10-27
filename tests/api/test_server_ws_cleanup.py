"""Closing the event stream must never leak a cancellation out of the handler.

Starlette's test client cancels the app's scope right after it sends the
disconnect, without waiting for the handler's cleanup. A real HUD reconnect or
a uvicorn shutdown cancels handlers the same way, so cleanup has to survive it.
"""

import asyncio

import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocket

from halo.api.server import create_app

ROUNDS = 200


@pytest.fixture
def slow_close(monkeypatch: pytest.MonkeyPatch) -> None:
    """Widen the race: the handler's own ws.close() takes a moment, so the
    test client's cancel arrives while the handler is still cleaning up."""
    real_close = WebSocket.close

    async def slow(self: WebSocket, *args, **kwargs) -> None:
        await asyncio.sleep(0.002)
        await real_close(self, *args, **kwargs)

    monkeypatch.setattr(WebSocket, "close", slow)


def test_opening_and_closing_the_event_stream_repeatedly_never_raises(
    halo_cm_factory, slow_close
) -> None:
    app = create_app(halo_cm_factory())
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        for _ in range(ROUNDS):
            with client.websocket_connect(
                "/events", headers={"Host": "127.0.0.1:8000"}
            ):
                pass


def test_a_client_that_vanished_before_the_close_does_not_raise(
    halo_cm_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When the socket is already gone, ws.close() raises WebSocketDisconnect; the
    handler must swallow it instead of logging an ASGI exception on shutdown."""
    from starlette.websockets import WebSocketDisconnect

    async def gone(self: WebSocket, *args, **kwargs) -> None:
        raise WebSocketDisconnect(code=1006)

    monkeypatch.setattr(WebSocket, "close", gone)
    app = create_app(halo_cm_factory())
    client = TestClient(
        app, base_url="http://127.0.0.1:8000", raise_server_exceptions=True
    )
    with (
        client,
        client.websocket_connect("/events", headers={"Host": "127.0.0.1:8000"}),
    ):
        pass
