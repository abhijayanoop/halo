"""Git worktree operations for Claude Code tasks.

Every task works in its own worktree on a ``halo/<slug>`` branch. Merging is
strictly local; nothing here ever pushes.
"""

from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

WORKTREE_DIRNAME = ".halo-worktrees"
BRANCH_PREFIX = "halo/"
MAX_SLUG_LEN = 48
GIT_TIMEOUT = 60
_SLUG_RE = re.compile(r"[a-z0-9](?:[a-z0-9-]*[a-z0-9])?")
_IDENT = ["-c", "user.name=Halo", "-c", "user.email=halo@localhost"]


class GitOpsError(Exception):
    """A git operation was refused or failed."""


class Worktree(BaseModel):
    model_config = ConfigDict(frozen=True)

    repo: Path
    path: Path
    slug: str
    branch: str
    base: str  # commit sha the branch was created from


class MergeResult(BaseModel):
    model_config = ConfigDict(frozen=True)

    merged: bool
    message: str = ""
    conflicts: list[str] = Field(default_factory=list)


def _git(cwd: Path, *args: str, check: bool = True) -> subprocess.CompletedProcess[str]:
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0"}
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=GIT_TIMEOUT,
            env=env,
            check=False,
        )
    except (subprocess.TimeoutExpired, OSError) as e:
        raise GitOpsError(f"git {args[0] if args else ''} failed: {e}") from e
    if check and proc.returncode != 0:
        raise GitOpsError(
            f"git {args[0]} failed: {(proc.stderr or proc.stdout).strip()}"
        )
    return proc


def validate_slug(slug: str) -> str:
    if (
        not isinstance(slug, str)
        or not slug
        or len(slug) > MAX_SLUG_LEN
        or not _SLUG_RE.fullmatch(slug)
        or "--" in slug
    ):
        raise GitOpsError(f"invalid slug: {str(slug)[:60]!r}")
    return slug


def _root(repo: Path) -> Path:
    return repo.resolve().parent / WORKTREE_DIRNAME


def _inside(child: Path, root: Path) -> bool:
    try:
        child.resolve().relative_to(root.resolve())
    except ValueError:
        return False
    return child.resolve() != root.resolve()


def default_branch(repo: Path) -> str:
    """origin/HEAD if set, else main/master if present, else the current branch."""
    p = _git(repo, "symbolic-ref", "--short", "refs/remotes/origin/HEAD", check=False)
    if p.returncode == 0 and p.stdout.strip().startswith("origin/"):
        return p.stdout.strip().removeprefix("origin/")
    for name in ("main", "master"):
        ref = f"refs/heads/{name}"
        if (
            _git(repo, "show-ref", "--verify", "--quiet", ref, check=False).returncode
            == 0
        ):
            return name
    return _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()


def _checked(wt: Worktree) -> None:
    if not _inside(wt.path, _root(wt.repo)):
        raise GitOpsError("worktree is not under the .halo-worktrees root")
    validate_slug(wt.slug)
    if wt.branch != BRANCH_PREFIX + wt.slug:
        raise GitOpsError("worktree branch does not match its slug")


def create_worktree(repo: Path, slug: str, *, base: str | None = None) -> Worktree:
    validate_slug(slug)
    repo = repo.resolve()
    root = _root(repo)
    path = root / repo.name / slug
    if not _inside(path, root):
        raise GitOpsError("worktree path escapes the .halo-worktrees root")
    branch = BRANCH_PREFIX + slug
    if path.exists():
        raise GitOpsError(f"worktree folder already exists: {slug}")
    ref = f"refs/heads/{branch}"
    if _git(repo, "show-ref", "--verify", "--quiet", ref, check=False).returncode == 0:
        raise GitOpsError(f"branch already exists: {branch}")
    base_ref = base if base is not None else default_branch(repo)
    if base_ref.startswith("-"):
        raise GitOpsError("invalid base")
    sha = _git(
        repo, "rev-parse", "--verify", "--end-of-options", f"{base_ref}^{{commit}}"
    ).stdout.strip()
    path.parent.mkdir(parents=True, exist_ok=True)
    _git(repo, "worktree", "add", "-b", branch, "--", str(path), sha)
    return Worktree(repo=repo, path=path.resolve(), slug=slug, branch=branch, base=sha)


def discard_worktree(wt: Worktree) -> None:
    _checked(wt)
    _git(wt.repo, "worktree", "remove", "--force", "--", str(wt.path))
    _git(wt.repo, "worktree", "prune", check=False)
    _git(wt.repo, "branch", "-D", wt.branch, check=False)


def _mark_untracked(wt: Worktree) -> None:
    _checked(wt)
    _git(wt.path, "add", "-N", "--", ".")  # intent-to-add: no content staged


def diff_stat(wt: Worktree) -> str:
    _mark_untracked(wt)
    return _git(wt.path, "diff", "--stat", wt.base, "--").stdout


def diff(wt: Worktree) -> str:
    _mark_untracked(wt)
    return _git(wt.path, "diff", wt.base, "--").stdout


def changed_files(wt: Worktree) -> list[str]:
    _mark_untracked(wt)
    out = _git(wt.path, "diff", "--name-only", "-z", wt.base, "--").stdout
    return [f for f in out.split("\0") if f]


def merge_worktree(repo: Path, wt: Worktree) -> MergeResult:
    """Merge halo/<slug> into the default branch locally. Never pushes."""
    repo = repo.resolve()
    _checked(wt)
    if wt.repo.resolve() != repo:
        raise GitOpsError("worktree belongs to a different repository")
    target = default_branch(repo)
    current = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.strip()
    if current != target:
        raise GitOpsError(f"main checkout is on {current!r}, not {target!r}")
    if _git(repo, "status", "--porcelain", "--untracked-files=no").stdout.strip():
        raise GitOpsError("main checkout has uncommitted changes")

    if _git(wt.path, "status", "--porcelain").stdout.strip():
        _git(wt.path, "add", "-A")
        _git(
            wt.path,
            *_IDENT,
            "commit",
            "-m",
            f"chore(halo): save changes from task {wt.slug}",
        )

    proc = _git(
        repo,
        *_IDENT,
        "merge",
        "--no-ff",
        "-m",
        f"feat(halo): merge task {wt.slug}",
        wt.branch,
        check=False,
    )
    if proc.returncode == 0:
        return MergeResult(merged=True, message=proc.stdout.strip())
    unmerged = _git(
        repo, "diff", "--name-only", "--diff-filter=U", "-z", check=False
    ).stdout
    conflicts = [f for f in unmerged.split("\0") if f]
    _git(repo, "merge", "--abort", check=False)
    return MergeResult(
        merged=False, message=(proc.stdout + proc.stderr).strip(), conflicts=conflicts
    )
