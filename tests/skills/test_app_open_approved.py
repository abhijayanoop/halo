"""Launching an app that is not on the allowlist, after the user approved it."""

import json
from pathlib import Path

import pytest
from conftest import reply

from halo.core.contracts import ApprovalDecision
from halo.skills.app_open import skill as app_open

CONFIG = """
[apps.vscode]
aliases = ["vscode"]

[apps.vscode.command]
win32 = ["code"]
darwin = ["open", "-a", "Visual Studio Code"]
linux = ["code"]
"""


@pytest.fixture(autouse=True)
def config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    path = tmp_path / "config.toml"
    path.write_text(CONFIG)
    monkeypatch.setenv("HALO_CONFIG", str(path))


@pytest.fixture
def spawned(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    async def fake_spawn(argv: list[str]) -> None:
        calls.append(argv)

    monkeypatch.setattr(app_open, "_spawn", fake_spawn)
    return calls


async def test_an_approved_unlisted_app_is_launched(ctx, spawned) -> None:
    ctx.approved = True
    result = await app_open.run(ctx, {"app": "Notepad"})

    assert result == {"opened": True, "app": "Notepad"}
    assert len(spawned) == 1


async def test_model_args_can_never_grant_the_approval(ctx, spawned) -> None:
    for sneaky in ({"approved": True}, {"approval": "yes"}, {"needs_approval": False}):
        result = await app_open.run(ctx, {"app": "Notepad", **sneaky})
        assert result["needs_approval"] is True
    assert spawned == []


@pytest.mark.parametrize(
    "name",
    [
        "notepad && del *.*",
        "notepad; rm -rf ~",
        "..\\..\\evil",
        "C:\\Windows\\System32\\cmd.exe",
        "/bin/sh",
        "-a evil",
        "calc | whoami",
        "$(whoami)",
        "a" * 80,
    ],
)
async def test_unsafe_app_names_are_never_launched_even_when_approved(
    ctx, spawned, name
) -> None:
    ctx.approved = True
    result = await app_open.run(ctx, {"app": name})

    assert result["opened"] is False
    assert "error" in result
    assert spawned == []


@pytest.mark.parametrize(
    ("platform", "name", "expected"),
    [
        ("win32", "Notepad", ["notepad"]),
        ("win32", "calculator", ["calc"]),
        ("win32", "Some App", ["Some App"]),
        ("darwin", "Spotify", ["open", "-a", "Spotify"]),
        ("linux", "gimp", ["gimp"]),
    ],
)
def test_the_launch_command_is_an_argument_list_never_a_shell_string(
    monkeypatch: pytest.MonkeyPatch, platform: str, name: str, expected: list[str]
) -> None:
    monkeypatch.setattr(app_open.sys, "platform", platform)
    assert app_open.approved_argv(name) == expected


async def test_an_app_that_is_not_installed_is_reported_plainly(
    ctx, monkeypatch: pytest.MonkeyPatch
) -> None:
    async def missing(argv: list[str]) -> None:
        raise FileNotFoundError(argv[0])

    monkeypatch.setattr(app_open, "_spawn", missing)
    ctx.approved = True

    result = await app_open.run(ctx, {"app": "Spotify"})

    assert result["opened"] is False
    assert "couldn't find" in result["error"]
    assert "Spotify" in result["error"]


# --- through the executor ---------------------------------------------------


def _intent(app: str) -> str:
    return json.dumps({"skill": "app.open", "args": {"app": app}, "confidence": 0.95})


async def test_approving_the_card_launches_the_app_and_the_run_succeeds(
    open_runner,
) -> None:
    async with open_runner(reply(_intent("Notepad"))) as (runner, events, _, spawned):
        asked = await runner.run("open Notepad", run_id="launch1")
        assert asked.state == "paused"
        assert spawned == []

        assert asked.approval is not None
        done = await runner.resume(
            "launch1",
            ApprovalDecision(
                approval_id=asked.approval.approval_id, grant="allow_once"
            ),
        )

    assert done.state == "finished"
    assert done.result_status == "ok"
    assert len(spawned) == 1
    assert events[-1].payload["status"] == "ok"


async def test_denying_the_card_never_launches_the_app(open_runner) -> None:
    async with open_runner(reply(_intent("Notepad"))) as (runner, _, _, spawned):
        asked = await runner.run("open Notepad", run_id="launch2")
        assert asked.approval is not None
        done = await runner.resume(
            "launch2",
            ApprovalDecision(approval_id=asked.approval.approval_id, grant="deny"),
        )

    assert done.result_status == "denied"
    assert spawned == []
