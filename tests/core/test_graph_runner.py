import json
import logging
import warnings

import pytest
from conftest import reply

from halo.core.contracts import ApprovalDecision, ApprovalGrant
from halo.models.transport import TransientModelError


def _intent(skill: str, app: str | None = None, confidence: float = 0.95) -> str:
    args = {"app": app} if app else {}
    return json.dumps({"skill": skill, "args": args, "confidence": confidence})


def _plan(*steps: tuple[str, str, dict]) -> str:
    return json.dumps(
        {
            "rationale": "test plan",
            "steps": [{"tool": t, "risk": r, "args": a} for t, r, a in steps],
        }
    )


async def _answer(runner, run_id: str, grant: ApprovalGrant):
    """Answer whatever approval the run is waiting on, as the card would."""
    pending = await runner.pending_approval(run_id)
    assert pending is not None
    return await runner.resume(
        run_id, ApprovalDecision(approval_id=pending.approval_id, grant=grant)
    )


def _types(events, *, skip=("cost.updated",)) -> list[str]:
    return [e.type for e in events if e.type not in skip]


async def test_open_vscode_runs_end_to_end_and_emits_the_full_event_story(
    open_runner,
) -> None:
    async with open_runner(reply(_intent("app.open", "vs code"))) as (
        runner,
        events,
        _,
        spawned,
    ):
        outcome = await runner.run("open VS Code", run_id="run1")

    assert outcome.state == "finished"
    assert outcome.result_status == "ok"
    assert len(spawned) == 1
    assert _types(events) == [
        "run.started",
        "step.started",  # router
        "step.finished",
        "step.started",  # planner
        "step.finished",
        "step.started",  # app.open
        "tool.called",
        "tool.result",
        "step.finished",
        "run.finished",
    ]
    assert {e.run_id for e in events} == {"run1"}
    assert events[-1].payload["status"] == "ok"


async def test_chat_reply_is_in_the_finished_event(open_runner) -> None:
    async with open_runner(reply(_intent("chat")), reply("Hello, I'm Halo.")) as (
        runner,
        events,
        *_,
    ):
        outcome = await runner.run("hi")
    assert outcome.result_status == "ok"
    assert outcome.results[0]["result"] == {"reply": "Hello, I'm Halo."}
    assert events[-1].payload["results"][0]["result"]["reply"] == "Hello, I'm Halo."


async def test_a_medium_risk_step_pauses_for_approval_before_doing_anything(
    open_runner,
) -> None:
    async with open_runner(reply(_intent("app.open", "Spotify"))) as (
        runner,
        events,
        _,
        spawned,
    ):
        outcome = await runner.run("open Spotify", run_id="run2")

        assert outcome.state == "paused"
        assert outcome.approval is not None
        assert outcome.approval.risk == "medium"
        assert outcome.approval.action == "app.open"
        assert "Spotify" in outcome.approval.detail
        assert _types(events)[-1] == "approval.requested"
        assert "run.finished" not in _types(events)
        assert "tool.called" not in _types(events)
        assert spawned == []
        assert (await runner.pending_approval("run2")) == outcome.approval


async def test_allow_once_resumes_the_paused_run(open_runner) -> None:
    async with open_runner(reply(_intent("app.open", "Spotify"))) as (
        runner,
        events,
        *_,
    ):
        await runner.run("open Spotify", run_id="run3")
        outcome = await _answer(runner, "run3", "allow_once")

        assert outcome.state == "finished"
        types = _types(events)
        assert types.index("approval.requested") < types.index("approval.resolved")
        last_step_finished = len(types) - 1 - types[::-1].index("step.finished")
        assert types.index("approval.resolved") < last_step_finished
        assert types.count("run.started") == 1  # resuming is not a new run
        assert types[-1] == "run.finished"
        assert (await runner.pending_approval("run3")) is None


async def test_deny_ends_the_run_without_running_the_tool(open_runner) -> None:
    async with open_runner(reply(_intent("app.open", "Spotify"))) as (
        runner,
        events,
        _,
        spawned,
    ):
        await runner.run("open Spotify", run_id="run4")
        outcome = await _answer(runner, "run4", "deny")

    assert outcome.state == "finished"
    assert outcome.result_status == "denied"
    assert "tool.called" not in _types(events)
    assert spawned == []
    assert events[-1].payload["status"] == "denied"


async def test_always_for_task_skips_asking_again_for_the_same_medium_tool(
    open_runner,
) -> None:
    two_steps = _plan(
        ("app.open", "medium", {"app": "vscode"}),
        ("app.open", "medium", {"app": "vscode"}),
    )
    async with open_runner(reply(_intent("trip.plan")), reply(two_steps)) as (
        runner,
        events,
        _,
        spawned,
    ):
        first = await runner.run("do the thing", run_id="run5")
        assert first.state == "paused"
        done = await _answer(runner, "run5", "always_for_task")

    assert done.state == "finished"
    assert _types(events).count("approval.requested") == 1
    assert len(spawned) == 2


