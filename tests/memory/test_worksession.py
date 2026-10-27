from datetime import date
from pathlib import Path

from halo.memory.worksession import plan_work

TODAY = date(2026, 10, 27)


def note(
    vault: Path, folder: str, name: str, body: str, *, front: str = "privacy: shared"
) -> Path:
    path = vault / folder / f"{name}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\n{front}\n---\n{body}", encoding="utf-8")
    return path


def project(vault: Path, name: str, last_stop: str = "", body: str = "# P\n") -> Path:
    front = f'privacy: shared\npath: C:/x/{name}\ntest_cmd: pytest\nlast_stop: "{last_stop}"'
    return note(vault, "Projects", name, body, front=front)


def test_an_empty_vault_has_nothing_to_propose(tmp_path: Path) -> None:
    plan = plan_work(tmp_path, TODAY)
    assert plan.stopped_at == "" and plan.proposals == []


def test_stopped_at_comes_from_the_most_recent_last_stop(tmp_path: Path) -> None:
    project(tmp_path, "old", "2026-10-20: merged: Old thing")
    project(tmp_path, "halo", "2026-10-27: merged: Add a hello file")
    project(tmp_path, "blank", "")
    plan = plan_work(tmp_path, TODAY)
    assert plan.project == "halo"
    assert "Add a hello file" in plan.stopped_at
    assert "2026-10-27" in plan.stopped_at


def test_unfinished_work_is_proposed_first_and_finished_work_is_not(
    tmp_path: Path,
) -> None:
    project(tmp_path, "halo", "2026-10-27: kept: Add rate limiting")
    plan = plan_work(tmp_path, TODAY)
    assert plan.proposals[0].source == "last_stop"
    assert "Add rate limiting" in plan.proposals[0].title
    assert plan.proposals[0].project == "halo"

    for outcome in ("merged", "discarded", "denied"):
        project(tmp_path, "halo", f"2026-10-27: {outcome}: Add rate limiting")
        assert plan_work(tmp_path, TODAY).proposals == []


def test_a_failed_session_counts_as_unfinished(tmp_path: Path) -> None:
    project(tmp_path, "halo", "2026-10-27: failed: Fix the flaky test")
    assert plan_work(tmp_path, TODAY).proposals[0].source == "last_stop"


def test_todays_journal_checkboxes_come_next_and_other_days_are_ignored(
    tmp_path: Path,
) -> None:
    project(tmp_path, "halo", "2026-10-27: kept: Add rate limiting")
    note(
        tmp_path,
        "Journal",
        "2026-10-27",
        "- [ ] Write the Day 4 notes\n- [x] Done thing\n",
    )
    note(tmp_path, "Journal", "2026-10-26", "- [ ] Yesterday's thing\n")
    plan = plan_work(tmp_path, TODAY)
    titles = [p.title for p in plan.proposals]
    assert titles[1] == "Write the Day 4 notes"
    assert "Done thing" not in titles and "Yesterday's thing" not in titles
    assert plan.proposals[1].source == "journal" and plan.proposals[1].project is None


def test_open_checkboxes_in_project_notes_fill_the_rest_up_to_three(
    tmp_path: Path,
) -> None:
    project(
        tmp_path,
        "halo",
        "2026-10-27: merged: x",
        body="# H\n- [ ] one\n- [ ] two\n- [ ] three\n- [ ] four\n",
    )
    plan = plan_work(tmp_path, TODAY)
    assert [p.title for p in plan.proposals] == ["one", "two", "three"]
    assert all(p.source == "project" and p.project == "halo" for p in plan.proposals)
    assert plan.proposals[0].request == "one in halo"


def test_duplicates_are_listed_once(tmp_path: Path) -> None:
    project(tmp_path, "halo", "", body="- [ ] Write tests\n")
    note(tmp_path, "Journal", "2026-10-27", "- [ ] write tests\n")
    assert len(plan_work(tmp_path, TODAY).proposals) == 1


def test_titles_are_cleaned_of_ids_and_inline_fields_and_capped(tmp_path: Path) -> None:
    note(
        tmp_path,
        "Journal",
        "2026-10-27",
        "- [ ] Call the bank [due:: 2026-11-01] ^t-12ab\n- [ ] " + "x" * 400 + "\n",
    )
    titles = [p.title for p in plan_work(tmp_path, TODAY).proposals]
    assert titles[0] == "Call the bank"
    assert len(titles[1]) <= 120


def test_a_note_without_a_path_or_test_command_does_not_break_planning(
    tmp_path: Path,
) -> None:
    note(tmp_path, "Projects", "bare", "- [ ] still counts\n", front="privacy: shared")
    plan = plan_work(tmp_path, TODAY)
    assert [p.title for p in plan.proposals] == ["still counts"]


def test_a_broken_note_is_skipped_not_fatal(tmp_path: Path) -> None:
    (tmp_path / "Projects").mkdir()
    (tmp_path / "Projects" / "bad.md").write_bytes(b"\xff\xfe not utf8 \x00")
    project(tmp_path, "halo", "2026-10-27: kept: Real work")
    assert plan_work(tmp_path, TODAY).proposals[0].title.endswith("Real work")
