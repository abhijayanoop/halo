"""Reading and writing memories in an Obsidian vault.

A memory is one bullet with Obsidian inline fields and a block id:

    - Picked pywebview for the HUD [src:: you] [trust:: high] [at:: 2026-10-10] ^m-4f2a

Writes touch only the line they add or remove: the rest of the note is kept
byte for byte, including its line endings.
"""

import hashlib
import re
import secrets
import shutil
from datetime import UTC, date, datetime
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Literal, get_args
from urllib.parse import quote

from halo.core.contracts import MemoryItem, MemorySource, TrustLevel

_BULLET = re.compile(r"^\s*[-*]\s+(?P<body>.*?)\s*$")
_FIELD = re.compile(
    r"\[(?P<key>src|trust|at|exp|sup|subject)::\s*(?P<value>[^\]]*?)\s*\]"
)
_BLOCK = re.compile(r"\s\^(?P<id>[A-Za-z0-9-]+)\s*$")
_FRONTMATTER = re.compile(r"\A---\r?\n(?P<body>.*?)\r?\n---\r?\n", re.DOTALL)
_PRIVACY = re.compile(r"^privacy:\s*(?P<value>\w+)\s*$", re.MULTILINE)
_LOCAL_FOLDERS = {"finance"}  # notes created here are privacy: local

TEMPLATE_DIR = Path(__file__).parent / "vault_template"


class VaultPathError(ValueError):
    """A note path that points outside the vault."""


def resolve_note(vault: Path, relative: str) -> Path:
    """The note at `relative` inside `vault`; anything that escapes it is refused."""
    if (
        PurePosixPath(relative).is_absolute()
        or PureWindowsPath(relative).is_absolute()
        or PureWindowsPath(relative).drive
        or ".." in PurePosixPath(relative.replace("\\", "/")).parts
    ):
        raise VaultPathError(f"not a path inside the vault: {relative!r}")
    root = vault.resolve()
    path = (root / relative).resolve()
    if not path.is_relative_to(root):
        raise VaultPathError(f"not a path inside the vault: {relative!r}")
    return path


def _read(path: Path) -> str:
    return path.read_bytes().decode("utf-8")


def note_privacy(path: Path) -> Literal["shared", "local"]:
    """`privacy: local` in the note's frontmatter, otherwise shared."""
    try:
        match = _FRONTMATTER.match(_read(path))
    except OSError:
        return "shared"
    if match and (found := _PRIVACY.search(match.group("body"))):
        return "local" if found.group("value").lower() == "local" else "shared"
    return "shared"


def _fields(body: str) -> tuple[str, dict[str, str], str | None]:
    """Split a bullet into (fact, inline fields, explicit block id)."""
    fields = {m["key"]: m["value"] for m in _FIELD.finditer(body)}
    text = _FIELD.sub("", body)
    block = _BLOCK.search(f" {text}")
    if block:
        text = f" {text}"[: block.start()]
    return " ".join(text.split()), fields, block["id"] if block else None


def _line_id(fact: str, explicit: str | None) -> str:
    if explicit:
        return f"^{explicit}"
    return "^h-" + hashlib.sha1(fact.encode("utf-8")).hexdigest()[:8]


