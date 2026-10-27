"""The memory store: what skills and the app use to remember, recall and forget."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from halo.core.contracts import MemoryCandidate
from halo.memory.store import MemoryStore
from halo.memory.vault import VaultPathError

NOW = datetime(2026, 10, 17, tzinfo=UTC)


@pytest.fixture
def store(tmp_path: Path):
    s = MemoryStore(tmp_path / "vault", tmp_path / "memory.db", clock=lambda: NOW)
    s.start()
    yield s
    s.close()


def _reopen(tmp_path: Path) -> MemoryStore:
    s = MemoryStore(tmp_path / "vault", tmp_path / "memory.db", clock=lambda: NOW)
    s.start()
    return s


def test_starting_creates_the_vault_from_the_template(store: MemoryStore) -> None:
    assert (store.vault / "Profile.md").is_file()
    assert (store.vault / "Inbox" / "proposed-memories.md").is_file()


def test_remember_writes_a_line_you_can_read_in_obsidian(store: MemoryStore) -> None:
    item = store.remember("I picked pywebview for the HUD window")
    text = (store.vault / "Profile.md").read_text(encoding="utf-8")
    assert "I picked pywebview for the HUD window [src:: you] [trust:: high]" in text
    assert item.source == "you"
    assert item.note_path == "Profile.md"


def test_remember_into_a_named_note(store: MemoryStore) -> None:
    item = store.remember("tests live in tests/", note="Projects/halo.md")
    assert item.note_path == "Projects/halo.md"
    assert (store.vault / "Projects" / "halo.md").is_file()


@pytest.mark.parametrize("bad", ["../outside.md", "/etc/passwd", "C:/x.md"])
def test_remember_can_not_write_outside_the_vault(store: MemoryStore, bad: str) -> None:
    with pytest.raises(VaultPathError):
        store.remember("nope", note=bad)


def test_a_remembered_fact_is_recalled_with_its_note(store: MemoryStore) -> None:
    store.remember("I picked pywebview for the HUD window")
    found = store.recall("what did I pick for the HUD window?")
    assert [i.fact for i in found] == ["I picked pywebview for the HUD window"]
    assert store.link(found[0]).startswith("obsidian://open?vault=")


def test_memory_survives_a_restart(store: MemoryStore, tmp_path: Path) -> None:
    store.remember("I picked pywebview for the HUD window")
    store.close()
    again = _reopen(tmp_path)
    try:
        assert again.recall("HUD window")
    finally:
        again.close()


def test_deleting_the_line_in_obsidian_makes_halo_forget(
    store: MemoryStore,
) -> None:
    store.remember("I picked pywebview for the HUD window")
    path = store.vault / "Profile.md"
    path.write_text(
        "\n".join(
            line
            for line in path.read_text(encoding="utf-8").splitlines()
            if "pywebview" not in line
        )
        + "\n",
        encoding="utf-8",
    )
    store.reindex_note(path)
    assert store.recall("what did I pick for the HUD window?") == []


def test_forget_deletes_the_matching_line_and_leaves_the_others(
    store: MemoryStore,
) -> None:
    store.remember("I picked pywebview for the HUD window")
    store.remember("I like green tea")
    gone = store.forget("pywebview HUD")
    assert [i.fact for i in gone] == ["I picked pywebview for the HUD window"]
    assert store.recall("pywebview") == []
    assert store.recall("green tea")


def test_forget_needs_every_word_to_match_so_it_never_over_deletes(
    store: MemoryStore,
) -> None:
    store.remember("I like green tea")
    store.remember("I like black coffee")
    assert store.forget("tea coffee") == []
    assert len(store.recall("like")) == 2


def test_forget_deletes_at_most_a_few_lines(store: MemoryStore) -> None:
    for n in range(6):
        store.remember(f"project note number {n}")
    assert len(store.forget("project note", max_items=3)) == 3
    assert len(store.recall("project note")) == 3


def test_forget_with_no_match_changes_nothing(store: MemoryStore) -> None:
    store.remember("I like green tea")
    assert store.forget("quantum physics") == []
    assert store.recall("green tea")


def test_the_context_for_a_cloud_prompt_never_holds_local_notes(
    store: MemoryStore,
) -> None:
    store.remember("my salary is twelve lakh", note="Finance/pay.md")
    store.remember("I like green tea")
    ctx = store.context("salary and tea")
    assert "salary" not in ctx.text
    assert "green tea" in ctx.text


def test_recalling_for_the_user_may_show_a_local_fact_on_screen(
    store: MemoryStore,
) -> None:
    store.remember("my salary is twelve lakh", note="Finance/pay.md")
    assert [i.fact for i in store.recall("salary")] == ["my salary is twelve lakh"]


def test_local_texts_are_the_full_text_of_privacy_local_notes_only(
    store: MemoryStore,
) -> None:
    store.remember("my salary is twelve lakh", note="Finance/pay.md")
    store.remember("I like green tea")
    texts = store.local_texts()
    assert any("salary is twelve lakh" in t for t in texts)
    assert not any("green tea" in t for t in texts)


# --- proposed memories ------------------------------------------------------------


def _candidate(fact="Prefers pytest over unittest", subject="halo") -> MemoryCandidate:
    return MemoryCandidate(fact=fact, subject=subject, source="agent", trust="medium")


def _proposed(store: MemoryStore, candidate: MemoryCandidate) -> str:
    pid = store.propose(candidate)
    assert pid
    return pid


def test_a_proposal_is_listed_but_is_not_a_memory_yet(store: MemoryStore) -> None:
    pid = _proposed(store, _candidate())
    assert pid
    assert [p.candidate.fact for p in store.proposals()] == [
        "Prefers pytest over unittest"
    ]
    assert store.recall("pytest") == []


def test_approving_writes_it_to_the_note_named_by_its_subject(
    store: MemoryStore,
) -> None:
    store.remember("starter", note="Projects/halo.md")
    pid = _proposed(store, _candidate())
    item = store.approve(pid)
    assert item.note_path == "Projects/halo.md"
    assert item.source == "agent"
    assert item.trust == "medium"
    assert store.proposals() == []
    assert store.recall("pytest")


def test_approving_with_an_unknown_subject_falls_back_to_the_profile(
    store: MemoryStore,
) -> None:
    pid = _proposed(store, _candidate(subject="nonexistent-thing"))
    assert store.approve(pid).note_path == "Profile.md"


def test_approving_into_a_chosen_note(store: MemoryStore) -> None:
    pid = _proposed(store, _candidate())
    assert store.approve(pid, note="People/sam.md").note_path == "People/sam.md"


def test_rejecting_discards_the_proposal(store: MemoryStore) -> None:
    pid = _proposed(store, _candidate())
    assert store.reject(pid) is True
    assert store.proposals() == []
    assert store.recall("pytest") == []
    assert store.reject(pid) is False


def test_approving_an_unknown_proposal_is_an_error(store: MemoryStore) -> None:
    with pytest.raises(KeyError):
        store.approve("^p-nope")


def test_a_fact_already_remembered_or_proposed_is_not_proposed_again(
    store: MemoryStore,
) -> None:
    store.remember("Prefers pytest over unittest")
    assert store.propose(_candidate()) is None
    pid = _proposed(store, _candidate("Uses ruff for linting"))
    assert pid
    assert store.propose(_candidate("Uses ruff for linting")) is None


def test_a_proposal_survives_a_restart(store: MemoryStore, tmp_path: Path) -> None:
    store.propose(_candidate())
    store.close()
    again = _reopen(tmp_path)
    try:
        assert len(again.proposals()) == 1
    finally:
        again.close()
