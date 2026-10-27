"""Notes in an Obsidian vault <-> MemoryItems. Writing never disturbs the rest of a note."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from halo.memory.vault import (
    append_memory,
    delete_memory,
    ensure_vault,
    note_privacy,
    obsidian_link,
    parse_note,
)

NOW = datetime(2026, 10, 17, tzinfo=UTC)

NOTE = """---
privacy: shared
---
# Halo

Some prose that is not a memory.

- Picked pywebview for the HUD [src:: you] [trust:: high] [at:: 2026-10-10] ^m-4f2a
- Scraped hint from a web page [src:: web] [trust:: low] [at:: 2026-10-11] [exp:: 2026-12-01] ^m-9c01
- A plain bullet with no fields
"""


def _write(vault: Path, rel: str, text: str) -> Path:
    path = vault / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="")
    return path


def test_a_bullet_with_inline_fields_becomes_a_memory_item(tmp_path: Path) -> None:
    path = _write(tmp_path, "Projects/halo.md", NOTE)
    items = parse_note(path, tmp_path)
    first = items[0]
    assert first.fact == "Picked pywebview for the HUD"
    assert (first.source, first.trust) == ("you", "high")
    assert first.block_id == "^m-4f2a"
    assert first.created_at == datetime(2026, 10, 10, tzinfo=UTC)
    assert first.note_path == "Projects/halo.md"
    assert first.privacy == "shared"
    assert first.superseded is False


def test_expiry_and_low_trust_are_read(tmp_path: Path) -> None:
    items = parse_note(_write(tmp_path, "n.md", NOTE), tmp_path)
    web = next(i for i in items if i.source == "web")
    assert web.trust == "low"
    assert web.expires_at == datetime(2026, 12, 1, tzinfo=UTC)


def test_prose_and_plain_bullets_are_not_memories(tmp_path: Path) -> None:
    items = parse_note(_write(tmp_path, "n.md", NOTE), tmp_path)
    assert [i.block_id for i in items] == ["^m-4f2a", "^m-9c01"]


def test_a_note_marked_privacy_local_makes_local_items(tmp_path: Path) -> None:
    text = "---\nprivacy: local\n---\n- Salary is private [src:: you] [trust:: high] ^m-0001\n"
    path = _write(tmp_path, "Finance/pay.md", text)
    assert note_privacy(path) == "local"
    assert parse_note(path, tmp_path)[0].privacy == "local"


def test_a_note_without_frontmatter_is_shared(tmp_path: Path) -> None:
    path = _write(tmp_path, "n.md", "- fact [src:: you] ^m-0001\n")
    assert note_privacy(path) == "shared"


def test_a_bullet_without_a_block_id_still_gets_a_stable_one(tmp_path: Path) -> None:
    path = _write(tmp_path, "n.md", "- I like tea [src:: you] [trust:: high]\n")
    first = parse_note(path, tmp_path)[0].block_id
    assert first == parse_note(path, tmp_path)[0].block_id
    assert first.startswith("^")


def test_append_writes_one_line_and_leaves_the_rest_byte_for_byte(
    tmp_path: Path,
) -> None:
    path = _write(tmp_path, "Projects/halo.md", NOTE)
    item = append_memory(
        path, tmp_path, "Tests live in tests/", source="you", trust="high", now=NOW
    )
    after = path.read_text(encoding="utf-8")
    assert after.startswith(NOTE)
    added = after[len(NOTE) :]
    assert added.count("\n") == 1
    assert "Tests live in tests/ [src:: you] [trust:: high] [at:: 2026-10-17]" in added
    assert added.rstrip().endswith(item.block_id)
    assert item.privacy == "shared"
    assert parse_note(path, tmp_path)[-1].fact == "Tests live in tests/"


def test_append_to_a_note_without_a_trailing_newline(tmp_path: Path) -> None:
    path = _write(tmp_path, "n.md", "# T\n- a [src:: you] ^m-0001")
    append_memory(path, tmp_path, "b", source="you", trust="high", now=NOW)
    facts = [i.fact for i in parse_note(path, tmp_path)]
    assert facts == ["a", "b"]


def test_append_creates_a_missing_note_and_its_folder(tmp_path: Path) -> None:
    path = tmp_path / "Projects" / "new.md"
    append_memory(path, tmp_path, "hello", source="you", trust="high", now=NOW)
    assert parse_note(path, tmp_path)[0].fact == "hello"


def test_a_note_in_finance_is_created_as_privacy_local(tmp_path: Path) -> None:
    path = tmp_path / "Finance" / "budget.md"
    item = append_memory(
        path, tmp_path, "rent 20k", source="you", trust="high", now=NOW
    )
    assert item.privacy == "local"
    assert note_privacy(path) == "local"


def test_new_ids_are_unique_within_a_note(tmp_path: Path) -> None:
    path = tmp_path / "n.md"
    ids = {
        append_memory(
            path, tmp_path, f"f{i}", source="you", trust="high", now=NOW
        ).block_id
        for i in range(40)
    }
    assert len(ids) == 40


def test_delete_removes_only_that_line(tmp_path: Path) -> None:
    path = _write(tmp_path, "Projects/halo.md", NOTE)
    assert delete_memory(path, "^m-4f2a") is True
    after = path.read_text(encoding="utf-8")
    assert "pywebview" not in after
    assert after == NOTE.replace(
        "- Picked pywebview for the HUD [src:: you] [trust:: high] [at:: 2026-10-10] ^m-4f2a\n",
        "",
    )


def test_delete_of_an_unknown_id_changes_nothing(tmp_path: Path) -> None:
    path = _write(tmp_path, "n.md", NOTE)
    assert delete_memory(path, "^m-ffff") is False
    assert path.read_text(encoding="utf-8") == NOTE


def test_delete_finds_a_line_that_only_has_a_derived_id(tmp_path: Path) -> None:
    path = _write(
        tmp_path, "n.md", "- I like tea [src:: you]\n- keep me [src:: you] ^m-0001\n"
    )
    derived = parse_note(path, tmp_path)[0].block_id
    assert delete_memory(path, derived) is True
    assert [i.fact for i in parse_note(path, tmp_path)] == ["keep me"]


def test_windows_line_endings_survive_an_append_and_a_delete(tmp_path: Path) -> None:
    text = "# T\r\n- a [src:: you] ^m-0001\r\n- b [src:: you] ^m-0002\r\n"
    path = _write(tmp_path, "n.md", text)
    append_memory(path, tmp_path, "c", source="you", trust="high", now=NOW)
    delete_memory(path, "^m-0001")
    after = path.read_bytes().decode("utf-8")
    assert "\n" not in after.replace("\r\n", "")
    assert [i.fact for i in parse_note(path, tmp_path)] == ["b", "c"]


def test_an_obsidian_link_names_the_vault_and_the_note(tmp_path: Path) -> None:
    vault = tmp_path / "HaloVault"
    link = obsidian_link(vault, "Projects/halo.md")
    assert link == "obsidian://open?vault=HaloVault&file=Projects%2Fhalo"


@pytest.mark.parametrize(
    "bad",
    [
        "../escape.md",
        "/abs.md",
        "C:/x.md",
        ".obsidian/plugins/x.md",
        "Projects/.hidden/x.md",
        ".git/config.md",
    ],
)
def test_a_note_path_can_not_leave_the_vault(tmp_path: Path, bad: str) -> None:
    from halo.memory.vault import VaultPathError, resolve_note

    with pytest.raises(VaultPathError):
        resolve_note(tmp_path, bad)


def test_the_template_is_copied_once_and_never_overwritten(tmp_path: Path) -> None:
    vault = tmp_path / "HaloVault"
    assert ensure_vault(vault) is True
    assert (vault / "Profile.md").is_file()
    assert (vault / "Inbox" / "proposed-memories.md").is_file()
    for folder in ("Projects", "Finance", "Trips", "People", "Journal", "Skills"):
        assert (vault / folder).is_dir()
    (vault / "Profile.md").write_text("mine", encoding="utf-8")
    assert ensure_vault(vault) is False
    assert (vault / "Profile.md").read_text(encoding="utf-8") == "mine"
    assert note_privacy(next((vault / "Finance").glob("*.md"))) == "local"


def test_the_starter_vault_holds_no_pre_written_memories(tmp_path: Path) -> None:
    """The template must not assert facts about the user that they never said."""
    vault = tmp_path / "HaloVault"
    ensure_vault(vault)
    found = [item for note in vault.rglob("*.md") for item in parse_note(note, vault)]
    assert found == []
