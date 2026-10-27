"""Smoke test: the real Claude Code worker in a real worktree.

Costs Claude Code usage, so it only runs with `-m live` and HALO_LIVE_REPO set to a
git repo. The worktree is always discarded; the repo's own checkout is not touched.
"""

import os
from decimal import Decimal
from pathlib import Path

import pytest

from halo.core.contracts import HaloEvent, TaskBrief
from halo.core.worker_approvals import WorkerApprovals
from halo.tools import git_ops
from halo.tools.claude_worker import ClaudeCodeWorker

pytestmark = pytest.mark.live

REPO = os.environ.get("HALO_LIVE_REPO")


@pytest.mark.skipif(not REPO, reason="set HALO_LIVE_REPO to a git repo")
async def test_worker_makes_a_small_change_in_a_worktree_and_leaves_the_checkout_alone() -> (
    None
):
    repo = Path(str(REPO))
    before = git_ops._git(repo, "status", "--porcelain").stdout
    wt = git_ops.create_worktree(repo, "halo-smoke")
    events: list[HaloEvent] = []
    try:
        worker = ClaudeCodeWorker(
            events.append,
            WorkerApprovals(),
            usd_to_inr=Decimal(85),
            max_cost_inr=Decimal(10),
            max_turns=8,
            timeout_s=240,
            approval_timeout_s=1,  # anything that needs a card is denied
        )
        brief = TaskBrief(
            goal="Add a short module docstring to token_count.py saying what the script does",
            acceptance_criteria=[
                "token_count.py starts with a one or two line module docstring",
                "No other behaviour or file changes",
            ],
            likely_files=["day01-tokens-attention-embeddings/token_count.py"],
            test_cmd="git status",
            constraints=["Do not change any code, only add the docstring"],
        )
        out = await worker.run(brief, wt.path, run_id="live-smoke")
        stat = git_ops.diff_stat(wt)
        print(f"status={out.status} cost_inr={out.cost_inr} turns={out.num_turns}")
        print(stat)
        assert out.status in ("done", "max_turns", "budget", "timeout")
        assert out.cost_inr <= Decimal(10) + Decimal(1)
        assert any(e.type == "tool.called" for e in events)
        assert git_ops.changed_files(wt) in (
            [],
            ["day01-tokens-attention-embeddings/token_count.py"],
        )
    finally:
        git_ops.discard_worktree(wt)
    assert git_ops._git(repo, "status", "--porcelain").stdout == before