async def test_always_for_task_never_covers_a_high_risk_step(open_runner) -> None:
    two_steps = _plan(
        ("app.open", "high", {"app": "vscode"}), ("app.open", "high", {"app": "vscode"})
    )
    async with open_runner(reply(_intent("trip.plan")), reply(two_steps)) as (
        runner,
        events,
        _,
        spawned,
    ):
        await runner.run("do the thing", run_id="run6")
        second = await _answer(runner, "run6", "always_for_task")
        assert second.state == "paused"
        assert len(spawned) == 1
        await _answer(runner, "run6", "allow_once")

    assert _types(events).count("approval.requested") == 2
    assert len(spawned) == 2


async def test_a_step_with_an_unknown_tool_is_a_reported_error_not_a_crash(
    open_runner,
) -> None:
    plan = _plan(("teleport", "low", {}))
    async with open_runner(reply(_intent("trip.plan")), reply(plan)) as (runner, *_):
        outcome = await runner.run("x")
    assert outcome.state == "finished"
    assert outcome.result_status == "error"
    assert "teleport" in json.dumps(outcome.results)


async def test_invalid_skill_args_are_a_reported_error_not_a_crash(open_runner) -> None:
    async with open_runner(reply(_intent("app.open"))) as (runner, *_):
        outcome = await runner.run("open")
    assert outcome.state == "finished"
    assert outcome.result_status == "error"


async def test_an_error_stops_the_remaining_steps(open_runner) -> None:
    plan = _plan(("teleport", "low", {}), ("app.open", "low", {"app": "vscode"}))
    async with open_runner(reply(_intent("trip.plan")), reply(plan)) as (
        runner,
        _,
        _,
        spawned,
    ):
        await runner.run("x")
    assert spawned == []


async def test_model_outage_fails_the_run_and_it_can_be_retried_from_the_checkpoint(
    open_runner,
) -> None:
    outage = [TransientModelError("503")] * 8  # nano and super both down
    async with open_runner(*outage, reply(_intent("app.open", "vscode"))) as (
        runner,
        events,
        _,
        spawned,
    ):
        failed = await runner.run("open vscode", run_id="run7")
        assert failed.state == "failed"
        assert failed.error
        assert _types(events)[-1] == "run.failed"
        assert events[-1].payload["reason"]
        assert spawned == []

        retried = await runner.retry("run7")

    assert retried.state == "finished"
    assert len(spawned) == 1
    types = _types(events)
    # The retry announces itself with a second run.started, marked as a retry.
    assert types.count("run.started") == 2
    retry_started = [e for e in events if e.type == "run.started"][1]
    assert retry_started.payload["retry"] is True
    assert types.count("run.failed") == 1
    assert types[-1] == "run.finished"


async def test_a_paused_run_survives_a_restart(open_runner, tmp_path) -> None:
    db = tmp_path / "restart.db"
    async with open_runner(reply(_intent("app.open", "Spotify")), db=db) as (
        runner,
        *_,
    ):
        await runner.run("open Spotify", run_id="run8")

    # A brand-new runner, graph and checkpointer connection over the same file.
    async with open_runner(db=db) as (runner, events, _, _):
        assert (await runner.pending_approval("run8")) is not None
        outcome = await _answer(runner, "run8", "allow_once")
    assert outcome.state == "finished"
    assert _types(events)[-1] == "run.finished"


async def test_resuming_a_run_that_is_not_paused_raises(open_runner) -> None:
    async with open_runner(reply(_intent("app.open", "vscode"))) as (runner, *_):
        await runner.run("open vscode", run_id="run9")
        with pytest.raises(ValueError, match="not waiting"):
            await runner.resume(
                "run9", ApprovalDecision(approval_id="x", grant="allow_once")
            )
        with pytest.raises(ValueError, match="not waiting"):
            await runner.resume(
                "never-existed", ApprovalDecision(approval_id="x", grant="allow_once")
            )


async def test_checkpointing_halo_models_raises_no_serialization_warnings(
    open_runner, caplog
) -> None:
    with warnings.catch_warnings(record=True) as caught, caplog.at_level(logging.DEBUG):
        warnings.simplefilter("always")
        async with open_runner(reply(_intent("app.open", "Spotify"))) as (runner, *_):
            await runner.run("open Spotify", run_id="run10")
            await _answer(runner, "run10", "allow_once")
    messages = [str(w.message) for w in caught] + [
        r.getMessage() for r in caplog.records
    ]
    assert not [m for m in messages if "unregistered" in m.lower()]


async def test_every_event_a_run_emits_is_stamped_with_its_run_id(open_runner) -> None:
    async with open_runner(reply(_intent("app.open", "Spotify"))) as (
        runner,
        events,
        *_,
    ):
        await runner.run("open Spotify", run_id="run11")
        await _answer(runner, "run11", "allow_once")
    assert {e.run_id for e in events} == {"run11"}


async def test_run_ids_are_generated_when_not_given(open_runner) -> None:
    async with open_runner(reply(_intent("app.open", "vscode"))) as (runner, *_):
        outcome = await runner.run("open vscode")
    assert len(outcome.run_id) == 26
