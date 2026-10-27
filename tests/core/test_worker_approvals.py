import asyncio

import pytest

from halo.core.contracts import ApprovalRequest
from halo.core.worker_approvals import WorkerApprovals


def _req(approval_id: str = "a1") -> ApprovalRequest:
    return ApprovalRequest(
        approval_id=approval_id, action="Bash", detail="make", risk="high"
    )


async def _pending(approvals: WorkerApprovals, run_id: str = "r1", aid: str = "a1"):
    task = asyncio.create_task(approvals.ask(run_id, _req(aid), timeout=5))
    await asyncio.sleep(0)
    return task


async def test_allow_once_resolves_the_waiting_request() -> None:
    approvals = WorkerApprovals()
    task = await _pending(approvals)
    assert approvals.owns("r1", "a1")
    assert approvals.resolve("r1", "a1", "allow_once")
    assert await task == "allow_once"
    assert not approvals.has_pending("r1")


async def test_always_for_task_never_sticks_for_worker_tools() -> None:
    approvals = WorkerApprovals()
    task = await _pending(approvals)
    approvals.resolve("r1", "a1", "always_for_task")
    assert await task == "allow_once"


async def test_wrong_approval_id_is_not_resolved_and_the_request_keeps_waiting() -> (
    None
):
    approvals = WorkerApprovals()
    task = await _pending(approvals)
    assert approvals.has_pending("r1")
    assert not approvals.owns("r1", "other")
    assert not approvals.resolve("r1", "other", "allow_once")
    assert not task.done()
    approvals.resolve("r1", "a1", "deny")
    assert await task == "deny"


async def test_an_answer_for_another_run_does_nothing() -> None:
    approvals = WorkerApprovals()
    task = await _pending(approvals)
    assert not approvals.resolve("r2", "a1", "allow_once")
    assert not task.done()
    approvals.deny_run("r1")
    assert await task == "deny"


async def test_a_request_nobody_answers_is_denied_after_the_timeout() -> None:
    approvals = WorkerApprovals()
    assert await approvals.ask("r1", _req(), timeout=0.01) == "deny"
    assert not approvals.has_pending("r1")


async def test_a_second_answer_to_the_same_request_is_refused() -> None:
    approvals = WorkerApprovals()
    task = await _pending(approvals)
    assert approvals.resolve("r1", "a1", "allow_once")
    assert not approvals.resolve("r1", "a1", "deny")
    assert await task == "allow_once"


async def test_several_requests_can_wait_at_once() -> None:
    approvals = WorkerApprovals()
    t1 = await _pending(approvals, aid="a1")
    t2 = await _pending(approvals, aid="a2")
    approvals.resolve("r1", "a2", "allow_once")
    approvals.resolve("r1", "a1", "deny")
    assert (await t1, await t2) == ("deny", "allow_once")


async def test_unknown_grant_is_rejected() -> None:
    approvals = WorkerApprovals()
    task = await _pending(approvals)
    with pytest.raises(ValueError):
        approvals.resolve("r1", "a1", "sure")  # type: ignore[arg-type]
    approvals.deny_run("r1")
    await task