def _day(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.combine(
            date.fromisoformat(value[:10]), datetime.min.time(), UTC
        )
    except ValueError:
        return None


def _parse_line(
    line: str,
    relative: str,
    privacy: Literal["shared", "local"],
    default_at: datetime,
) -> MemoryItem | None:
    bullet = _BULLET.match(line)
    if not bullet:
        return None
    fact, fields, explicit = _fields(bullet["body"])
    source = fields.get("src")
    if not fact or source not in get_args(MemorySource):
        return None  # a plain bullet is not a memory
    trust = fields.get("trust")
    return MemoryItem(
        fact=fact,
        source=source,  # type: ignore[arg-type]
        trust=trust if trust in get_args(TrustLevel) else "medium",  # type: ignore[arg-type]
        created_at=_day(fields.get("at")) or default_at,
        expires_at=_day(fields.get("exp")),
        block_id=_line_id(fact, explicit),
        note_path=relative,
        superseded=fields.get("sup", "").lower() == "true",
        privacy=privacy,
    )


def parse_note(path: Path, vault: Path) -> list[MemoryItem]:
    """Every memory bullet in the note, in file order."""
    try:
        text = _read(path)
        default_at = datetime.fromtimestamp(path.stat().st_mtime, UTC)
    except OSError:
        return []
    relative = path.resolve().relative_to(vault.resolve()).as_posix()
    privacy = note_privacy(path)
    items = (
        _parse_line(line, relative, privacy, default_at) for line in text.splitlines()
    )
    return [item for item in items if item is not None]


def _clean_fact(fact: str) -> str:
    """One line, with no brackets: a fact from anywhere (even a web page) must not
    be able to forge the inline fields or a block id."""
    flat = " ".join(fact.split()).replace("[", "(").replace("]", ")")
    return flat.replace("^", "").strip()


def append_memory(
    path: Path,
    vault: Path,
    fact: str,
    *,
    source: MemorySource,
    trust: TrustLevel,
    now: datetime,
    expires_at: datetime | None = None,
) -> MemoryItem:
    """Add one memory line to the end of the note (created if missing)."""
    fact = _clean_fact(fact)
    if not fact:
        raise ValueError("a memory needs some text")
    relative = path.resolve().relative_to(vault.resolve()).as_posix()
    if path.exists():
        text = _read(path)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        local = PurePosixPath(relative).parts[0].lower() in _LOCAL_FOLDERS
        text = "---\nprivacy: local\n---\n" if local else ""
    eol = "\r\n" if "\r\n" in text else "\n"
    existing = set(re.findall(r"\^([A-Za-z0-9-]+)\s*$", text, re.MULTILINE))
    block = f"m-{secrets.token_hex(2)}"
    for size in (2, 2, 2, 3, 4):  # a longer id only if short ones keep colliding
        block = f"m-{secrets.token_hex(size)}"
        if block not in existing:
            break
    line = (
        f"- {fact} [src:: {source}] [trust:: {trust}] [at:: {now.date().isoformat()}]"
    )
    if expires_at is not None:
        line += f" [exp:: {expires_at.date().isoformat()}]"
    line += f" ^{block}"
    if text and not text.endswith(("\n", "\r")):
        text += eol
    path.write_bytes((text + line + eol).encode("utf-8"))
    return next(i for i in parse_note(path, vault) if i.block_id == f"^{block}")


def delete_memory(path: Path, block_id: str) -> bool:
    """Remove the one line with this block id. Everything else stays as it was."""
    try:
        text = _read(path)
    except OSError:
        return False
    lines = text.splitlines(keepends=True)
    for index, line in enumerate(lines):
        bullet = _BULLET.match(line)
        if not bullet:
            continue
        fact, fields, explicit = _fields(bullet["body"])
        if "src" in fields and _line_id(fact, explicit) == block_id:
            del lines[index]
            path.write_bytes("".join(lines).encode("utf-8"))
            return True
    return False


def obsidian_link(vault: Path, note_path: str) -> str:
    """An obsidian:// link that opens the note in the vault."""
    name = note_path.removesuffix(".md")
    return (
        f"obsidian://open?vault={quote(vault.name, safe='')}"
        f"&file={quote(name, safe='')}"
    )


def ensure_vault(vault: Path) -> bool:
    """Copy the starter vault into `vault` the first time. An existing,
    non-empty folder is never touched. True if it was created."""
    if vault.exists() and any(vault.iterdir()):
        return False
    for source in sorted(TEMPLATE_DIR.rglob("*")):
        target = vault / source.relative_to(TEMPLATE_DIR)
        if source.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif source.name != ".gitkeep":
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    return True
