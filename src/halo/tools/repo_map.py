"""Compact repo map for prompts: file tree, key files, top-level symbols.

Pure data in, plain text out. No model is called here. Repo content is treated as
untrusted data: it is only read, parsed and summarised, never executed.
"""

from __future__ import annotations

import ast
import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_MAX_TOKENS = 4000
DEFAULT_CACHE_DIR = Path.home() / ".halo" / "cache" / "repo_map"

_GIT_TIMEOUT = 20
_MAX_FILE_BYTES = 200_000
_EXCERPT_CHARS = 240
_MAX_FILES = 5000
_CACHE_VERSION = 1

_KEY_FILE_RE = re.compile(
    r"^(readme[^/]*|claude\.md|package\.json|pyproject\.toml)$", re.IGNORECASE
)
_LOCKFILES = {
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "uv.lock",
    "poetry.lock",
    "cargo.lock",
    "pipfile.lock",
    "composer.lock",
    "gemfile.lock",
}
_SKIP_DIRS = {"node_modules", ".git", "__pycache__", ".venv", "venv", "dist", "build"}
_BINARY_EXT = {
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".ico", ".pdf", ".zip", ".gz", ".tar",
    ".woff", ".woff2", ".ttf", ".otf", ".mp3", ".mp4", ".wav", ".onnx", ".bin", ".pyc",
    ".so", ".dll", ".exe", ".sqlite", ".db", ".lock", ".map",
}  # fmt: skip

_TS_EXT = {".ts", ".tsx"}
_TS_DECL = re.compile(
    r"^(?P<exp>export\s+(?:default\s+)?)?(?:declare\s+)?(?:abstract\s+)?(?:async\s+)?"
    r"(?P<kind>function\*?|class|interface|type|enum|const)\s+(?P<name>[A-Za-z_$][\w$]*)"
)


@dataclass
class RepoMap:
    """Structured repo summary. `text` is the rendered, budgeted prompt form."""

    root: str
    head: str
    files: list[str] = field(default_factory=list)
    key_files: dict[str, str] = field(default_factory=dict)
    symbols: dict[str, list[str]] = field(default_factory=dict)
    text: str = ""
    from_cache: bool = False

    @property
    def token_estimate(self) -> int:
        return len(self.text) // 4

    def render(self, max_tokens: int = DEFAULT_MAX_TOKENS) -> str:
        return _render(self, max_tokens)


def _git(repo: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-c", "core.quotepath=off", *args],
        cwd=repo,
        capture_output=True,
        timeout=_GIT_TIMEOUT,
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"git {args[0]} failed in {repo}")
    return proc.stdout.decode("utf-8", errors="replace")


def _head(repo: Path) -> str:
    try:
        return _git(repo, "rev-parse", "HEAD").strip()
    except RuntimeError:
        return "nohead"


def _dirty_hash(repo: Path) -> str:
    """Hash of `git status --porcelain` plus size/mtime of each dirty path."""
    status = _git(repo, "status", "--porcelain", "-z", "--untracked-files=all")
    h = hashlib.sha256(status.encode("utf-8"))
    for entry in status.split("\0"):
        if len(entry) < 4:
            continue
        try:
            st = (repo / entry[3:]).stat()
            h.update(f"{entry[3:]}:{st.st_size}:{st.st_mtime_ns}".encode())
        except OSError:
            continue
    return h.hexdigest()


def _is_binary(path: Path) -> bool:
    if path.suffix.lower() in _BINARY_EXT:
        return True
    try:
        with path.open("rb") as f:
            return b"\0" in f.read(4096)
    except OSError:
        return True


def _safe_path(repo: Path, rel: str) -> Path | None:
    """Return the file path if it is a regular file inside the repo, else None."""
    p = repo / rel
    try:
        if p.is_symlink():
            return None
        p.resolve().relative_to(repo)
        return p if p.is_file() else None
    except (OSError, ValueError):
        return None


def _list_files(repo: Path) -> list[str]:
    out = _git(repo, "ls-files", "-z", "--cached", "--others", "--exclude-standard")
    seen: set[str] = set()
    result: list[str] = []
    for rel in out.split("\0"):
        if not rel or rel in seen:
            continue
        seen.add(rel)
        parts = rel.split("/")
        if any(d in _SKIP_DIRS for d in parts[:-1]) or parts[-1].lower() in _LOCKFILES:
            continue
        p = _safe_path(repo, rel)
        if p is None or _is_binary(p):
            continue
        result.append(rel)
        if len(result) >= _MAX_FILES:
            break
    return sorted(result)


def _read_text(path: Path, limit: int = _MAX_FILE_BYTES) -> str | None:
    try:
        if path.stat().st_size > limit:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def _first_line(doc: str | None) -> str:
    if not doc or not doc.strip():
        return ""
    return doc.strip().splitlines()[0].strip()


def _py_symbols(source: str) -> list[str]:
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, RecursionError):
        return []
    out: list[str] = []
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            kw = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            ret = f" -> {ast.unparse(node.returns)}" if node.returns else ""
            sig = f"{kw} {node.name}({ast.unparse(node.args)}){ret}"
        elif isinstance(node, ast.ClassDef):
            bases = ", ".join(ast.unparse(b) for b in node.bases)
            sig = f"class {node.name}" + (f"({bases})" if bases else "")
        else:
            continue
        doc = _first_line(ast.get_docstring(node))
        sig = sig[:140]
        out.append(f"{sig}  # {doc[:100]}" if doc else sig)
    return out


