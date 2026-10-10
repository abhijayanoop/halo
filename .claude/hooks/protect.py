"""PreToolUse hook: block edits to protected files.

Claude Code sends the tool call as JSON on stdin. Exit code 2 blocks the edit,
and the message on stderr tells Claude why.
"""

import json
import os
import sys
from pathlib import PurePosixPath

data = json.load(sys.stdin)
raw = data.get("tool_input", {}).get("file_path", "")
path = PurePosixPath(raw.replace("\\", "/"))
posix = path.as_posix()


def block(reason: str) -> None:
    print(reason, file=sys.stderr)
    sys.exit(2)


if path.name.startswith(".env") and path.name != ".env.example":
    block(f"{path.name} holds secrets and is protected. Ask the user to edit it.")

if path.name in {"LICENSE", "uv.lock", "package-lock.json"}:
    block(
        f"{path.name} is protected. Lockfiles change only via uv or npm; LICENSE never changes."
    )

frozen = ("docs/CONTRACTS.md", "halo/core/contracts.py")
if posix.endswith(frozen) and os.environ.get("HALO_CONTRACT_EDIT") != "1":
    block(
        "Contracts are frozen. Propose the change to the user; it is applied with "
        "/add-event in a session started with HALO_CONTRACT_EDIT=1."
    )

is_test = "tests" in path.parts or posix.endswith((".test.ts", ".test.tsx"))
if os.environ.get("HALO_LOCK_TESTS") == "1" and is_test:
    block(
        "Tests are locked for this session (HALO_LOCK_TESTS=1). Make them pass without editing them."
    )

sys.exit(0)
