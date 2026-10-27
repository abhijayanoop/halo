from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from halo.tools.repo_map import RepoMap, build_repo_map

GIT = ["git", "-c", "user.name=T", "-c", "user.email=t@example.com"]


def git(repo: Path, *args: str) -> None:
    subprocess.run([*GIT, *args], cwd=repo, check=True, capture_output=True)


def write(repo: Path, rel: str, text: str) -> None:
    p = repo / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text, encoding="utf-8")


@pytest.fixture
def repo(tmp_path: Path) -> Path:
    r = tmp_path / "repo"
    r.mkdir()
    git(r, "init", "-q")
    write(r, "README.md", "# Demo\nA demo project for testing.\n")
    write(r, "pyproject.toml", '[project]\nname = "demo"\n')
    write(r, ".gitignore", "ignored.txt\n")
    write(r, "ignored.txt", "x")
    write(
        r,
        "src/app.py",
        'def run(x: int) -> int:\n    """Run the thing.\n\n    More."""\n    return x\n\n'
        "class Engine:\n    '''Engine class.'''\n\n    def go(self): ...\n",
    )
    write(r, "src/broken.py", "def (:\n  nope\n")
    write(
        r,
        "ui/App.tsx",
        "export function App() { return null }\n"
        "export const Card = () => null\n"
        "export interface Props { a: string }\n"
        "export type Mode = 'a' | 'b'\n"
        "export class Store {}\n"
        "function hidden() {}\n",
    )
    write(r, "package-lock.json", "{}")
    write(r, "node_modules/x/index.js", "x")
    write(r, "blob.bin", "a\x00b")
    git(r, "add", "-A")
    git(r, "add", "-f", "node_modules/x/index.js")
    git(r, "commit", "-q", "-m", "init")
    return r


def test_file_listing(repo: Path, tmp_path: Path) -> None:
    m = build_repo_map(repo, cache_dir=tmp_path / "c")
    assert "src/app.py" in m.files
    assert "ui/App.tsx" in m.files
    assert "ignored.txt" not in m.files
    assert not any("node_modules" in f for f in m.files)
    assert "package-lock.json" not in m.files
    assert "blob.bin" not in m.files
    assert "README.md" in m.key_files
    assert "demo project" in m.key_files["README.md"]


def test_python_symbols(repo: Path, tmp_path: Path) -> None:
    m = build_repo_map(repo, cache_dir=tmp_path / "c")
    syms = "\n".join(m.symbols["src/app.py"])
    assert "def run(x: int) -> int" in syms
    assert "Run the thing." in syms
    assert "class Engine" in syms
    assert "Engine class." in syms


def test_typescript_symbols(repo: Path, tmp_path: Path) -> None:
    m = build_repo_map(repo, cache_dir=tmp_path / "c")
    syms = "\n".join(m.symbols["ui/App.tsx"])
    for name in ("App", "Card", "Props", "Mode", "Store"):
        assert name in syms
    assert "hidden" not in syms


def test_syntax_error_file_does_not_crash(repo: Path, tmp_path: Path) -> None:
    m = build_repo_map(repo, cache_dir=tmp_path / "c")
    assert "src/broken.py" in m.files
    assert m.symbols.get("src/broken.py", []) == []


def test_budget_truncation(repo: Path, tmp_path: Path) -> None:
    for i in range(60):
        write(
            repo,
            f"tests/deep/t{i}.py",
            "\n".join(f"def test_{j}(): ..." for j in range(20)),
        )
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "more")
    big = build_repo_map(repo, max_tokens=100000, cache_dir=tmp_path / "c")
    small = build_repo_map(repo, max_tokens=600, cache_dir=tmp_path / "c")
    assert len(big.text) > len(small.text)
    assert len(small.text) / 4 <= 600
    assert "src/app.py" in small.text
    assert "def run" in small.text  # top-level symbols outlive deep test symbols
    assert "tests/deep/t59.py" not in small.text


def test_cache_hit_and_misses(repo: Path, tmp_path: Path) -> None:
    cache = tmp_path / "c"
    first = build_repo_map(repo, cache_dir=cache)
    assert not first.from_cache
    assert build_repo_map(repo, cache_dir=cache).from_cache
    # uncommitted edit -> miss
    write(repo, "src/app.py", "def other(): ...\n")
    edited = build_repo_map(repo, cache_dir=cache)
    assert not edited.from_cache
    assert "def other" in "\n".join(edited.symbols["src/app.py"])
    # editing the same dirty file again -> miss
    write(repo, "src/app.py", "def third(): ...\n")
    assert not build_repo_map(repo, cache_dir=cache).from_cache
    # commit -> miss
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "c2")
    assert not build_repo_map(repo, cache_dir=cache).from_cache
    assert build_repo_map(repo, cache_dir=cache).from_cache


def test_maps_real_halo_repo(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[2]
    m: RepoMap = build_repo_map(root, max_tokens=4000, cache_dir=tmp_path / "c")
    assert len(m.text) / 4 <= 4000
    assert "pyproject.toml" in m.text
    assert any(f.startswith("src/halo/") for f in m.files)
