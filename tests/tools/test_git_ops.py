from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from halo.tools import git_ops
from halo.tools.git_ops import GitOpsError, Worktree


def _git(cwd: Path, *args: str) -> str:
    out = subprocess.run(
        ["git", "-c", "user.name=T", "-c", "user.email=t@example.com", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=True,
    )
    return out.stdout


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "proj" / "myrepo"
    r.mkdir(parents=True)
    _git(r, "init", "-b", "main")
    (r / "a.txt").write_text("one\n")
    _git(r, "add", ".")
    _git(r, "commit", "-m", "init")
    return r


def _branches(repo: Path) -> list[str]:
    return _git(repo, "branch", "--format=%(refname:short)").split()


def test_create_worktree(repo: Path) -> None:
    wt = git_ops.create_worktree(repo, "fix-bug")
    expected = repo.parent.resolve() / ".halo-worktrees" / "myrepo" / "fix-bug"
    assert wt.path.resolve() == expected
    assert wt.branch == "halo/fix-bug"
    assert (wt.path / "a.txt").exists()
    assert "halo/fix-bug" in _branches(repo)


def test_duplicate_refused(repo: Path) -> None:
    git_ops.create_worktree(repo, "dup")
    with pytest.raises(GitOpsError):
        git_ops.create_worktree(repo, "dup")


def test_existing_branch_refused(repo: Path) -> None:
    _git(repo, "branch", "halo/taken")
    with pytest.raises(GitOpsError):
        git_ops.create_worktree(repo, "taken")


@pytest.mark.parametrize(
    "slug", ["../x", "a/b", "a\b", "-rf", "Upper", "", "x" * 200, "a..b", "a b"]
)
def test_bad_slugs(repo: Path, slug: str) -> None:
    with pytest.raises(GitOpsError):
        git_ops.create_worktree(repo, slug)
    assert not (repo.parent / ".halo-worktrees").exists() or not any(
        (repo.parent / ".halo-worktrees").rglob("*.txt")
    )


def test_diff_includes_untracked(repo: Path) -> None:
    wt = git_ops.create_worktree(repo, "d")
    (wt.path / "a.txt").write_text("one\ntwo\n")
    (wt.path / "new.txt").write_text("hello\n")
    assert sorted(git_ops.changed_files(wt)) == ["a.txt", "new.txt"]
    d = git_ops.diff(wt)
    assert "+two" in d and "+hello" in d
    assert "2 files changed" in git_ops.diff_stat(wt)
    # nothing really staged with content
    assert _git(wt.path, "diff", "--cached", "--name-only").split() in ([], ["new.txt"])


def test_discard_removes_folder_and_branch(repo: Path) -> None:
    wt = git_ops.create_worktree(repo, "gone")
    (wt.path / "junk.txt").write_text("x")
    git_ops.discard_worktree(wt)
    assert not wt.path.exists()
    assert "halo/gone" not in _branches(repo)


def test_discard_refuses_outside_root(repo: Path, tmp_path: Path) -> None:
    fake = Worktree(repo=repo, path=repo, slug="x", branch="main", base="0" * 40)
    with pytest.raises(GitOpsError):
        git_ops.discard_worktree(fake)
    assert repo.exists()


def test_merge_success(repo: Path) -> None:
    wt = git_ops.create_worktree(repo, "feat")
    (wt.path / "b.txt").write_text("b\n")  # uncommitted: Halo commits it
    res = git_ops.merge_worktree(repo, wt)
    assert res.merged and not res.conflicts
    assert (repo / "b.txt").read_text() == "b\n"
    assert _git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip() == "main"


def test_merge_refused_on_dirty_main(repo: Path) -> None:
    wt = git_ops.create_worktree(repo, "feat")
    (wt.path / "b.txt").write_text("b\n")
    (repo / "a.txt").write_text("dirty\n")
    with pytest.raises(GitOpsError):
        git_ops.merge_worktree(repo, wt)
    assert not (repo / "b.txt").exists()


def test_merge_refused_off_default_branch(repo: Path) -> None:
    wt = git_ops.create_worktree(repo, "feat")
    _git(repo, "checkout", "-b", "other")
    with pytest.raises(GitOpsError):
        git_ops.merge_worktree(repo, wt)


def test_merge_conflict_aborts_cleanly(repo: Path) -> None:
    wt = git_ops.create_worktree(repo, "c")
    (wt.path / "a.txt").write_text("theirs\n")
    (repo / "a.txt").write_text("ours\n")
    _git(repo, "commit", "-am", "ours")
    res = git_ops.merge_worktree(repo, wt)
    assert not res.merged
    assert "a.txt" in res.conflicts
    assert _git(repo, "status", "--porcelain").strip() == ""
    assert (repo / "a.txt").read_text() == "ours\n"
    assert not (repo / ".git" / "MERGE_HEAD").exists()


def test_never_pushes(repo: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    real = subprocess.run

    def spy(cmd, *a, **k):  # type: ignore[no-untyped-def]
        calls.append(list(cmd))
        return real(cmd, *a, **k)

    monkeypatch.setattr(subprocess, "run", spy)
    wt = git_ops.create_worktree(repo, "np")
    (wt.path / "z.txt").write_text("z")
    git_ops.merge_worktree(repo, wt)
    assert calls
    assert all("push" not in c for c in calls)
    assert _git(repo, "remote").strip() == ""
