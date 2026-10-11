import asyncio
import json

import httpx2 as httpx
import pytest
from conftest import reply

from halo.api.server import create_app
from halo.core.contracts import ApprovalDecision


def _intent(app: str) -> str:
    return json.dumps({"skill": "app.open", "args": {"app": app}, "confidence": 0.95})


async def test_two_simultaneous_approvals_resume_the_run_only_once(
    halo_cm_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    app = create_app(halo_cm_factory(reply(_intent("Spotify"))))
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1:8000"
        ) as client,
    ):
        halo = app.state.halo
        resumed: list[ApprovalDecision] = []
        real_resume = halo.runner.resume

        async def slow_resume(run_id, decision):
            resumed.append(decision)
            await asyncio.sleep(
                0.05
            )  # keep the first resume in flight while the second arrives
            return await real_resume(run_id, decision)

        monkeypatch.setattr(halo.runner, "resume", slow_resume)
        run_id = (await client.post("/run", json={"request": "open Spotify"})).json()[
            "run_id"
        ]
        for _ in range(100):  # wait for the run to pause on its approval
            if await halo.runner.pending_approval(run_id):
                break
            await asyncio.sleep(0.05)

        pending = await halo.runner.pending_approval(run_id)
        assert pending is not None
        body = {
            "run_id": run_id,
            "approval_id": pending.approval_id,
            "grant": "allow_once",
        }
        first, second = await asyncio.gather(
            client.post("/approve", json=body), client.post("/approve", json=body)
        )
        await asyncio.sleep(0.3)

    assert sorted([first.status_code, second.status_code]) == [200, 409]
    assert len(resumed) == 1


async def test_a_page_served_from_another_local_port_is_refused(
    halo_cm_factory,
) -> None:
    app = create_app(halo_cm_factory())
    transport = httpx.ASGITransport(app=app)
    async with (
        app.router.lifespan_context(app),
        httpx.AsyncClient(
            transport=transport, base_url="http://127.0.0.1:8000"
        ) as client,
    ):
        other_port = await client.get(
            "/health", headers={"Origin": "http://localhost:9999"}
        )
        same_origin = await client.get(
            "/health", headers={"Origin": "http://127.0.0.1:8000"}
        )
        ui_dev = await client.get(
            "/health", headers={"Origin": "http://localhost:5173"}
        )
    assert other_port.status_code == 403
    assert same_origin.status_code == 200
    assert ui_dev.status_code == 200
