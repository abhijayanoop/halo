"""The local HTTP API: POST /run, POST /approve, WS /events.

It listens on localhost only and refuses requests whose Host or Origin is not
local, so a web page open in the user's browser cannot start runs, approve
actions or read events. /run, /approve and /events also need the per-launch
token, so another program on this machine cannot use them either.
"""

import asyncio
import contextlib
import os
import secrets
from collections.abc import AsyncIterator, Awaitable, Callable, Mapping
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlsplit

from fastapi import FastAPI, HTTPException, Request, WebSocket
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, field_validator
from starlette.types import ASGIApp, Receive, Scope, Send
from starlette.websockets import WebSocketDisconnect

from halo.bootstrap import Halo
from halo.core.contracts import ApprovalDecision, ApprovalGrant, HaloEvent
from halo.core.events import new_event_id
from halo.memory.events import approved_event, proposed_event, rejected_event
from halo.memory.store import MemoryStore
from halo.memory.vault import VaultPathError

LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
# The Vite dev server the HUD is developed against.
UI_ORIGINS = {"http://localhost:5173", "http://127.0.0.1:5173"}
TOKEN_HEADER = "x-halo-token"
TOKEN_ENV = "HALO_API_TOKEN"
# Everything that acts on, or reveals, a run. /health and the UI's own files stay open.
PROTECTED_PATHS = {"/run", "/approve", "/events"}


def _retrieve(task: asyncio.Future[Any]) -> None:
    """Done-callback: mark a finished helper task's outcome as seen."""
    if not task.cancelled():
        task.exception()


class CatchUp:
    """What a HUD that connects late (or reconnects) needs to be told: the current
    mood, and every approval card still waiting for an answer. Without it a
    dropped socket would leave a run paused forever with no card on screen."""

    def __init__(self) -> None:
        self._mood: HaloEvent | None = None
        self._open: dict[str, HaloEvent] = {}
        self._proposals: dict[str, HaloEvent] = {}  # proposed memories not yet settled

    def feed(self, event: HaloEvent) -> None:
        match event.type:
            case "mood":
                self._mood = event
            case "memory.proposed":
                self._proposals[str(event.payload.get("candidate_id"))] = event
            case "memory.saved" | "memory.forgotten":
                self._proposals.pop(str(event.payload.get("candidate_id")), None)
            case "approval.requested":
                key = event.payload.get("approval_id")
                self._open[str(key or event.id)] = event
            case "approval.resolved":
                self._open.pop(str(event.payload.get("approval_id")), None)
            case "run.finished" | "run.failed":
                self._open = {
                    k: e for k, e in self._open.items() if e.run_id != event.run_id
                }

    def snapshot(self) -> list[HaloEvent]:
        return [
            *([self._mood] if self._mood else []),
            *self._open.values(),
            *self._proposals.values(),
        ]


class RunBody(BaseModel):
    request: str

    @field_validator("request")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("request must not be blank")
        return value


class StopBody(BaseModel):
    run_id: str


class MemoryDecisionBody(BaseModel):
    candidate_id: str
    note: str | None = None  # where to write an approved memory; default by subject


class ApproveBody(BaseModel):
    run_id: str
    approval_id: str
    grant: ApprovalGrant


class LocalOnlyMiddleware:
    """Pure ASGI so it covers WebSockets too. A missing Origin (curl, the CLI,
    scripts) is fine; a present one must be local, because browsers always send it."""

    def __init__(self, app: ASGIApp, token: str | None = None) -> None:
        self.app = app
        self.token = token

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
            await self._refuse(scope, receive, send, 403, b"forbidden")
            return
        if not self._token_ok(scope, headers):
            await self._refuse(scope, receive, send, 401, b"unauthorized")
            return
        await self.app(scope, receive, send)

    def _token_ok(self, scope: Scope, headers: dict[str, str]) -> bool:
        if self.token is None or scope["path"] not in PROTECTED_PATHS:
            return True
        if scope["type"] == "websocket":  # browsers cannot set WS headers
            query = parse_qs(scope.get("query_string", b"").decode("latin-1"))
            given = (query.get("token") or [""])[0]
        else:
            given = headers.get(TOKEN_HEADER, "")
        return secrets.compare_digest(given.encode(), self.token.encode())

    @staticmethod
    async def _refuse(
        scope: Scope, receive: Receive, send: Send, status: int, body: bytes
    ) -> None:
        if scope["type"] == "websocket":
            await receive()  # the connect message
            await send({"type": "websocket.close", "code": 1008})
            return
        await send(
            {
                "type": "http.response.start",
                "status": status,
                "headers": [(b"content-type", b"text/plain")],
            }
        )
        await send({"type": "http.response.body", "body": body})


def resolve_token(home: Path, env: Mapping[str, str] | None = None) -> str:
    """The token for this launch: $HALO_API_TOKEN if set, otherwise a fresh random
    one, written to <home>/api-token so a dev UI can read it."""
    env = os.environ if env is None else env
    if given := env.get(TOKEN_ENV):
        return given
    token = secrets.token_urlsafe(32)
    home.mkdir(parents=True, exist_ok=True)
    path = home / "api-token"
    path.write_text(token, encoding="utf-8")
    path.chmod(0o600)
    return token


