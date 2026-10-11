"""The local HTTP API: POST /run, POST /approve, WS /events.

It listens on localhost only and refuses requests whose Host or Origin is not
local, so a web page open in the user's browser cannot start runs, approve
actions or read events.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, HTTPException, Request, WebSocket
from pydantic import BaseModel, field_validator
from starlette.types import ASGIApp, Receive, Scope, Send

from halo.bootstrap import Halo
from halo.core.contracts import ApprovalDecision, ApprovalGrant
from halo.core.events import new_event_id

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
# The Vite dev server the HUD is developed against.
UI_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}


class RunBody(BaseModel):
    request: str

    @field_validator("request")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("request must not be blank")
        return value


class ApproveBody(BaseModel):
    run_id: str
    grant: ApprovalGrant


class LocalOnlyMiddleware:
    """Pure ASGI so it covers WebSockets too. A missing Origin (curl, the CLI,
    scripts) is fine; a present one must be local, because browsers always send it."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    @staticmethod
    def _is_local(value: str | None) -> bool:
        return value is not None and urlsplit(f"//{value}").hostname in LOCAL_HOSTS

    @staticmethod
    def _origin_allowed(origin: str, host: str | None) -> bool:
        """The page must be served by this server (same origin) or be the UI dev
        server. A page from any other local port, e.g. a throwaway `http.server`
        or a notebook, is refused."""
        if origin in UI_ORIGINS:
            return True
        parts = urlsplit(origin)
        return (
            host is not None
            and parts.scheme in ("http", "https")
            and parts.netloc.casefold() == host.casefold()
        )

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] not in ("http", "websocket"):
            await self.app(scope, receive, send)
            return
        headers = {
            k.decode("latin-1"): v.decode("latin-1") for k, v in scope["headers"]
        }
        host = headers.get("host")
        origin = headers.get("origin")
        origin_ok = origin is None or self._origin_allowed(origin, host)
        if not (self._is_local(host) and origin_ok):
            if scope["type"] == "websocket":
                await receive()  # the connect message
                await send({"type": "websocket.close", "code": 1008})
            else:
                body = b"forbidden"
                await send(
                    {
                        "type": "http.response.start",
                        "status": 403,
                        "headers": [(b"content-type", b"text/plain")],
                    }
                )
                await send({"type": "http.response.body", "body": body})
            return
        await self.app(scope, receive, send)


def create_app(
    open_halo_cm: Callable[[], AbstractAsyncContextManager[Halo]],
) -> FastAPI:
    tasks: set[asyncio.Task[Any]] = set()
    resuming: set[str] = set()

    def spawn(coro: Awaitable[Any]) -> None:
        task = asyncio.ensure_future(coro)
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with open_halo_cm() as halo:
            app.state.halo = halo
            yield
            for task in list(tasks):
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)

    app = FastAPI(title="Halo", lifespan=lifespan)
    app.add_middleware(LocalOnlyMiddleware)

    @app.get("/health")
    async def health() -> dict[str, bool]:
        return {"ok": True}

    @app.post("/run")
    async def run(body: RunBody, request: Request) -> dict[str, str]:
        halo: Halo = request.app.state.halo
        run_id = new_event_id()
        spawn(halo.runner.run(body.request, run_id=run_id))
        return {"run_id": run_id}

    @app.post("/approve")
    async def approve(body: ApproveBody, request: Request) -> dict[str, bool]:
        halo: Halo = request.app.state.halo
        not_waiting = HTTPException(409, "that run is not waiting for approval")
        if body.run_id in resuming:
            raise not_waiting
        # Claim the run before any await, so two simultaneous requests cannot both pass.
        resuming.add(body.run_id)
        try:
            pending = await halo.runner.pending_approval(body.run_id)
        except BaseException:
            resuming.discard(body.run_id)
            raise
        if pending is None:
            resuming.discard(body.run_id)
            raise not_waiting

        async def resume() -> None:
            try:
                await halo.runner.resume(
                    body.run_id, ApprovalDecision(grant=body.grant)
                )
            finally:
                resuming.discard(body.run_id)

        spawn(resume())
        return {"ok": True}

    @app.websocket("/events")
    async def events(ws: WebSocket) -> None:
        halo: Halo = ws.app.state.halo
        # Subscribe before accepting, so no event between connect and subscribe is missed.
        async with halo.bus.subscribe() as queue:
            await ws.accept()

            async def pump() -> None:
                while True:
                    event = await queue.get()
                    await ws.send_text(event.model_dump_json())

            pump_task = asyncio.ensure_future(pump())
            receive_task = asyncio.ensure_future(ws.receive())
            try:
                while True:
                    done, _ = await asyncio.wait(
                        {pump_task, receive_task}, return_when=asyncio.FIRST_COMPLETED
                    )
                    if (
                        pump_task in done
                    ):  # a send failed: stop instead of idling silently
                        break
                    if receive_task.result()["type"] == "websocket.disconnect":
                        break
                    receive_task = asyncio.ensure_future(ws.receive())
            finally:
                for task in (pump_task, receive_task):
                    task.cancel()
                await asyncio.gather(pump_task, receive_task, return_exceptions=True)
                with contextlib.suppress(RuntimeError):
                    await ws.close()

    return app


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the API (used by the desktop app and `python -m halo.api.server`)."""
    import uvicorn

    from halo.bootstrap import open_halo
    from halo.config import load_config, load_env

    load_env()
    config = load_config()
    uvicorn.run(create_app(lambda: open_halo(config)), host=host, port=port)


if __name__ == "__main__":
    serve()
