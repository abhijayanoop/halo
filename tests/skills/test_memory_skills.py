"""memory.remember, memory.recall and memory.forget."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from halo.core.context import HaloContext
from halo.memory.store import MemoryStore
from halo.skills.errors import SkillArgsError
from halo.skills.registry import SkillRegistry, default_skills_dir

NOW = datetime(2026, 10, 17, tzinfo=UTC)


@pytest.fixture
def registry() -> SkillRegistry:
    return SkillRegistry.load(default_skills_dir())


@pytest.fixture
def store(tmp_path: Path):
    s = MemoryStore(tmp_path / "vault", tmp_path / "memory.db", clock=lambda: NOW)
    s.start()
    yield s
    s.close()


@pytest.fixture
def events() -> list:
    return []


def _ctx(store, events, *, approved=False, memory=True) -> HaloContext:
    return HaloContext(
        "run-m",
        events.append,
        None,  # type: ignore[arg-type]  # these skills never call a model
        approved=approved,
        memory=store if memory else None,
    )


# --- the policy decision for each skill ----------------------------------------------


def test_remember_and_recall_are_low_risk_and_forget_asks(registry) -> None:
    assert registry.get("memory.remember").manifest.risk == "low"
    assert registry.get("memory.recall").manifest.risk == "low"
    assert registry.get("memory.forget").manifest.risk == "medium"


def test_forget_can_never_be_an_always_grant(registry) -> None:
    module = registry.get("memory.forget").module
    assert module.grantable({"query": "tea"}) is False


def test_the_forget_card_says_what_will_be_deleted(registry) -> None:
    module = registry.get("memory.forget").module
    assert "pywebview" in module.describe({"query": "pywebview"})
    with pytest.raises(ValueError):
        module.describe({"query": "  "})


# --- remember --------------------------------------------------------------------------


async def test_remember_saves_a_line_from_you_and_says_so(
    registry, store, events
) -> None:
    run = registry.get("memory.remember").module.run
    result = await run(_ctx(store, events), {"fact": "I picked pywebview for the HUD"})
    assert result["saved"] is True
    assert result["note"] == "Profile.md"
    assert store.recall("pywebview")[0].source == "you"
    saved = [e for e in events if e.type == "memory.saved"]
    assert len(saved) == 1
    assert saved[0].payload["fact"] == "I picked pywebview for the HUD"
    assert saved[0].payload["source"] == "you"


@pytest.mark.parametrize("args", [{}, {"fact": ""}, {"fact": "  "}, {"fact": 5}])
async def test_remember_rejects_a_missing_or_blank_fact(
    registry, store, events, args
) -> None:
    run = registry.get("memory.remember").module.run
    with pytest.raises(SkillArgsError):
        await run(_ctx(store, events), args)
    assert events == []


async def test_remember_refuses_a_note_outside_the_vault(
    registry, store, events
) -> None:
    run = registry.get("memory.remember").module.run
    with pytest.raises(SkillArgsError):
        await run(_ctx(store, events), {"fact": "x", "note": "../outside.md"})


async def test_remember_into_a_project_note(registry, store, events) -> None:
    run = registry.get("memory.remember").module.run
    result = await run(
        _ctx(store, events),
        {"fact": "tests live in tests/", "note": "Projects/halo.md"},
    )
    assert result["note"] == "Projects/halo.md"


async def test_without_a_memory_store_the_skill_says_so(
    registry, store, events
) -> None:
    run = registry.get("memory.remember").module.run
    result = await run(_ctx(store, events, memory=False), {"fact": "x"})
    assert "error" in result


# --- recall ----------------------------------------------------------------------------


async def test_recall_answers_from_memory_with_a_link_to_the_note(
    registry, store, events
) -> None:
    store.remember("I picked pywebview for the HUD window", note="Projects/halo.md")
    run = registry.get("memory.recall").module.run
    result = await run(
        _ctx(store, events), {"query": "what did I pick for the HUD window?"}
    )
    assert "pywebview" in result["answer"]
    assert result["sources"][0]["note"] == "Projects/halo.md"
    assert result["sources"][0]["link"].startswith("obsidian://open?vault=")
    assert "obsidian://" in result["answer"]


async def test_recall_says_it_does_not_know_when_nothing_matches(
    registry, store, events
) -> None:
    run = registry.get("memory.recall").module.run
    result = await run(_ctx(store, events), {"query": "my passport number"})
    assert result["sources"] == []
    assert "don't know" in result["answer"].lower()


async def test_recall_after_the_line_is_deleted_does_not_know(
    registry, store, events
) -> None:
    store.remember("I picked pywebview for the HUD window")
    path = store.vault / "Profile.md"
    path.write_text("# Profile\n", encoding="utf-8")
    store.reindex_note(path)
    run = registry.get("memory.recall").module.run
    result = await run(_ctx(store, events), {"query": "what did I pick for the HUD"})
    assert "don't know" in result["answer"].lower()


async def test_recall_rejects_a_blank_query(registry, store, events) -> None:
    run = registry.get("memory.recall").module.run
    with pytest.raises(SkillArgsError):
        await run(_ctx(store, events), {"query": " "})


async def test_recall_marks_low_trust_facts_as_hints(registry, store, events) -> None:
    store.remember("the site says it opens at nine", source="web", trust="low")
    run = registry.get("memory.recall").module.run
    result = await run(_ctx(store, events), {"query": "when does the site open"})
    assert "hint" in result["answer"].lower()


# --- forget ----------------------------------------------------------------------------


async def test_forget_does_nothing_until_the_executor_has_approved_it(
    registry, store, events
) -> None:
    store.remember("I picked pywebview for the HUD window")
    run = registry.get("memory.forget").module.run
    result = await run(_ctx(store, events, approved=False), {"query": "pywebview"})
    assert result["needs_approval"] is True
    assert store.recall("pywebview")
    assert events == []


async def test_forget_deletes_the_lines_and_tells_the_hud(
    registry, store, events
) -> None:
    store.remember("I picked pywebview for the HUD window")
    store.remember("I like green tea")
    run = registry.get("memory.forget").module.run
    result = await run(_ctx(store, events, approved=True), {"query": "pywebview"})
    assert [f["fact"] for f in result["forgotten"]] == [
        "I picked pywebview for the HUD window"
    ]
    assert store.recall("pywebview") == []
    assert store.recall("green tea")
    gone = [e for e in events if e.type == "memory.forgotten"]
    assert len(gone) == 1
    assert gone[0].payload["fact"] == "I picked pywebview for the HUD window"


async def test_forget_with_no_match_says_so_and_deletes_nothing(
    registry, store, events
) -> None:
    store.remember("I like green tea")
    run = registry.get("memory.forget").module.run
    result = await run(_ctx(store, events, approved=True), {"query": "quantum"})
    assert result["forgotten"] == []
    assert store.recall("green tea")
    assert not [e for e in events if e.type == "memory.forgotten"]


async def test_forget_rejects_a_blank_query(registry, store, events) -> None:
    run = registry.get("memory.forget").module.run
    with pytest.raises(SkillArgsError):
        await run(_ctx(store, events, approved=True), {"query": ""})
