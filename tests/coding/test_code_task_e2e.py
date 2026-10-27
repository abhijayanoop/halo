"""A request through the whole app: router -> plan -> code.task -> cards -> merge."""

import asyncio
import json
import subprocess
from decimal import Decimal
from pathlib import Path

from conftest import reply

from halo.bootstrap import open_halo
from halo.config import VaultConfig, load_config
from halo.core.code_decisions import CodeDecision
from halo.security.taint import Tainted
from halo.tools.claude_worker import WorkerResult


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-c", "user.name=t", "-c", "user.email=t@t", *args],
        cwd=repo,
        check=True,
        capture_output=True,
        text=True,
    ).stdout


class _Worker:
    def __init__(self) -> None:
        self.calls = 0

    async def run(self, brief, worktree, *, run_id, session_id=None, feedback=None):
        self.calls += 1
        (worktree / "hello.txt").write_text("hello\n")
        return WorkerResult(
            "done",
            Tainted("Added hello.txt", source="claude_code"),
            "sess-1",
            Decimal(3),
            1,
        )


async def test_a_coding_request_runs_end_to_end_and_merges_only_on_the_click(
    tmp_path: Path, make_client, monkeypatch
) -> None:
    repo = tmp_path / "proj"
    repo.mkdir()
    _git(repo, "init", "-q", "-b", "main")
    (repo / "README.md").write_text("# proj\n")
    _git(repo, "add", "-A")
    _git(repo, "commit", "-q", "-m", "init")
    vault = tmp_path / "vault"
    (vault / "Projects").mkdir(parents=True)
    (vault / "Projects" / "proj.md").write_text(
        f"---\nprivacy: shared\npath: {repo}\ntest_cmd: git status\n---\n# proj\n",
        encoding="utf-8",
    )
    config_file = tmp_path / "config.toml"
    config_file.write_text("")
    monkeypatch.setenv("HALO_CONFIG", str(config_file))
    config = load_config().model_copy(update={"vault": VaultConfig(path=vault)})

    args = {"task": "add a hello file", "mode": "implement"}
    script = [
        reply(json.dumps({"skill": "code.task", "args": args, "confidence": 0.95})),
        reply(
            json.dumps(
                {
                    "rationale": "one coding session",
                    "steps": [{"tool": "code.task", "args": args, "risk": "low"}],
                }
            )
        ),
        reply(
            json.dumps(
                {
                    "goal": "Add a hello file",
                    "acceptance_criteria": ["hello.txt exists"],
                    "likely_files": [],
                    "test_cmd": "rm -rf /",
                }
            )
        ),
        reply(json.dumps({"result": "pass", "summary": "ok", "issues": []})),
    ]
    worker = _Worker()
    async with (
        open_halo(
            config,
            home=tmp_path / "home",
            client_factory=lambda emit: make_client(*script, emit=emit)[0],
            worker_factory=lambda emit, approvals: worker,
        ) as halo,
        halo.bus.subscribe() as queue,
    ):
        run = asyncio.create_task(halo.runner.run("add a hello file", run_id="r1"))
        seen = []

        async def next_card(kind: str) -> dict:
            for _ in range(400):
                event = await asyncio.wait_for(queue.get(), 30)
                seen.append(event)
                if (
                    event.type == "approval.requested"
                    and event.payload.get("kind") == kind
                ):
                    return event.payload
            raise AssertionError(f"no {kind} card")

        brief = await next_card("code.brief")
        assert worker.calls == 0
        assert not (tmp_path / ".halo-worktrees").exists()
        assert halo.code_decisions.resolve(
            "r1", brief["approval_id"], CodeDecision(action="approve")
        )
        result = await next_card("code.result")
        assert result["tests"]["passed"] and result["changed_files"] == ["hello.txt"]
        assert not (repo / "hello.txt").exists()  # nothing merged yet
        assert halo.code_decisions.resolve(
            "r1", result["approval_id"], CodeDecision(action="merge")
        )
        outcome = await asyncio.wait_for(run, 60)

    assert outcome.result_status == "ok"
    assert (repo / "hello.txt").read_text() == "hello\n"
    assert _git(repo, "branch", "--list", "halo/*").strip() == ""
    assert outcome.state == "finished"