def _ts_symbols(source: str) -> list[str]:
    out: list[str] = []
    for line in source.splitlines():
        if not line or line[0] in " \t/*":
            continue
        m = _TS_DECL.match(line)
        if not m:
            continue
        name, kind = m["name"], m["kind"]
        exported = bool(m["exp"])
        if not exported and not (name[0].isupper() and kind in {"function", "const"}):
            continue  # unexported helpers are noise; unexported components are kept
        sig = re.split(r"\s*(?:\{|=>|=\s*\()", line, maxsplit=1)[0].strip()
        out.append((sig or f"{kind} {name}")[:140])
    return out


def _symbols_for(rel: str, path: Path) -> list[str]:
    suffix = Path(rel).suffix.lower()
    if suffix == ".py":
        src = _read_text(path)
        return _py_symbols(src) if src is not None else []
    if suffix in _TS_EXT:
        src = _read_text(path)
        return _ts_symbols(src) if src is not None else []
    return []


def _build(repo: Path, head: str) -> RepoMap:
    files = _list_files(repo)
    key_files: dict[str, str] = {}
    symbols: dict[str, list[str]] = {}
    for rel in files:
        path = repo / rel
        if rel.count("/") <= 1 and _KEY_FILE_RE.match(Path(rel).name):
            text = _read_text(path, 64_000)
            if text is not None:
                key_files[rel] = " ".join(text.split())[:_EXCERPT_CHARS]
        syms = _symbols_for(rel, path)
        if syms:
            symbols[rel] = syms
    return RepoMap(
        root=repo.name, head=head, files=files, key_files=key_files, symbols=symbols
    )


def _is_test(rel: str) -> bool:
    parts = rel.split("/")
    name = parts[-1]
    return (
        any(p in {"tests", "test", "__tests__", "fixtures"} for p in parts[:-1])
        or name.startswith("test_")
        or ".test." in name
        or ".spec." in name
    )


def _render(m: RepoMap, max_tokens: int) -> str:
    """Render in priority order; later (less important) blocks are dropped first."""
    budget = max(max_tokens, 1) * 4
    blocks: list[str] = [f"# repo: {m.root} ({len(m.files)} files)"]

    if m.key_files:
        blocks.append("## key files")
        blocks.extend(f"- {rel}: {ex}" for rel, ex in m.key_files.items())

    # File tree: shallow non-test files listed; the rest summarised per directory.
    blocks.append("## files")
    shown = [f for f in m.files if f.count("/") <= 3 and not _is_test(f)]
    shown_set = set(shown)
    by_dir: dict[str, list[str]] = {}
    for f in shown:
        d, _, n = f.rpartition("/")
        by_dir.setdefault(d, []).append(n)
    for d in sorted(by_dir):
        blocks.append(f"{d or '.'}/: {' '.join(by_dir[d])}")
    counts: dict[str, int] = {}
    for f in m.files:
        if f in shown_set:
            continue
        d = "/".join(f.split("/")[:2][:-1]) or "."
        counts[d] = counts.get(d, 0) + 1
    for d in sorted(counts):
        blocks.append(f"{d}/ ... {counts[d]} more files")

    # Symbols: shallow non-test files first, deep and test files last.
    ordered = sorted(m.symbols, key=lambda f: (_is_test(f), f.count("/"), f))
    if ordered:
        blocks.append("## symbols")
        blocks.extend(
            f"{f}\n" + "\n".join(f"  {s}" for s in m.symbols[f]) for f in ordered
        )

    out: list[str] = []
    used = 0
    truncated = False
    for b in blocks:
        cost = len(b) + 1
        if used + cost > budget - 20:
            truncated = True
            continue  # a smaller, later block may still fit
        out.append(b)
        used += cost
    if truncated:
        out.append("... (truncated)")
    return "\n".join(out)[:budget]


def _cache_file(cache_dir: Path, repo: Path) -> Path:
    digest = hashlib.sha256(str(repo).encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"{digest}.json"


def _load_cache(path: Path, key: str) -> RepoMap | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if data.get("version") != _CACHE_VERSION or data.get("key") != key:
            return None
        m = RepoMap(**data["map"])
    except (OSError, ValueError, TypeError, KeyError):
        return None
    m.from_cache = True
    return m


def _store_cache(path: Path, key: str, m: RepoMap) -> None:
    payload = {
        "version": _CACHE_VERSION,
        "key": key,
        "map": {
            "root": m.root,
            "head": m.head,
            "files": m.files,
            "key_files": m.key_files,
            "symbols": m.symbols,
        },
    }
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(payload), encoding="utf-8")
        tmp.replace(path)
    except OSError:
        pass  # caching is best-effort


def build_repo_map(
    repo: Path,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    cache_dir: Path | None = None,
) -> RepoMap:
    """Map `repo` (a git checkout). Cached by HEAD plus working-tree state."""
    repo = Path(repo).resolve()
    head = _head(repo)
    key = f"{head}:{_dirty_hash(repo)}"
    cache_path = _cache_file(
        cache_dir if cache_dir is not None else DEFAULT_CACHE_DIR, repo
    )
    m = _load_cache(cache_path, key)
    if m is None:
        m = _build(repo, head)
        _store_cache(cache_path, key, m)
    m.text = _render(m, max_tokens)
    return m
