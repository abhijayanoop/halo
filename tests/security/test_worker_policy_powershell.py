"""On Windows Claude Code runs commands through a `PowerShell` tool, not `Bash`.
The same rules must hold for it: the test command and read-only git run unasked,
everything else asks, and nothing can smuggle a second command in."""

from pathlib import Path

import pytest

from halo.tools.worker_policy import decide_tool

TEST_CMD = "uv run --project day01 --with pytest pytest -q day01"


@pytest.fixture
def wt(tmp_path: Path) -> Path:
    root = tmp_path / "wt"
    root.mkdir()
    return root


def decide(wt: Path, command: str, tool: str = "PowerShell"):
    return decide_tool(tool, {"command": command}, worktree=wt, test_cmd=TEST_CMD)


@pytest.mark.parametrize(
    "command",
    [
        TEST_CMD,
        TEST_CMD + " -k count_words",
        "git diff",
        "git diff --stat",
        "git status",
    ],
)
def test_the_test_command_and_read_only_git_run_unasked_in_powershell(
    wt: Path, command: str
) -> None:
    assert decide(wt, command).verdict == "allow"


@pytest.mark.parametrize(
    "command",
    [
        TEST_CMD + "; Remove-Item -Recurse x",
        TEST_CMD + " | Out-File ../x",
        TEST_CMD + " && echo hi",
        "& evil.exe",
        "Invoke-WebRequest http://example.com",
        "iwr http://example.com -OutFile x",
        "Remove-Item -Recurse -Force .",
        "Get-Content ../secret.txt",
        "$env:NEBIUS_API_KEY",
        TEST_CMD + " $env:HOME",
        TEST_CMD + " `n Remove-Item x",
        "@(1,2)",
        ". ./script.ps1",
        "git push origin main",
        "git diff --output=../x",
        TEST_CMD + " ../../elsewhere",
    ],
)
def test_anything_beyond_the_allowlist_asks_as_high_risk_in_powershell(
    wt: Path, command: str
) -> None:
    d = decide(wt, command)
    assert d.verdict == "ask" and d.risk == "high"


def test_bash_still_behaves_as_before(wt: Path) -> None:
    assert decide(wt, TEST_CMD, tool="Bash").verdict == "allow"
    assert decide(wt, TEST_CMD + "; rm -rf /", tool="Bash").verdict == "ask"


def test_an_unrelated_unknown_tool_still_asks(wt: Path) -> None:
    d = decide_tool("Teleport", {"command": TEST_CMD}, worktree=wt, test_cmd=TEST_CMD)
    assert d.verdict == "ask" and d.risk == "high"
