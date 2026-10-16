"""Memory inside the graph: what goes into the prompts, what the HUD is told, and
the memory skills running end to end."""

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from pathlib import Path

import pytest
from conftest import reply

from halo.core.contracts import ApprovalDecision
from halo.core.graph import GraphDeps, build_graph, open_checkpointer
from halo.core.runner import HaloRunner
from halo.memory.store import MemoryStore
from halo.skills.registry import SkillRegistry, default_skills_dir

NOW = datetime(2026, 10, 17, tzinfo=UTC)


def _intent(skill: str, **args) -> str:
    return json.dumps({"skill": skill, "args": args, "confidence": 0.95})


@pytest.fixture
def memory(tmp_path: Path):
    store = MemoryStore(tmp_path / "vault", tmp_path / "memory.db", clock=lambda: NOW)
    store.start()
    yield store
    store.close()


@pytest.fixture
def memory_runner(tmp_path: Path, make_client, memory: MemoryStore):
    @asynccontextmanager
    async def opener(*script):
        events: list = []
        client, transport, _ = make_client(*script, emit=events.append)
        registry = SkillRegistry.load(default_skills_dir())
        async with open_checkpointer(tmp_path / "cp.db") as checkpointer:
            graph = build_graph(
                GraphDeps(client, registry, events.append, memory=memory), checkpointer
            )
            yield HaloRunner(graph, events.append), events, transport

    return opener


def _system(transport, call: int = 0) -> str:
    return transport.calls[call]["messages"][0]["content"]


async def test_what_you_know_goes_into_the_router_prompt_with_its_source(
    memory_runner, memory
) -> None:
    memory.remember("I picked pywebview for the HUD window", note="Projects/halo.md")
    async with memory_runner(reply(_intent("memory.recall", query="HUD"))) as (
        runner,
        _events,
        transport,
    ):
        await runner.run("what did I pick for the HUD window?", run_id="m1")
    system = _system(transport)
    assert "What you know, with sources" in system
    assert "I picked pywebview for the HUD window" in system
    assert "Projects/halo.md" in system


async def test_the_hud_is_told_exactly_which_memories_went_into_the_prompt(
    memory_runner, memory
) -> None:
    memory.remember("I picked pywebview for the HUD window", note="Projects/halo.md")
    async with memory_runner(reply(_intent("memory.recall", query="HUD"))) as (
        runner,
        events,
        _,
    ):
        await runner.run("what did I pick for the HUD window?", run_id="m2")
    recalled = [e for e in events if e.payload.get("stage") == "memory"]
    assert len(recalled) == 1
    assert recalled[0].title == "Recalled 1 memory"
    assert recalled[0].payload["memories"] == [
        {
            "fact": "I picked pywebview for the HUD window",
            "note": "Projects/halo.md",
            "source": "you",
            "trust": "high",
        }
    ]


async def test_nothing_remembered_means_no_memory_section_and_no_event(
    memory_runner,
) -> None:
    async with memory_runner(reply(_intent("memory.recall", query="x"))) as (
        runner,
        events,
        transport,
    ):
        await runner.run("tell me something unrelated", run_id="m3")
    assert "What you know" not in _system(transport)
    assert not [e for e in events if e.payload.get("stage") == "memory"]


async def test_a_privacy_local_note_never_reaches_the_prompt_or_the_event(
    memory_runner, memory
) -> None:
    memory.remember("my salary is twelve lakh", note="Finance/pay.md")
    async with memory_runner(reply(_intent("memory.recall", query="salary"))) as (
        runner,
        events,
        transport,
    ):
        await runner.run("what is my salary?", run_id="m4")
    # Not in any prompt that was sent to the model...
    assert "twelve lakh" not in str(transport.calls)
    # ...and not in the event that lists what went into the prompt. (The recall
    # skill may still show the fact to the user on their own screen.)
    recalled = [e for e in events if e.payload.get("stage") == "memory"]
    assert recalled == []


async def test_remember_runs_end_to_end_and_writes_the_note(
    memory_runner, memory
) -> None:
    script = reply(_intent("memory.remember", fact="I picked pywebview for the HUD"))
    async with memory_runner(script) as (runner, events, _):
        outcome = await runner.run("remember that I picked pywebview", run_id="m5")
    assert outcome.state == "finished"
    assert outcome.result_status == "ok"
    assert memory.recall("pywebview")[0].source == "you"
    assert [e for e in events if e.type == "memory.saved"]


async def test_recall_runs_end_to_end_and_answers_with_a_link(
    memory_runner, memory
) -> None:
    memory.remember("I picked pywebview for the HUD window", note="Projects/halo.md")
    script = reply(_intent("memory.recall", query="what did I pick for the HUD window"))
    async with memory_runner(script) as (runner, _events, _):
        outcome = await runner.run("what did I pick for the HUD window?", run_id="m6")
    answer = outcome.results[0]["result"]["answer"]
    assert "pywebview" in answer
    assert "obsidian://open?vault=" in answer


async def test_forget_waits_for_approval_then_deletes(memory_runner, memory) -> None:
    memory.remember("I picked pywebview for the HUD window")
    script = reply(_intent("memory.forget", query="pywebview"))
    async with memory_runner(script) as (runner, events, _):
        paused = await runner.run("forget the pywebview thing", run_id="m7")
        assert paused.state == "paused"
        assert paused.approval is not None
        assert "pywebview" in paused.approval.detail
        assert memory.recall("pywebview")  # nothing deleted before the yes

        done = await runner.resume(
            "m7",
            ApprovalDecision(
                approval_id=paused.approval.approval_id, grant="allow_once"
            ),
        )
    assert done.state == "finished"
    assert memory.recall("pywebview") == []
    assert [e for e in events if e.type == "memory.forgotten"]


async def test_a_denied_forget_deletes_nothing(memory_runner, memory) -> None:
    memory.remember("I picked pywebview for the HUD window")
    script = reply(_intent("memory.forget", query="pywebview"))
    async with memory_runner(script) as (runner, _events, _):
        paused = await runner.run("forget the pywebview thing", run_id="m8")
        assert paused.approval is not None
        done = await runner.resume(
            "m8",
            ApprovalDecision(approval_id=paused.approval.approval_id, grant="deny"),
        )
    assert done.result_status == "denied"
    assert memory.recall("pywebview")
