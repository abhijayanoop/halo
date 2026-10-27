"""The SQLite index: keyword search over the memories in a vault, kept in step with the notes."""

from pathlib import Path

import pytest

from halo.memory.index import MemoryIndex


def _note(vault: Path, rel: str, *bullets: str, privacy: str = "shared") -> Path:
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    body = "\n".join(bullets)
    path.write_text(f"---\nprivacy: {privacy}\n---\n{body}\n", encoding="utf-8")
    return path


def _bullet(fact: str, n: int, **extra: str) -> str:
    fields = " ".join(
        f"[{k}:: {v}]" for k, v in {"src": "you", "trust": "high", **extra}.items()
    )
    return f"- {fact} {fields} ^m-{n:04x}"


@pytest.fixture
def vault(tmp_path: Path) -> Path:
    root = tmp_path / "vault"
    root.mkdir()
    return root


@pytest.fixture
def index(tmp_path: Path, vault: Path):
    idx = MemoryIndex(tmp_path / "memory.db", vault)
    yield idx
    idx.close()


def test_a_fact_is_found_by_a_word_in_it(index: MemoryIndex, vault: Path) -> None:
    index.reindex_note(
        _note(
            vault, "Projects/halo.md", _bullet("Picked pywebview for the HUD window", 1)
        )
    )
    found = index.search("what did I pick for the HUD window")
    assert [i.fact for i in found] == ["Picked pywebview for the HUD window"]


def test_search_matches_word_forms(index: MemoryIndex, vault: Path) -> None:
    index.reindex_note(_note(vault, "a.md", _bullet("Picked pywebview", 1)))
    assert index.search("picking")


def test_an_unrelated_query_finds_nothing(index: MemoryIndex, vault: Path) -> None:
    index.reindex_note(_note(vault, "a.md", _bullet("Picked pywebview", 1)))
    assert index.search("quarterly tax filing") == []
    assert index.search("") == []
    assert index.search("the of a") == []


@pytest.mark.parametrize(
    "query", ['"unterminated', "AND OR NOT", "foo*", "a-b", "(x", "NEAR(", "col:val"]
)
def test_odd_characters_in_a_query_never_raise(
    index: MemoryIndex, vault: Path, query: str
) -> None:
    index.reindex_note(_note(vault, "a.md", _bullet("Picked pywebview", 1)))
    index.search(query)


def test_editing_a_note_replaces_its_rows(index: MemoryIndex, vault: Path) -> None:
    path = _note(vault, "a.md", _bullet("old fact about tea", 1))
    index.reindex_note(path)
    _note(vault, "a.md", _bullet("new fact about coffee", 2))
    index.reindex_note(path)
    assert index.search("tea") == []
    assert [i.fact for i in index.search("coffee")] == ["new fact about coffee"]


def test_a_line_deleted_in_obsidian_is_forgotten(
    index: MemoryIndex, vault: Path
) -> None:
    path = _note(
        vault, "a.md", _bullet("fact one tea", 1), _bullet("fact two coffee", 2)
    )
    index.reindex_note(path)
    _note(vault, "a.md", _bullet("fact two coffee", 2))
    index.reindex_note(path)
    assert index.search("tea") == []
    assert index.search("coffee")


def test_remove_note_forgets_everything_in_it(index: MemoryIndex, vault: Path) -> None:
    path = _note(vault, "a.md", _bullet("fact about tea", 1))
    index.reindex_note(path)
    index.remove_note("a.md")
    assert index.search("tea") == []
    assert index.items() == []


def test_reindex_all_picks_up_new_notes_and_drops_deleted_ones(
    index: MemoryIndex, vault: Path
) -> None:
    gone = _note(vault, "gone.md", _bullet("about tea", 1))
    index.reindex_all()
    gone.unlink()
    _note(vault, "Projects/new.md", _bullet("about coffee", 2))
    index.reindex_all()
    assert [i.fact for i in index.items()] == ["about coffee"]


def test_only_markdown_outside_obsidian_and_the_inbox_is_indexed(
    index: MemoryIndex, vault: Path
) -> None:
    _note(vault, ".obsidian/plugins/x.md", _bullet("hidden config", 1))
    _note(vault, "Inbox/proposed-memories.md", _bullet("only a proposal", 2))
    (vault / "pic.png").write_bytes(b"x")
    _note(vault, "real.md", _bullet("real fact", 3))
    index.reindex_all()
    assert [i.fact for i in index.items()] == ["real fact"]


def test_items_carry_privacy_and_trust_from_the_note(
    index: MemoryIndex, vault: Path
) -> None:
    index.reindex_note(
        _note(vault, "Finance/pay.md", _bullet("salary is private", 1), privacy="local")
    )
    item = index.search("salary")[0]
    assert item.privacy == "local"
    assert item.trust == "high"


def test_the_index_survives_a_restart(tmp_path: Path, vault: Path) -> None:
    db = tmp_path / "persist.db"
    first = MemoryIndex(db, vault)
    first.reindex_note(_note(vault, "a.md", _bullet("tea time", 1)))
    first.close()
    second = MemoryIndex(db, vault)
    try:
        assert second.search("tea")
    finally:
        second.close()


def test_the_best_match_comes_first(index: MemoryIndex, vault: Path) -> None:
    index.reindex_note(
        _note(
            vault,
            "a.md",
            _bullet("coffee", 1),
            _bullet("coffee beans grinder coffee machine", 2),
            _bullet("tea", 3),
        )
    )
    found = index.search("coffee grinder machine")
    assert found[0].fact == "coffee beans grinder coffee machine"


def test_a_fact_that_matches_only_one_of_several_words_is_not_an_answer(
    index: MemoryIndex, vault: Path
) -> None:
    """Matching a single stray word ("Windows" vs "window") must not count as relevant."""
    index.reindex_note(
        _note(
            vault,
            "a.md",
            _bullet("Picked pywebview for the HUD window", 1),
            _bullet("I work on Windows 11 and use Git Bash", 2),
        )
    )
    found = index.search("what did I pick for the HUD window")
    assert [i.fact for i in found] == ["Picked pywebview for the HUD window"]


def test_when_the_only_matching_line_is_gone_nothing_is_found(
    index: MemoryIndex, vault: Path
) -> None:
    path = _note(vault, "a.md", _bullet("I work on Windows 11 and use Git Bash", 2))
    index.reindex_note(path)
    assert index.search("what did I pick for the HUD window") == []


def test_a_two_word_question_needs_at_least_one_of_them(
    index: MemoryIndex, vault: Path
) -> None:
    index.reindex_note(_note(vault, "a.md", _bullet("I use Python for my work", 1)))
    assert index.search("what do I use for work")


def test_half_of_the_meaningful_words_is_enough_but_fewer_is_not(
    index: MemoryIndex, vault: Path
) -> None:
    index.reindex_note(
        _note(
            vault,
            "a.md",
            _bullet("alpha beta", 1),
            _bullet("alpha only", 2),
        )
    )
    # four words, so two must match: the first fact has two, the second has one
    found = index.search("alpha beta gamma delta")
    assert [i.fact for i in found] == ["alpha beta"]
