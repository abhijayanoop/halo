"""Stop ends a run the user no longer wants, whether it is working or waiting
on a permission card, using the existing run.finished event (status "denied",
which the HUD already words as "Stopped, as you asked")."""

import asyncio
import json

from conftest import reply


def _intent(app: str) -> str:
    return json.dumps({"skill": "app.open", "args": {"app": app}, "confidence": 0.95})


async def test_stopping_a_working_run_ends_it_without_a_failure(open_runner) -> None:
    async with open_runner() as (runner, events, transport, spawned):
        release = asyncio.Event()

        async def hang(**_: object) -> None:
            await release.wait()

        transport.chat = hang
        task = asyncio.create_task(runner.run("open vscode", run_id="s1"))
        await asyncio.sleep(0.05)  # the router call is now in flight

        assert await runner.stop("s1") is True
        outcome = await asyncio.wait_for(task, 2)

    assert outcome.state == "finished"
    assert outcome.result_status == "denied"
    finished = [e for e in events if e.type == "run.finished"]
    assert len(finished) == 1
    assert finished[0].payload["status"] == "denied"
    assert finished[0].payload["stopped"] is True
    assert not [e for e in events if e.type == "run.failed"]
    assert spawned == []


async def test_stopping_a_run_that_waits_on_a_card_denies_it(open_runner) -> None:
    async with open_runner(reply(_intent("Notepad"))) as (
        runner,
        events,
        _,
        spawned,
    ):
        paused = await runner.run("open Notepad", run_id="s2")
        assert paused.state == "paused"

        assert await runner.stop("s2") is True

        assert await runner.pending_approval("s2") is None
    assert spawned == []
    types = [e.type for e in events]
    assert types[-1] == "run.finished"
    assert events[-1].payload["status"] == "denied"


async def test_stopping_a_run_that_is_not_active_does_nothing(open_runner) -> None:
    async with open_runner() as (runner, events, *_):
        assert await runner.stop("never-existed") is False
    assert events == []


async def test_a_stopped_run_can_not_be_stopped_twice(open_runner) -> None:
    async with open_runner(reply(_intent("Notepad"))) as (runner, *_):
        await runner.run("open Notepad", run_id="s3")
        assert await runner.stop("s3") is True
        assert await runner.stop("s3") is False
