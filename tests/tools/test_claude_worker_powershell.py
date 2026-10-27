"""The worker lets its own test command through PowerShell without a card."""

from decimal import Decimal
from pathlib import Path

import claude_agent_sdk as sdk

from halo.core.contracts import HaloEvent, TaskBrief
from halo.core.worker_approvals import WorkerApprovals
from halo.tools.claude_worker import ClaudeCodeWorker

TEST_CMD = "uv run --project day01 --with pytest pytest -q day01"
BRIEF = TaskBrief(goal="g", acceptance_criteria=["c"], test_cmd=TEST_CMD)


def _worker(events: list[HaloEvent]) -> ClaudeCodeWorker:
    async def never(**kwargs):  # the SDK is not used here
        raise AssertionError("no query expected")
        yield  # pragma: no cover

    return ClaudeCodeWorker(
        events.append,
        WorkerApprovals(),
        usd_to_inr=Decimal(80),
        approval_timeout_s=0.05,
        query=never,
    )


async def test_the_test_command_through_powershell_is_allowed_without_a_card(
    tmp_path: Path,
) -> None:
    events: list[HaloEvent] = []
    result = await _worker(events)._permission(
        "run1", tmp_path, BRIEF, "PowerShell", {"command": TEST_CMD}
    )
    assert isinstance(result, sdk.PermissionResultAllow)
    assert events == []


async def test_another_powershell_command_still_asks_and_is_denied_with_no_answer(
    tmp_path: Path,
) -> None:
    events: list[HaloEvent] = []
    result = await _worker(events)._permission(
        "run1", tmp_path, BRIEF, "PowerShell", {"command": "Remove-Item -Recurse x"}
    )
    assert isinstance(result, sdk.PermissionResultDeny)
    assert next(e.type for e in events) == "approval.requested"
