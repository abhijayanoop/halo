"""Project notes: `Projects/<name>.md`, a typed view of the frontmatter.

    ---
    path: C:\\code\\halo
    test_cmd: uv run pytest -q
    claude_session_id: ""
    last_stop: ""
    ---

Reads are line based (no YAML library). Writes touch only the lines they set
and the session log they append to: the rest of the note is kept byte for byte,
including its line endings. Text written here comes from model or tool output,
so it is flattened to one line and stripped of anything that could forge
frontmatter, an inline field or a memory id.
"""

import re
from datetime import datetime
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict

from halo.memory.vault import VaultPathError, resolve_note

REQUIRED = ("path", "test_cmd")
SESSIONS_HEADING = "## Sessions"
MAX_TEXT = 300

_KEY = re.compile(r"^(?P<key>[A-Za-z_][\w-]*):[ \t]*(?P<value>.*?)\s*$")
_HEADING = re.compile(r"^#{1,6}\s")


class ProjectNoteError(ValueError):
    """A project note that is missing, malformed or not a valid name."""


class ProjectNote(BaseModel):
    model_config = ConfigDict(frozen=True)

    name: str
    path: str
    test_cmd: str
    default_branch: str = ""
    lint_cmd: str = ""
    stack: str = ""
    claude_session_id: str = ""
    last_stop: str = ""
    privacy: Literal["shared", "local"] = "shared"


def _note_path(vault: Path, name: str) -> Path:
    if not name or any(c in name for c in "/\\") or name.startswith("."):
        raise ProjectNoteError(f"not a project name: {name!r}")
    try:
        return resolve_note(vault, f"Projects/{name}.md")
    except VaultPathError as exc:
        raise ProjectNoteError(str(exc)) from exc


def _read(path: Path, name: str) -> str:
    try:
        return path.read_bytes().decode("utf-8")
    except FileNotFoundError:
        raise ProjectNoteError(f"no project note for {name!r} ({path})") from None


def _frontmatter_range(lines: list[str], name: str) -> tuple[int, int]:
    """Indexes of the opening and closing `---` lines."""
    if not lines or lines[0].rstrip("\r\n") != "---":
        raise ProjectNoteError(f"project note {name!r} has no frontmatter")
    for index in range(1, len(lines)):
        if lines[index].rstrip("\r\n") == "---":
            return 0, index
    raise ProjectNoteError(f"project note {name!r} has unclosed frontmatter")


def _unquote(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    return value


def _values(lines: list[str], start: int, end: int) -> dict[str, str]:
    found: dict[str, str] = {}
    for line in lines[start + 1 : end]:
        match = _KEY.match(line.rstrip("\r\n"))
        if match:
            found[match["key"]] = _unquote(match["value"])
    return found


def load(vault: Path, name: str) -> ProjectNote:
    """Read `Projects/<name>.md`; a missing note or required key is an error."""
    path = _note_path(vault, name)
    lines = _read(path, name).splitlines(keepends=True)
    start, end = _frontmatter_range(lines, name)
    values = _values(lines, start, end)
    missing = [key for key in REQUIRED if not values.get(key)]
    if missing:
        raise ProjectNoteError(
            f"project note {name!r} is missing: {', '.join(missing)}"
        )
    return ProjectNote(
        name=name,
        path=values["path"],
        test_cmd=values["test_cmd"],
        default_branch=values.get("default_branch", ""),
        lint_cmd=values.get("lint_cmd", ""),
        stack=values.get("stack", ""),
        claude_session_id=values.get("claude_session_id", ""),
        last_stop=values.get("last_stop", ""),
        privacy="local" if values.get("privacy", "").lower() == "local" else "shared",
    )


def _clean(text: str) -> str:
    """One short line with no brackets, carets, quotes, backslashes or `---`."""
    flat = " ".join(text.split())
    flat = flat.replace("[", "(").replace("]", ")").replace("^", "")
    flat = flat.replace('"', "'").replace("\\", "/")
    flat = re.sub(r"-{3,}", "-", flat)
    return flat[:MAX_TEXT].strip()


def _set_key(
    lines: list[str], start: int, end: int, key: str, value: str, eol: str
) -> None:
    """Replace the `key:` line inside the frontmatter, or add it before the close."""
    new = f'{key}: "{value}"{eol}'
    for index in range(start + 1, end):
        match = _KEY.match(lines[index].rstrip("\r\n"))
        if match and match["key"] == key:
            ending = lines[index][len(lines[index].rstrip("\r\n")) :] or eol
            lines[index] = f'{key}: "{value}"{ending}'
            return
    lines.insert(end, new)


def _write_if_changed(path: Path, old: str, lines: list[str]) -> None:
    text = "".join(lines)
    if text != old:
        path.write_bytes(text.encode("utf-8"))


def _apply(
    vault: Path,
    name: str,
    last_stop: str,
    session_id: str,
    log_line: str | None,
) -> None:
    path = _note_path(vault, name)
    text = _read(path, name)
    lines = text.splitlines(keepends=True)
    start, end = _frontmatter_range(lines, name)
    eol = "\r\n" if "\r\n" in text else "\n"
    _set_key(lines, start, end, "claude_session_id", _clean(session_id), eol)
    end = _frontmatter_range(lines, name)[1]
    _set_key(lines, start, end, "last_stop", _clean(last_stop), eol)
    if log_line is not None:
        _append_log(lines, log_line, eol)
    _write_if_changed(path, text, lines)


def _append_log(lines: list[str], entry: str, eol: str) -> None:
    heading = next(
        (i for i, ln in enumerate(lines) if ln.rstrip("\r\n") == SESSIONS_HEADING),
        None,
    )
    if heading is None:
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += eol
        if lines:
            lines.append(eol)
        lines.extend([SESSIONS_HEADING + eol, entry + eol])
        return
    stop = len(lines)
    for index in range(heading + 1, len(lines)):
        if _HEADING.match(lines[index]):
            stop = index
            break
    last = heading
    for index in range(heading + 1, stop):
        if lines[index].strip():
            last = index
    if not lines[last].endswith(("\n", "\r")):
        lines[last] += eol
    lines.insert(last + 1, entry + eol)


def set_session(vault: Path, name: str, *, last_stop: str, session_id: str) -> None:
    """Set `last_stop` and `claude_session_id`. A no-op if they already match."""
    _apply(vault, name, last_stop, session_id, None)


def record_stop(
    vault: Path, name: str, *, now: datetime, summary: str, session_id: str
) -> None:
    """Log a work session: a dated line under `## Sessions`, then `last_stop` and
    `claude_session_id` in the frontmatter. Nothing else in the note changes."""
    entry = f"{now.date().isoformat()}: {_clean(summary)}"
    _apply(vault, name, entry, session_id, f"- {entry}")
