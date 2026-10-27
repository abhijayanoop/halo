import asyncio
import json
import subprocess
from datetime import datetime
from decimal import Decimal
from pathlib import Path

import pytest
from conftest import reply

from halo.coding.session import CodeDeps, run_code_task
from halo.config import CodingConfig
from halo.core.code_decisions import CodeDecision, CodeDecisions
from halo.core.contracts import HaloEvent, TaskBrief
from halo.memory import project_note
from halo.security.taint import Tainted
from halo.tools.claude_worker import WorkerResult

NOW = datetime(2026, 10, 27, 12, 0)
RUN = "run1"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def make_repo(root: Path) -> Path:
    repo = root / "proj"
    repo.mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("# proj\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo


def make_vault(root: Path, repo: Path, *, name="demo", test_cmd="git status") -> Path:
    vault = root / "vault"
    (vault / "Projects").mkdir(parents=True, exist_ok=True)
    (vault / "Projects" / f"{name}.md").write_text(
        "---\nprivacy: shared\n"
        f"path: {repo}\ndefault_branch: main\ntest_cmd: {test_cmd}\n"
        'stack: Python\nclaude_session_id: ""\nlast_stop: ""\n---\n# Demo\n',
        encoding="utf-8",
    )
    return vault


def brief_json(**over) -> str:
    data = {
        "goal": "Add a hello file",
        "acceptance_criteria": ["hello.txt exists"],
        "likely_files": ["README.md"],
        "test_cmd": "rm -rf /",
        "constraints": [],
        "out_of_scope": [],
    }
    data.update(over)
    return json.dumps(data)


def review_json(result="pass") -> str:
    return json.dumps({"result": result, "summary": "Looks right", "issues": []})


class FakeWorker:
    def __init__(self, *, status="done", name="hello.txt") -> None:
        self.status = status
        self.name = name
        self.calls: list[dict] = []

    async def run(
        self, brief, worktree, *, run_id, session_id=None, feedback=None
    ) -> WorkerResult:
        self.calls.append(
            {
                "brief": brief,
                "worktree": worktree,
                "session_id": session_id,
                "feedback": feedback,
            }
        )
        (worktree / self.name).write_text(f"hello {len(self.calls)}\n")
        return WorkerResult(
            self.status,  # type: ignore[arg-type]
            Tainted("Added the hello file", source="claude_code"),
            f"sess-{len(self.calls)}",
            Decimal("5.00"),
            2,
        )


class Rig:
    def __init__(
        self, tmp_path: Path, make_client, *script, test_cmd="git status", **cfg
    ):
        self.repo = make_repo(tmp_path)
        self.vault = make_vault(tmp_path, self.repo, test_cmd=test_cmd)
        self.events: list[HaloEvent] = []
        self.client, self.transport, _ = make_client(*script, emit=self.events.append)
        self.worker = FakeWorker()
        self.decisions = CodeDecisions()
        coding = CodingConfig(
            approval_timeout_s=cfg.pop("approval_timeout_s", 5),
            test_timeout_s=30,
            result_timeout_s=cfg.pop("result_timeout_s", 5),
        )
        self.deps = CodeDeps(
            self.worker,
            self.decisions,
            self.vault,
            coding,
            cache_dir=tmp_path / "cache",
        )
        self.worktrees = tmp_path / ".halo-worktrees"

    def start(self, **args) -> asyncio.Task:
        full = {"project": "demo", "task": "add a hello file", "mode": "implement"}
        full.update(args)
        return asyncio.create_task(
            run_code_task(
                self.client, self.deps, self.events.append, RUN, full, now=NOW
            )
        )

    def cards(self, kind: str) -> list[dict]:
        return [
            e.payload
            for e in self.events
            if e.type == "approval.requested" and e.payload.get("kind") == kind
        ]

    async def card(self, kind: str, count: int = 1) -> dict:
        for _ in range(500):
            found = self.cards(kind)
            if len(found) >= count:
                return found[count - 1]
            await asyncio.sleep(0.01)
        raise AssertionError(f"no {kind} card #{count}")

    async def answer(self, kind: str, decision: CodeDecision, count: int = 1) -> dict:
        card = await self.card(kind, count)
        assert self.decisions.resolve(RUN, card["approval_id"], decision)
        return card


@pytest.fixture
def rig(tmp_path: Path, make_client):
    def build(*script, **kw) -> Rig:
        return Rig(tmp_path, make_client, *script, **kw)

    return build


async def test_nothing_is_created_and_the_worker_is_not_started_before_the_brief_is_approved(
    rig,
) -> None:
    r = rig(reply(brief_json()))
    task = r.start()
    card = await r.card("code.brief")
    assert card["brief"]["goal"] == "Add a hello file"
    assert card["risk"] == "medium" and card["project"] == "demo"
    assert r.worker.calls == []
    assert not r.worktrees.exists()
    assert git(r.repo, "branch", "--list", "halo/*").strip() == ""
    r.decisions.deny_run(RUN)
    await task


async def test_denying_the_brief_ends_the_session_with_nothing_started(rig) -> None:
    r = rig(reply(brief_json()))
    task = r.start()
    await r.answer("code.brief", CodeDecision(action="deny"))
    out = await task
    assert out["outcome"] == "denied"
    assert r.worker.calls == [] and not r.worktrees.exists()
    resolved = [e for e in r.events if e.type == "approval.resolved"]
    assert resolved and resolved[-1].payload["grant"] == "deny"


async def test_an_approved_brief_runs_the_worker_in_a_worktree_and_shows_the_result(
    rig,
) -> None:
    r = rig(reply(brief_json()), reply(review_json()))
    task = r.start()
    await r.answer("code.brief", CodeDecision(action="approve"))
    result = await r.card("code.result")
    call = r.worker.calls[0]
    assert ".halo-worktrees" in call["worktree"].as_posix()
    assert call["brief"].test_cmd == "git status"  # from the note, not the model
    assert result["tests"]["passed"] is True
    assert result["review"]["result"] == "pass"
    assert result["changed_files"] == ["hello.txt"]
    assert result["status"] == "done" and result["cost_inr"]
    assert result["branch"].startswith("halo/")
    assert result["iteration"] == 1
    await r.answer("code.result", CodeDecision(action="discard"))
    out = await task
    assert out["outcome"] == "discarded"
    assert not call["worktree"].exists()
    assert git(r.repo, "branch", "--list", "halo/*").strip() == ""
    assert not (r.repo / "hello.txt").exists()  # the checkout was never touched


async def test_an_edited_brief_is_used_but_its_test_command_and_files_are_not_trusted(
    rig,
) -> None:
    r = rig(reply(brief_json()), reply(review_json()))
    task = r.start()
    edited = TaskBrief(
        goal="Add a hello file, in French",
        acceptance_criteria=["bonjour.txt exists"],
        likely_files=["README.md", "../../.ssh/id_rsa", "ghost.py"],
        test_cmd="rm -rf /",
    )
    await r.answer("code.brief", CodeDecision(action="approve", brief=edited))
    await r.card("code.result")
    sent = r.worker.calls[0]["brief"]
    assert sent.goal == "Add a hello file, in French"
    assert sent.test_cmd == "git status"
    assert sent.likely_files == ["README.md"]
    await r.answer("code.result", CodeDecision(action="discard"))
    await task


async def test_merge_lands_the_change_on_main_and_removes_the_worktree(rig) -> None:
    r = rig(reply(brief_json()), reply(review_json()))
    task = r.start()
    await r.answer("code.brief", CodeDecision(action="approve"))
    await r.card("code.result")
    wt = r.worker.calls[0]["worktree"]
    await r.answer("code.result", CodeDecision(action="merge"))
    out = await task
    assert out["outcome"] == "merged"
    assert (r.repo / "hello.txt").read_text() == "hello 1\n"
    assert not wt.exists()
    assert git(r.repo, "branch", "--show-current").strip() == "main"


async def test_a_dirty_checkout_refuses_the_merge_and_the_card_comes_back_with_the_reason(
    rig,
) -> None:
    r = rig(reply(brief_json()), reply(review_json()))
    task = r.start()
    await r.answer("code.brief", CodeDecision(action="approve"))
    await r.card("code.result")
    (r.repo / "README.md").write_text("# edited by the user\n")  # a tracked change
    await r.answer("code.result", CodeDecision(action="merge"))
    second = await r.card("code.result", count=2)
    assert "uncommitted" in second["notice"]
    assert (r.repo / "README.md").read_text() == "# edited by the user\n"
    assert not (r.repo / "hello.txt").exists()
    await r.answer("code.result", CodeDecision(action="discard"), count=2)
    assert (await task)["outcome"] == "discarded"


async def test_iterate_resumes_the_saved_session_with_the_feedback(rig) -> None:
    r = rig(reply(brief_json()), reply(review_json()), reply(review_json()))
    task = r.start()
    await r.answer("code.brief", CodeDecision(action="approve"))
    await r.card("code.result")
    await r.answer(
        "code.result", CodeDecision(action="iterate", feedback="use a greeting")
    )
    second = await r.card("code.result", count=2)
    assert second["iteration"] == 2
    first, again = r.worker.calls
    assert first["session_id"] is None and first["feedback"] is None
    assert again["session_id"] == "sess-1" and again["feedback"] == "use a greeting"
    assert again["worktree"] == first["worktree"]
    await r.answer("code.result", CodeDecision(action="discard"), count=2)
    await task


async def test_iterate_without_feedback_is_not_accepted(rig) -> None:
    r = rig(reply(brief_json()), reply(review_json()))
    task = r.start()
    await r.answer("code.brief", CodeDecision(action="approve"))
    await r.card("code.result")
    await r.answer("code.result", CodeDecision(action="iterate"))
    second = await r.card("code.result", count=2)
    assert "feedback" in second["notice"].lower()
    assert len(r.worker.calls) == 1
    await r.answer("code.result", CodeDecision(action="discard"), count=2)
    await task


async def test_failing_tests_are_shown_as_failing_and_cap_the_review(
    tmp_path: Path, make_client
) -> None:
    r = Rig(
        tmp_path,
        make_client,
        reply(brief_json()),
        reply(review_json("pass")),
        test_cmd="git no-such-subcommand-xyz",
    )
    task = r.start()
    await r.answer("code.brief", CodeDecision(action="approve"))
    result = await r.card("code.result")
    assert result["tests"]["passed"] is False
    assert (
        result["review"]["result"] == "concerns"
    )  # the model said pass; the tests did not
    await r.answer("code.result", CodeDecision(action="discard"))
    await task


async def test_a_worker_that_stopped_early_still_gets_a_result_card(rig) -> None:
    r = rig(reply(brief_json()), reply(review_json("concerns")))
    r.worker.status = "budget"
    task = r.start()
    await r.answer("code.brief", CodeDecision(action="approve"))
    result = await r.card("code.result")
    assert result["status"] == "budget"
    await r.answer("code.result", CodeDecision(action="discard"))
    await task


async def test_stop_before_the_result_card_discards_the_worktree_and_clears_cards(
    rig,
) -> None:
    r = rig(reply(brief_json()), reply(review_json()))
    task = r.start()
    await r.answer("code.brief", CodeDecision(action="approve"))
    await r.card("code.result")
    wt = r.worker.calls[0]["worktree"]
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not r.decisions.has_pending(RUN)
    assert not wt.exists()
    assert git(r.repo, "branch", "--list", "halo/*").strip() == ""


async def test_an_unanswered_result_card_keeps_the_worktree_and_says_where(
    rig,
) -> None:
    r = rig(reply(brief_json()), reply(review_json()), result_timeout_s=0.2)
    task = r.start()
    await r.answer("code.brief", CodeDecision(action="approve"))
    out = await task
    assert out["outcome"] == "kept"
    assert r.worker.calls[0]["worktree"].exists()
    assert out["branch"].startswith("halo/") and str(out["worktree"])


async def test_the_project_note_records_where_the_session_stopped(rig) -> None:
    r = rig(reply(brief_json()), reply(review_json()))
    task = r.start()
    await r.answer("code.brief", CodeDecision(action="approve"))
    await r.card("code.result")
    await r.answer("code.result", CodeDecision(action="discard"))
    await task
    note = project_note.load(r.vault, "demo")
    assert note.claude_session_id == "sess-1"
    assert note.last_stop.startswith("2026-10-27")
    assert "discarded" in (r.vault / "Projects" / "demo.md").read_text()


async def test_the_model_cannot_pick_the_directory(rig, tmp_path: Path) -> None:
    r = rig(reply(brief_json()))
    task = r.start(path=str(tmp_path / "elsewhere"), repo="/etc")
    card = await r.card("code.brief")
    assert card["project"] == "demo"
    r.decisions.deny_run(RUN)
    await task
    assert r.worker.calls == []


async def test_an_unknown_project_is_an_error(rig) -> None:
    r = rig()
    out = await r.start(project="../../etc")
    assert "error" in out
    out = await r.start(project="nope")
    assert "error" in out


async def test_a_missing_project_uses_the_only_one_and_asks_when_there_are_several(
    tmp_path: Path, make_client
) -> None:
    r = Rig(tmp_path, make_client, reply(brief_json()))
    task = asyncio.create_task(
        run_code_task(
            r.client,
            r.deps,
            r.events.append,
            RUN,
            {"task": "add a hello file", "mode": "implement"},
            now=NOW,
        )
    )
    card = await r.card("code.brief")
    assert card["project"] == "demo"
    r.decisions.deny_run(RUN)
    await task

    make_vault(tmp_path, r.repo, name="other")
    out = await run_code_task(
        r.client,
        r.deps,
        r.events.append,
        RUN,
        {"task": "x", "mode": "implement"},
        now=NOW,
    )
    assert "which project" in out["answer"].lower()
    assert "demo" in out["answer"] and "other" in out["answer"]


async def test_a_vague_task_or_bad_mode_is_an_error_not_a_guess(rig) -> None:
    r = rig()
    assert "error" in await r.start(task="  ")
    assert "error" in await r.start(mode="deploy")


@pytest.mark.parametrize("mode", ["explain", "plan"])
async def test_explain_and_plan_answer_from_the_repo_without_a_worker_or_worktree(
    rig, mode: str
) -> None:
    r = rig(reply("The repo is a tiny README project."))
    out = await r.start(mode=mode, task="what is in this repo?")
    assert out["outcome"] == {"explain": "explained", "plan": "planned"}[mode]
    assert "tiny README" in out["answer"]
    assert r.worker.calls == [] and not r.worktrees.exists()
    assert r.cards("code.brief") == []
    assert r.transport.calls[0]["model_id"] == "super-id"


async def test_a_worker_failure_still_cleans_up(rig) -> None:
    r = rig(reply(brief_json()))

    async def boom(*a, **k):
        raise RuntimeError("worker exploded")

    r.worker.run = boom  # type: ignore[method-assign]
    task = r.start()
    await r.answer("code.brief", CodeDecision(action="approve"))
    with pytest.raises(RuntimeError):
        await task
    assert not r.decisions.has_pending(RUN)
    assert git(r.repo, "branch", "--list", "halo/*").strip() == ""
    assert not r.worktrees.exists() or not any(r.worktrees.rglob("hello.txt"))
