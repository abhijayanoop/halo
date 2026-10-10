"""PostToolUse hook: format and lint the file Claude just edited.

Lint errors that can't be auto-fixed go to stderr with exit code 2, which
Claude Code shows to Claude so it fixes them in the same turn.
"""

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

data = json.load(sys.stdin)
file_path = data.get("tool_input", {}).get("file_path")
if not file_path:
    sys.exit(0)

path = Path(file_path)
root = Path(os.environ.get("CLAUDE_PROJECT_DIR", "."))


def run(cmd: list[str], cwd: Path = root) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, check=False)


if path.suffix == ".py":
    run(["uv", "run", "ruff", "format", str(path)])
    result = run(["uv", "run", "ruff", "check", "--fix", str(path)])
    if result.returncode != 0:
        print(
            f"ruff found problems in {path.name} that need a manual fix:\n{result.stdout[-3000:]}",
            file=sys.stderr,
        )
        sys.exit(2)
elif path.suffix in {".ts", ".tsx", ".css"} and "ui" in path.parts:
    npx = shutil.which("npx")
    if npx:
        run([npx, "prettier", "--write", str(path)], cwd=root / "ui")

sys.exit(0)
