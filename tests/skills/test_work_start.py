import json
import time
from datetime import date
from pathlib import Path

import pytest
from conftest import FakeContext, FakeTransport

from halo.core.context import HaloContext
from halo.memory.store import MemoryStore
from halo.skills.registry import SkillRegistry, default_skills_dir


@pytest.fixture(scope="module")
def skill():
    return SkillRegistry.load(default_skills_dir()).get("work.start")


@pytest.fixture
def memory(tmp_path: Path):
    store = MemoryStore(tmp_path / "vault", tmp_path / "memory.db")
    store.start()
    yield store
    store.close()


def _ctx(make_client, memory) -> tuple[HaloContext, FakeTransport]:
    client, transport, _ = make_client()
    return HaloContext("run1", lambda e: None, client, memory=memory), transport


def _project(vault: Path, name: str, last_stop: str, body: str = "# P\n") -> None:
    path = vault / "Projects" / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        f'---\nprivacy: shared\npath: C:/x\ntest_cmd: pytest\nlast_stop: "{last_stop}"\n---\n{body}',
        encoding="utf-8",
    )


def test_the_skill_is_registered_low_risk(skill) -> None:
    assert skill.manifest.name == "work.start"
    assert skill.manifest.risk == "low"


async def test_it_needs_a_halo_context(skill) -> None:
    with pytest.raises(TypeError):
        await skill.module.run(FakeContext(), {})


async def test_without_memory_it_says_so(skill, make_client) -> None:
    client, _, _ = make_client()
    out = await skill.module.run(HaloContext("r", lambda e: None, client), {})
    assert "error" in out and out["proposals"] == []


async def test_it_says_where_you_stopped_and_proposes_what_to_pick_up(
    skill, make_client, memory
) -> None:
    _project(
        memory.vault,
        "halo",
        "2026-10-27: kept: Add rate limiting",
        "- [ ] Write docs\n",
    )
    ctx, _ = _ctx(make_client, memory)
    out = await skill.module.run(ctx, {})
    assert out["answer"].startswith("You stopped at: Add rate limiting")
    assert "1." in out["answer"] and "Write docs" in out["answer"]
    assert out["proposals"][0]["project"] == "halo"
    assert out["proposals"][0]["request"]
    assert out["stopped_at"].startswith("Add rate limiting")


async def test_todays_journal_is_read(skill, make_client, memory) -> None:
    today = date.today().isoformat()
    journal = memory.vault / "Journal" / f"{today}.md"
    journal.parent.mkdir(parents=True, exist_ok=True)
    journal.write_text("- [ ] Review the PRs\n", encoding="utf-8")
    ctx, _ = _ctx(make_client, memory)
    out = await skill.module.run(ctx, {})
    assert "Review the PRs" in out["answer"]


async def test_with_nothing_open_it_says_so_and_suggests_a_task(
    skill, make_client, memory
) -> None:
    ctx, _ = _ctx(make_client, memory)
    out = await skill.module.run(ctx, {})
    assert out["proposals"] == []
    assert "nothing" in out["answer"].lower() or "don't see" in out["answer"].lower()


async def test_it_never_calls_a_model_even_with_local_notes(
    skill, make_client, memory
) -> None:
    _project(memory.vault, "halo", "2026-10-27: kept: Add rate limiting")
    secret = memory.vault / "Finance" / "Budget.md"
    secret.parent.mkdir(parents=True, exist_ok=True)
    secret.write_text(
        "---\nprivacy: local\n---\n- [ ] Pay the tax bill of 12345\n", encoding="utf-8"
    )
    ctx, transport = _ctx(make_client, memory)
    out = await skill.module.run(ctx, {})
    assert transport.calls == []
    assert "12345" not in json.dumps(out)  # Finance is not a work source


async def test_it_answers_well_inside_the_time_the_spec_allows(
    skill, make_client, memory
) -> None:
    for i in range(30):
        _project(
            memory.vault,
            f"p{i}",
            f"2026-10-{(i % 27) + 1:02d}: merged: thing {i}",
            "- [ ] a\n- [ ] b\n",
        )
    ctx, _ = _ctx(make_client, memory)
    started = time.perf_counter()
    await skill.module.run(ctx, {})
    assert time.perf_counter() - started < 1.5
