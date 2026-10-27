"""An approval is bound to the exact step the user saw (its approval_id)."""

import json

import pytest
from conftest import reply

from halo.core.contracts import ApprovalDecision
from halo.core.runner import ApprovalMismatch


def _intent(skill: str) -> str:
    return json.dumps({"skill": skill, "args": {}, "confidence": 0.95})


def _spotify_intent() -> str:
    return json.dumps(
        {"skill": "app.open", "args": {"app": "Spotify"}, "confidence": 0.95}
    )


def _two_high_risk_steps() -> str:
    step = {"tool": "app.open", "risk": "high", "args": {"app": "vscode"}}
    return json.dumps({"rationale": "t", "steps": [step, step]})


async def test_the_request_carries_an_approval_id_that_the_event_repeats(
    open_runner,
) -> None:
    async with open_runner(reply(_spotify_intent())) as (runner, events, *_):
        outcome = await runner.run("open Spotify", run_id="b1")

    assert outcome.approval is not None
    assert len(outcome.approval.approval_id) == 26
    asked = [e for e in events if e.type == "approval.requested"][-1]
    assert asked.payload["approval_id"] == outcome.approval.approval_id


async def test_the_approval_id_survives_a_restart(open_runner, tmp_path) -> None:
    db = tmp_path / "bind.db"
    async with open_runner(reply(_spotify_intent()), db=db) as (runner, *_):
        first = await runner.run("open Spotify", run_id="b2")
    async with open_runner(db=db) as (runner, *_):
        pending = await runner.pending_approval("b2")

    assert first.approval is not None
    assert pending is not None
    assert pending.approval_id == first.approval.approval_id


async def test_a_wrong_approval_id_is_refused_and_the_run_stays_paused(
    open_runner,
) -> None:
    async with open_runner(reply(_spotify_intent())) as (runner, events, _, spawned):
        await runner.run("open Spotify", run_id="b3")
        with pytest.raises(ApprovalMismatch):
            await runner.resume(
                "b3", ApprovalDecision(approval_id="X" * 26, grant="allow_once")
            )

        assert (await runner.pending_approval("b3")) is not None
    assert spawned == []
    assert "approval.resolved" not in [e.type for e in events]


async def test_a_click_for_the_previous_step_cannot_approve_the_next_one(
    open_runner,
) -> None:
    plan = _two_high_risk_steps()
    async with open_runner(reply(_intent("code.task")), reply(plan)) as (
        runner,
        _,
        _,
        spawned,
    ):
        first = await runner.run("go", run_id="b4")
        assert first.approval is not None
        second = await runner.resume(
            "b4",
            ApprovalDecision(
                approval_id=first.approval.approval_id, grant="allow_once"
            ),
        )
        assert second.state == "paused"
        assert second.approval is not None
        assert second.approval.approval_id != first.approval.approval_id

        stale = ApprovalDecision(
            approval_id=first.approval.approval_id, grant="allow_once"
        )
        with pytest.raises(ApprovalMismatch):
            await runner.resume("b4", stale)
        assert len(spawned) == 1

        done = await runner.resume(
            "b4",
            ApprovalDecision(
                approval_id=second.approval.approval_id, grant="allow_once"
            ),
        )
    assert done.state == "finished"
    assert len(spawned) == 2


async def test_the_resolved_event_names_the_approval_it_answered(open_runner) -> None:
    async with open_runner(reply(_spotify_intent())) as (runner, events, *_):
        asked = await runner.run("open Spotify", run_id="b5")
        assert asked.approval is not None
        await runner.resume(
            "b5",
            ApprovalDecision(approval_id=asked.approval.approval_id, grant="deny"),
        )

    resolved = [e for e in events if e.type == "approval.resolved"][-1]
    assert resolved.payload["approval_id"] == asked.approval.approval_id
