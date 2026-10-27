"""What a coding worker may do on its own, what needs the user, and what never happens.

The worker's own edits stay inside its worktree; the test command and read-only git
run unasked; anything else asks, as high risk. Shell metacharacters are never
inside an unasked command, so an allowed prefix cannot smuggle a second command.
"""

import re
import shlex
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from halo.core.contracts import RiskLevel

Verdict = Literal["allow", "ask", "deny"]

READ_TOOLS = ("Read", "Glob", "Grep")
EDIT_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
NETWORK_TOOLS = ("WebFetch", "WebSearch")

# No bare "Bash": shell commands are listed per command (see `allowed_tools`).
ALLOWED_TOOLS = [*READ_TOOLS, *EDIT_TOOLS]
DISALLOWED_TOOLS = list(NETWORK_TOOLS)

# A Windows drive or UNC prefix that this OS would read as a relative name (on macOS
# or Linux "C:/x" is a file called "C:") is never a path inside a worktree.
_FOREIGN_ROOT = re.compile(r"^(?:[A-Za-z]:|[\\/]{2})")
_SHELL_META = set(";&|`$<>\n\r(){}")
_PATH_KEYS = ("file_path", "notebook_path", "path")
_GIT_FORBIDDEN = (
    "--output",
    "--ext-diff",
    "--textconv",
    "--no-index",
    "-c",
    "--exec-path",
)


@dataclass(frozen=True)
class ToolDecision:
    verdict: Verdict
    risk: RiskLevel = "low"
    reason: str = ""


def allowed_tools(test_cmd: str) -> list[str]:
    """The SDK's pre-approved list: file tools plus exactly the commands Halo trusts."""
    return [
        *ALLOWED_TOOLS,
        f"Bash({test_cmd.strip()} *)",
        "Bash(git diff *)",
        "Bash(git status *)",
    ]


def _inside(worktree: Path, raw: str) -> Path | None:
    """The resolved path if it stays inside the worktree (symlinks followed), else None."""
    if _FOREIGN_ROOT.match(raw) and not Path(raw).is_absolute():
        return None
    root = worktree.resolve()
    try:
        path = (root / raw).resolve()
    except (OSError, ValueError):
        return None
    return path if path.is_relative_to(root) else None


def _in_git_dir(worktree: Path, path: Path) -> bool:
    return ".git" in path.relative_to(worktree.resolve()).parts


def _path_args_ok(worktree: Path, tokens: list[str]) -> bool:
    for token in tokens:
        if token.startswith("-"):
            if token.startswith(_GIT_FORBIDDEN):
                return False
            continue
        if ".." in Path(token).parts or Path(token).is_absolute():
            return False
    return True


def _bash(command: str, worktree: Path, test_cmd: str) -> ToolDecision:
    ask = ToolDecision("ask", "high", "A command Halo does not run on its own")
    if any(ch in _SHELL_META for ch in command):
        return ask
    try:
        tokens = shlex.split(command)
        test_tokens = shlex.split(test_cmd)
    except ValueError:
        return ask
    if not tokens:
        return ask
    for prefix in (test_tokens, ["git", "diff"], ["git", "status"]):
        if (
            prefix
            and tokens[: len(prefix)] == prefix
            and _path_args_ok(worktree, tokens[len(prefix) :])
        ):
            return ToolDecision("allow")
    return ask


def decide_tool(
    tool: str, args: dict[str, Any], *, worktree: Path, test_cmd: str
) -> ToolDecision:
    if tool in NETWORK_TOOLS:
        return ToolDecision("deny", "high", "The coding worker has no network access")
    if tool in READ_TOOLS or tool in EDIT_TOOLS:
        for key in _PATH_KEYS:
            raw = args.get(key)
            if raw is None:
                continue
            path = _inside(worktree, str(raw))
            if path is None:
                return ToolDecision(
                    "deny", "high", "That path is outside the work folder"
                )
            if tool in EDIT_TOOLS and _in_git_dir(worktree, path):
                return ToolDecision("deny", "high", "Git's own folder is off limits")
        return ToolDecision("allow", "medium" if tool in EDIT_TOOLS else "low")
    if tool == "Bash":
        return _bash(str(args.get("command", "")), worktree, test_cmd)
    return ToolDecision("ask", "high", f"Halo does not know the tool {tool}")
