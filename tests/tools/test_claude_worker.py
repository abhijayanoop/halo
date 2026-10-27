import asyncio
from decimal import Decimal
from pathlib import Path

import claude_agent_sdk as sdk
import pytest

from halo.core.contracts import HaloEvent, TaskBrief
from halo.core.worker_approvals import WorkerApprovals
from halo.security.taint import Tainted
from halo.tools.claude_worker import ClaudeCodeWorker, WorkerResult

BRIEF = TaskBrief(
    goal="Add rate limiting",
    acceptance_criteria=["Over-limit requests get 429"],
    test_cmd="uv run pytest -q",
    constraints=["No new dependencies"],
    out_of_scope=["Auth"],
)


def assistant(*blocks, parent=None) -> sdk.AssistantMessage:
    return sdk.AssistantMessage(
        content=list(blocks), model="m", parent_tool_use_id=parent
    )


def tool_use(id: str, name: str = "Read", **input) -> sdk.ToolUseBlock:
    return sdk.ToolUseBlock(id=id, name=name, input=input)


def tool_result(id: str, content="ok", parent=None, is_error=False) -> sdk.UserMessage:
    return sdk.UserMessage(
        content=[
            sdk.ToolResultBlock(tool_use_id=id, content=content, is_error=is_error)
        ],
        parent_tool_use_id=parent,
    )


def result(subtype="success", is_error=False, cost=0.1, text="All done", turns=3):
    return sdk.ResultMessage(
        subtype=subtype,
        duration_ms=10,
        duration_api_ms=8,
        is_error=is_error,
        num_turns=turns,
        session_id="sess-1",
        total_cost_usd=cost,
        result=text,
    )


class Harness:
    def __init__(self, tmp_path: Path, messages=(), **kw) -> None:
        self.events: list[HaloEvent] = []
        self.approvals = WorkerApprovals()
        self.worktree = tmp_path / "wt"
        self.worktree.mkdir(exist_ok=True)
        self.options: sdk.ClaudeAgentOptions | None = None
        self.prompt = ""
        self.messages = list(messages)
        self.script = kw.pop("script", None)

        async def fake_query(*, prompt, options):
            self.prompt, self.options = prompt, options
            if self.script is not None:
                async for m in self.script(self):
                    yield m
                return
            for m in self.messages:
                yield m

        self.worker = ClaudeCodeWorker(
            self.events.append,
            self.approvals,
            usd_to_inr=Decimal(80),
            query=fake_query,
            **kw,
        )

    async def run(self, **kw) -> WorkerResult:
        return await self.worker.run(BRIEF, self.worktree, run_id="run1", **kw)

    def types(self) -> list[str]:
        return [e.type for e in self.events]


async def test_options_confine_the_worker_to_its_worktree(tmp_path: Path) -> None:
    h = Harness(tmp_path, [result()])
    await h.run()
    o = h.options
    assert o is not None
    assert Path(str(o.cwd)) == h.worktree
    assert o.permission_mode == "acceptEdits"
    assert o.setting_sources == []
    assert o.max_turns == 30
    assert o.max_budget_usd == pytest.approx(1.875)  # 150 rupees at 80 per dollar
    assert "Bash(uv run pytest -q *)" in o.allowed_tools
    assert "Bash" not in o.allowed_tools
    assert {"WebFetch", "WebSearch"} <= set(o.disallowed_tools)
    assert o.can_use_tool is not None
    assert o.hooks and "PreToolUse" in o.hooks
    assert o.resume is None


async def test_resume_and_feedback_continue_the_saved_session(tmp_path: Path) -> None:
    h = Harness(tmp_path, [result()])
    await h.run(session_id="sess-0", feedback="Also return a Retry-After header")
    assert h.options is not None and h.options.resume == "sess-0"
    assert "Retry-After" in h.prompt