def create_app(
    open_halo_cm: Callable[[], AbstractAsyncContextManager[Halo]],
    *,
    token: str | None = None,
    static_dir: Path | None = None,
) -> FastAPI:
    """`token=None` turns the token check off; only tests do that. serve()
    always passes one. `static_dir` is the built HUD, served from the same
    origin as the API."""
    tasks: set[asyncio.Task[Any]] = set()
    catchup = CatchUp()
    resuming: set[str] = set()

    def spawn(coro: Awaitable[Any]) -> None:
        task = asyncio.ensure_future(coro)
        tasks.add(task)
        task.add_done_callback(tasks.discard)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        async with open_halo_cm() as halo, halo.bus.subscribe() as watch:
            app.state.halo = halo
            app.state.catchup = catchup
            # Cards that were open when Halo last quit are still waiting: offer them.
            for restored in await halo.runner.paused_approvals():
                catchup.feed(restored)
            if halo.memory is not None:
                for waiting in await asyncio.to_thread(halo.memory.proposals):
                    catchup.feed(proposed_event(waiting.id, waiting.candidate))

            async def track() -> None:
                while True:
                    catchup.feed(await watch.get())

            tracker = asyncio.ensure_future(track())
            yield
            tracker.cancel()
            for task in list(tasks):
                task.cancel()
            await asyncio.gather(tracker, *tasks, return_exceptions=True)

    app = FastAPI(title="Halo", lifespan=lifespan)
    app.add_middleware(LocalOnlyMiddleware, token=token)

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
        if body.approval_id != pending.approval_id:
            # A stale or repeated click: the run keeps waiting for the real answer.
            resuming.discard(body.run_id)
            raise HTTPException(409, "that approval is no longer the one pending")

        async def resume() -> None:
            try:
                await halo.runner.resume(
                    body.run_id,
                    ApprovalDecision(approval_id=body.approval_id, grant=body.grant),
                )
            finally:
                resuming.discard(body.run_id)

        spawn(resume())
        return {"ok": True}

    def _memory(request: Request) -> MemoryStore:
        halo: Halo = request.app.state.halo
        if halo.memory is None:
            raise HTTPException(503, "memory is not set up")
        return halo.memory

    @app.post("/memory/approve")
    async def approve_memory(
        body: MemoryDecisionBody, request: Request
    ) -> dict[str, Any]:
        memory = _memory(request)
        try:
            item = await asyncio.to_thread(
                memory.approve, body.candidate_id, note=body.note
            )
        except KeyError:
            raise HTTPException(404, "no such proposed memory") from None
        except (VaultPathError, ValueError) as exc:
            raise HTTPException(422, str(exc)) from None
        request.app.state.halo.bus.publish(approved_event(body.candidate_id, item))
        return {"ok": True, "note": item.note_path}

    @app.post("/memory/reject")
    async def reject_memory(
        body: MemoryDecisionBody, request: Request
    ) -> dict[str, bool]:
        memory = _memory(request)
        if not await asyncio.to_thread(memory.reject, body.candidate_id):
            raise HTTPException(404, "no such proposed memory")
        request.app.state.halo.bus.publish(rejected_event(body.candidate_id))
        return {"ok": True}

    @app.post("/stop")
    async def stop(body: StopBody, request: Request) -> dict[str, bool]:
        halo: Halo = request.app.state.halo
        if body.run_id in resuming:
            raise HTTPException(409, "that run is answering a permission card")
        if not await halo.runner.stop(body.run_id):
            raise HTTPException(404, "that run is not working or waiting")
        return {"ok": True}

    @app.websocket("/events")
    async def events(ws: WebSocket) -> None:
        halo: Halo = ws.app.state.halo
        # Subscribe before accepting, so no event between connect and subscribe is missed.
        async with halo.bus.subscribe() as queue:
            await ws.accept()
            # Tell a late or reconnecting HUD where things stand. Anything that also
            # arrives through the queue is a duplicate the HUD ignores by event id.
            for event in ws.app.state.catchup.snapshot():
                await ws.send_text(event.model_dump_json())

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
                # Cancel the two helper tasks but do not await them here. Parked in
                # an await while this handler is itself being cancelled (a client
                # reconnect, a server shutdown), anyio re-delivers the cancel, the
                # task's cancel count reaches 2 and a CancelledError leaks out.
                # The done-callback still retrieves each task's result.
                for task in (pump_task, receive_task):
                    task.add_done_callback(_retrieve)
                    task.cancel()
                # The client may already be gone: closing then raises, which is fine.
                with contextlib.suppress(RuntimeError, WebSocketDisconnect):
                    await ws.close()

    if static_dir is not None:
        # Last, so the API routes above always win over a file of the same name.
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="ui")

    return app


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Run the API (used by the desktop app and `python -m halo.api.server`)."""
    import uvicorn

    from halo.bootstrap import default_home, open_halo
    from halo.config import load_config, load_env

    load_env()
    config = load_config()
    token = resolve_token(default_home())
    app = create_app(lambda: open_halo(config, watch=True), token=token)
    uvicorn.run(app, host=host, port=port, access_log=False)


if __name__ == "__main__":
    serve()
