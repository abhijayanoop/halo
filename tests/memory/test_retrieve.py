"""Ranking and the context budget: what actually goes into a prompt, and why."""

from datetime import UTC, datetime, timedelta
from typing import Literal

from halo.core.contracts import MemoryItem, MemorySource, TrustLevel
from halo.memory.retrieve import assemble_context, retrieve, rrf, rrf_scores

NOW = datetime(2026, 10, 17, tzinfo=UTC)


def _item(
    fact: str,
    *,
    n: int = 1,
    trust: TrustLevel = "high",
    source: MemorySource = "you",
    privacy: Literal["shared", "local"] = "shared",
    note_path="Profile.md",
    **extra,
) -> MemoryItem:
    return MemoryItem(
        fact=fact,
        source=source,
        trust=trust,
        created_at=NOW - timedelta(days=3),
        block_id=f"^m-{n:04x}",
        note_path=note_path,
        privacy=privacy,
        **extra,
    )


class FakeIndex:
    """Stands in for the SQLite index: returns items in a fixed ranking."""

    def __init__(self, *items: MemoryItem) -> None:
        self._items = list(items)

    def search(self, query: str, limit: int = 20) -> list[MemoryItem]:
        return self._items[:limit]


# --- reciprocal rank fusion ---------------------------------------------------


def test_rrf_puts_an_item_found_by_both_searches_first() -> None:
    assert rrf(["a", "b", "c"], ["c", "d"])[0] == "c"


def test_rrf_needs_no_comparable_scores_only_ranks() -> None:
    assert rrf(["a", "b"]) == ["a", "b"]


def test_rrf_with_nothing_returns_nothing() -> None:
    assert rrf() == []
    assert rrf([], []) == []


def test_rrf_scores_each_list_as_one_over_sixty_plus_rank() -> None:
    scores = rrf_scores(["a", "b"], ["b"])
    assert scores["a"] == 1 / 61
    assert scores["b"] == 1 / 62 + 1 / 61


# --- retrieve ------------------------------------------------------------------


def test_expired_item_is_never_returned() -> None:
    old = _item("expired hint", n=1, expires_at=NOW - timedelta(days=1))
    live = _item("live fact", n=2, expires_at=NOW + timedelta(days=1))
    got = retrieve(FakeIndex(old, live), "q", now=NOW)
    assert [i.fact for i in got] == ["live fact"]


def test_a_superseded_item_is_never_returned() -> None:
    got = retrieve(
        FakeIndex(_item("old", superseded=True), _item("new", n=2)), "q", now=NOW
    )
    assert [i.fact for i in got] == ["new"]


def test_high_trust_is_boosted_above_low_trust_at_a_similar_rank() -> None:
    low = _item("low trust claim", n=1, trust="low", source="web")
    high = _item("high trust claim", n=2, trust="high")
    got = retrieve(FakeIndex(low, high), "q", now=NOW)
    assert got[0].fact == "high trust claim"


def test_a_much_better_match_still_beats_the_trust_boost() -> None:
    filler = [_item(f"filler {i}", n=i + 10, trust="high") for i in range(8)]
    best_low = _item("exact match", n=1, trust="low", source="web")
    got = retrieve(FakeIndex(best_low, *filler), "q", now=NOW)
    # Ranked first by the search, boosted down by trust, but not buried at the bottom.
    assert [i.fact for i in got].index("exact match") < 4


def test_retrieve_takes_at_most_the_limit() -> None:
    items = [_item(f"f{i}", n=i) for i in range(30)]
    assert len(retrieve(FakeIndex(*items), "q", now=NOW, limit=20)) == 20


# --- the context budget and the privacy filter -----------------------------------


def test_context_names_where_each_fact_came_from() -> None:
    ctx = assemble_context(
        [_item("Picked pywebview", note_path="Projects/halo.md", source="you")]
    )
    assert "Picked pywebview" in ctx.text
    assert "Projects/halo.md" in ctx.text
    assert "you" in ctx.text


def test_context_stays_within_the_token_budget_and_keeps_the_best_first() -> None:
    items = [_item("word " * 50 + str(i), n=i) for i in range(40)]
    ctx = assemble_context(items, budget=300)
    assert ctx.tokens <= 300
    assert ctx.used[0] is items[0]
    assert len(ctx.used) < len(items)
    assert ctx.dropped == len(items) - len(ctx.used)


def test_nothing_to_say_gives_an_empty_context() -> None:
    ctx = assemble_context([])
    assert ctx.text == ""
    assert ctx.used == []


def test_a_privacy_local_item_never_goes_into_the_context() -> None:
    secret = _item("salary is 12 lakh", privacy="local", note_path="Finance/pay.md")
    open_ = _item("likes tea", n=2)
    ctx = assemble_context([secret, open_])
    assert "salary" not in ctx.text
    assert "Finance" not in ctx.text
    assert [i.fact for i in ctx.used] == ["likes tea"]


def test_low_trust_facts_are_marked_as_hints_that_cannot_trigger_actions() -> None:
    ctx = assemble_context([_item("a web claim", trust="low", source="web")])
    assert "hint" in ctx.text.lower()
    assert "never" in ctx.text.lower()


def test_a_fact_that_alone_exceeds_the_budget_is_skipped_not_truncated() -> None:
    huge = _item("x " * 5000)
    small = _item("tiny", n=2)
    ctx = assemble_context([huge, small], budget=100)
    assert [i.fact for i in ctx.used] == ["tiny"]
