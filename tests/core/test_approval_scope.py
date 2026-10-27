"""An approval covers the exact thing the user saw, never "the next app too"."""

import json
from pathlib import Path

import pytest
from conftest import reply

from halo.core.approval import apply_grant
from halo.core.contracts import ApprovalDecision, ApprovalGrant, Step
from halo.skills.app_open import skill as app_open


def _answer_factory(runner):
    async def answer(run_id: str, grant: ApprovalGrant):
        pending = await runner.pending_approval(run_id)
        assert pending is not None
        return await runner.resume(
            run_id, ApprovalDecision(approval_id=pending.approval_id, grant=grant)
        )

    return answer


def _plan(*apps: str) -> str:
    steps = [{"tool": "app.open", "risk": "medium", "args": {"app": a}} for a in apps]
    return json.dumps({"rationale": "t", "steps": steps})


def _intent() -> str:
    return json.dumps({"skill": "code.task", "args": {}, "confidence": 0.95})


def test_a_step_that_cannot_be_granted_ignores_always_for_task() -> None:
    step = Step(tool="app.open", risk="medium", args={"app": "calc"})
    allowed, granted = apply_grant("always_for_task", step, [], grantable=False)
    assert allowed is True
    assert granted == []


def test_a_step_is_grantable_by_default() -> None:
    step = Step(tool="x", risk="medium")
    assert apply_grant("always_for_task", step, [])[1] == ["x"]


def test_only_an_allowlisted_app_open_can_be_granted_for_the_task(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config = tmp_path / "config.toml"
    config.write_text(
        '[apps.vscode]\naliases = ["vscode"]\n[apps.vscode.command]\nwin32 = ["code"]\n'
    )
    monkeypatch.setenv("HALO_CONFIG", str(config))
    assert app_open.grantable({"app": "vscode"}) is True
    assert app_open.grantable({"app": "Notepad"}) is False
    assert app_open.grantable({}) is False


async def test_always_for_task_on_one_unlisted_app_does_not_open_the_next(
    open_runner,
) -> None:
    async with open_runner(reply(_intent()), reply(_plan("calc", "setup"))) as (
        runner,
        events,
        _,
        spawned,
    ):
        answer = _answer_factory(runner)
        first = await runner.run("go", run_id="scope1")
        assert first.state == "paused"
        second = await answer("scope1", "always_for_task")

        # The grant for the first app must not carry over to the second.
        assert second.state == "paused"
        assert len(spawned) == 1
        asked = [e for e in events if e.type == "approval.requested"]
        assert [a.payload["detail"] for a in asked] == [
            "{'app': 'calc'}",
            "{'app': 'setup'}",
        ]
        done = await answer("scope1", "allow_once")

    assert done.state == "finished"
    assert len(spawned) == 2