async def test_the_prompt_carries_the_whole_brief(tmp_path: Path) -> None:
    h = Harness(tmp_path, [result()])
    await h.run()
    for needle in (
        "Add rate limiting",
        "Over-limit requests get 429",
        "No new dependencies",
        "Auth",
        "uv run pytest -q",
    ):
        assert needle in h.prompt


async def test_tool_use_and_result_become_events(tmp_path: Path) -> None:
    h = Harness(
        tmp_path,
        [
            assistant(tool_use("t1", "Read", file_path="src/a.py")),
            tool_result("t1", "def a(): ..."),
            result(),
        ],
    )
    await h.run()
    called = next(e for e in h.events if e.type == "tool.called")
    done = next(e for e in h.events if e.type == "tool.result")
    assert called.run_id == "run1" and called.agent_id == "claude-code"
    assert called.payload["tool"] == "Read"
    assert called.payload["tool_use_id"] == "t1"
    assert done.payload["tool_use_id"] == "t1" and done.payload["is_error"] is False


async def test_tool_output_in_events_is_cleaned_and_short(tmp_path: Path) -> None:
    dirty = "\x1b[31mred\x1b[0m " + "x" * 5000
    h = Harness(
        tmp_path,
        [assistant(tool_use("t1")), tool_result("t1", dirty), result()],
    )
    await h.run()
    preview = next(e for e in h.events if e.type == "tool.result").payload["preview"]
    assert "\x1b" not in preview and len(preview) <= 300


async def test_a_sub_agent_is_spawned_parented_and_finished(tmp_path: Path) -> None:
    h = Harness(
        tmp_path,
        [
            assistant(tool_use("sub1", "Task", description="explore the tests")),
            assistant(tool_use("t2", "Grep", pattern="x"), parent="sub1"),
            tool_result("t2", parent="sub1"),
            tool_result("sub1", "explored"),
            result(),
        ],
    )
    await h.run()
    spawned = next(e for e in h.events if e.type == "agent.spawned")
    assert spawned.agent_id == "sub1" and spawned.parent_agent_id == "claude-code"
    inner = next(
        e for e in h.events if e.type == "tool.called" and e.payload["tool"] == "Grep"
    )
    assert inner.agent_id == "sub1"
    assert any(e.type == "agent.finished" and e.agent_id == "sub1" for e in h.events)


async def test_success_returns_the_session_cost_in_rupees_and_a_tainted_summary(
    tmp_path: Path,
) -> None:
    h = Harness(tmp_path, [result(cost=0.25, text="Done \x1b[31mred")])
    out = await h.run()
    assert out.status == "done"
    assert out.session_id == "sess-1"
    assert out.cost_inr == Decimal("20.00")
    assert out.num_turns == 3
    assert isinstance(out.summary, Tainted) and out.summary.source == "claude_code"
    assert "\x1b" not in out.summary.value
    cost = next(e for e in h.events if e.type == "cost.updated")
    assert cost.payload["cost_inr"] == "20.00"
    assert cost.payload["source"] == "claude_code"


@pytest.mark.parametrize(
    ("subtype", "status"),
    [
        ("error_max_turns", "max_turns"),
        ("error_max_budget_usd", "budget"),
        ("error_during_execution", "error"),
    ],
)
async def test_an_error_result_is_a_status_not_a_crash(
    tmp_path: Path, subtype: str, status: str
) -> None:
    async def script(h):
        yield result(subtype=subtype, is_error=True, cost=0.3)
        # the SDK raises after it has yielded the result
        raise sdk.ResultError("exit 1", {"subtype": subtype}, 1)

    h = Harness(tmp_path, script=script)
    out = await h.run()
    assert out.status == status
    assert out.cost_inr == Decimal("24.00")  # partial cost is kept
    assert out.session_id == "sess-1"


async def test_a_crash_with_no_result_is_an_error_status(tmp_path: Path) -> None:
    async def script(h):
        yield assistant(tool_use("t1"))
        raise sdk.ProcessError("boom", exit_code=2)

    h = Harness(tmp_path, script=script)
    out = await h.run()
    assert out.status == "error"
    assert "boom" not in out.summary.value  # fixed reason, never the exception text


