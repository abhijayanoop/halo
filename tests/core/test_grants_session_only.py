"""An "always for this task" grant lives for the session only: it covers the
rest of the task but is never written to the on-disk checkpoint."""

import json
from pathlib import Path

import pytest
from conftest import reply

from halo.core.contracts import ApprovalDecision


def _plan(*apps: str) -> str:
    steps = [{"tool": "app.open", "risk": "medium", "args": {"app": a}} for a in apps]
    return json.dumps({"rationale": "t", "steps": steps})


def _intent() -> str:
    return json.dumps({"skill": "code.task", "args": {}, "confidence": 0.95})


@pytest.fixture
def allowlisted_vscode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config = tmp_path / "config.toml"
    # Every platform has a launch command, so the test is the same on Windows,
    # macOS and the Linux CI runner.
    config.write_text(
        '[apps.vscode]\naliases = ["vscode"]\n[apps.vscode.command]\n'
        'win32 = ["code"]\ndarwin = ["code"]\nlinux = ["code"]\n'
    )
    monkeypatch.setenv("HALO_CONFIG", str(config))


async def test_an_always_grant_covers_the_rest_of_the_task(
    open_runner, allowlisted_vscode
) -> None:
    async with open_runner(reply(_intent()), reply(_plan("vscode", "vscode"))) as (
        runner,
        events,
        _,
        spawned,
    ):
        first = await runner.run("go", run_id="g1")
        assert first.state == "paused"
        pending = await runner.pending_approval("g1")
        assert pending is not None
        done = await runner.resume(
            "g1",
            ApprovalDecision(approval_id=pending.approval_id, grant="always_for_task"),
        )

    assert done.state == "finished"
    assert len(spawned) == 2
    assert len([e for e in events if e.type == "approval.requested"]) == 1


async def test_an_always_grant_is_never_written_to_the_checkpoint(
    open_runner, allowlisted_vscode
) -> None:
    async with open_runner(reply(_intent()), reply(_plan("vscode", "vscode"))) as (
        runner,
        _events,
        _,
        _spawned,
    ):
        await runner.run("go", run_id="g2")
        pending = await runner.pending_approval("g2")
        assert pending is not None
        await runner.resume(
            "g2",
            ApprovalDecision(approval_id=pending.approval_id, grant="always_for_task"),
        )
        snapshot = await runner._graph.aget_state(runner._config("g2"))

    assert not snapshot.values.get("granted_tools")