async def test_the_wall_clock_timeout_stops_the_worker(tmp_path: Path) -> None:
    async def script(h):
        yield assistant(tool_use("t1"))
        await asyncio.sleep(30)
        yield result()

    h = Harness(tmp_path, script=script, timeout_s=0.1)
    out = await h.run()
    assert out.status == "timeout"


async def test_stop_cancels_the_run_and_denies_waiting_cards(tmp_path: Path) -> None:
    async def script(h):
        await h.options.can_use_tool(
            "Bash", {"command": "make deploy"}, sdk.ToolPermissionContext()
        )
        yield result()

    h = Harness(tmp_path, script=script)
    task = asyncio.create_task(h.run())
    for _ in range(50):
        await asyncio.sleep(0.01)
        if h.approvals.has_pending("run1"):
            break
    assert h.approvals.has_pending("run1")
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not h.approvals.has_pending("run1")


async def _ask(h: Harness, tool: str, args: dict, answer: str | None):
    """Drive can_use_tool the way the SDK would, answering through the registry."""
    decision: list = []

    async def script(_h):
        decision.append(
            await _h.options.can_use_tool(tool, args, sdk.ToolPermissionContext())
        )
        yield result()

    h.script = script
    task = asyncio.create_task(h.run())
    if answer is not None:
        for _ in range(100):
            await asyncio.sleep(0.01)
            card = next((e for e in h.events if e.type == "approval.requested"), None)
            if card:
                h.approvals.resolve("run1", card.payload["approval_id"], answer)  # type: ignore[arg-type]
                break
    await task
    return decision[0]


async def test_an_unlisted_command_asks_on_a_card_and_runs_after_allow(
    tmp_path: Path,
) -> None:
    h = Harness(tmp_path, approval_timeout_s=5)
    d = await _ask(h, "Bash", {"command": "make build"}, "allow_once")
    assert isinstance(d, sdk.PermissionResultAllow)
    card = next(e for e in h.events if e.type == "approval.requested")
    assert card.payload["risk"] == "high" and "make build" in card.payload["detail"]
    assert any(e.type == "approval.resolved" for e in h.events)


async def test_deny_on_the_card_denies_the_tool(tmp_path: Path) -> None:
    h = Harness(tmp_path, approval_timeout_s=5)
    d = await _ask(h, "Bash", {"command": "make build"}, "deny")
    assert isinstance(d, sdk.PermissionResultDeny)


async def test_no_answer_denies_the_tool(tmp_path: Path) -> None:
    h = Harness(tmp_path, approval_timeout_s=0.05)
    d = await _ask(h, "Bash", {"command": "make build"}, None)
    assert isinstance(d, sdk.PermissionResultDeny)


async def test_an_edit_outside_the_worktree_is_denied_without_a_card(
    tmp_path: Path,
) -> None:
    h = Harness(tmp_path)
    d = await _ask(h, "Edit", {"file_path": "../../.ssh/config"}, None)
    assert isinstance(d, sdk.PermissionResultDeny)
    assert "approval.requested" not in h.types()


async def test_the_pre_tool_hook_blocks_what_policy_denies(tmp_path: Path) -> None:
    out: list = []

    async def script(h):
        hook = h.options.hooks["PreToolUse"][0].hooks[0]
        bad = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "/etc/passwd"},
        }
        good = {
            "hook_event_name": "PreToolUse",
            "tool_name": "Write",
            "tool_input": {"file_path": "src/a.py"},
        }
        out.append(await hook(bad, "t1", {"signal": None}))
        out.append(await hook(good, "t2", {"signal": None}))
        yield result()

    h = Harness(tmp_path, script=script)
    await h.run()
    assert out[0]["hookSpecificOutput"]["permissionDecision"] == "deny"
    assert not out[1].get("hookSpecificOutput", {}).get("permissionDecision")
