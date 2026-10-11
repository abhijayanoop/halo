import sys
from pathlib import Path

import pytest

from halo.skills.app_open import skill as app_open

CONFIG = """
[apps.vscode]
aliases = ["vs code", "vscode", "visual studio code"]

[apps.vscode.command]
win32 = ["code"]
darwin = ["open", "-a", "Visual Studio Code"]
linux = ["code"]
"""


@pytest.fixture(autouse=True)
def config_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "config.toml"
    path.write_text(CONFIG)
    monkeypatch.setenv("HALO_CONFIG", str(path))
    return path


@pytest.fixture
def spawned(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    calls: list[list[str]] = []

    async def fake_spawn(argv: list[str]) -> None:
        calls.append(argv)

    monkeypatch.setattr(app_open, "_spawn", fake_spawn)
    return calls


async def test_allowlisted_app_opens_by_alias(ctx, spawned) -> None:
    result = await app_open.run(ctx, {"app": "VS Code"})
    assert result == {"opened": True, "app": "vscode"}
    assert len(spawned) == 1
    assert spawned[0][0] in {"code", "open"}


async def test_alias_matching_ignores_case_and_whitespace(ctx, spawned) -> None:
    result = await app_open.run(ctx, {"app": "  Visual STUDIO Code "})
    assert result["opened"] is True


async def test_unlisted_app_is_not_launched_and_asks_for_approval(ctx, spawned) -> None:
    result = await app_open.run(ctx, {"app": "Spotify"})
    assert result == {"opened": False, "app": "Spotify", "needs_approval": True}
    assert spawned == []


@pytest.mark.parametrize("args", [{}, {"app": ""}, {"app": "   "}, {"app": 7}])
async def test_missing_or_blank_app_raises(ctx, spawned, args) -> None:
    with pytest.raises(ValueError, match="app"):
        await app_open.run(ctx, args)
    assert spawned == []


async def test_model_supplied_flags_cannot_bypass_the_allowlist(ctx, spawned) -> None:
    result = await app_open.run(ctx, {"app": "Spotify", "approved": True})
    assert result["opened"] is False
    assert spawned == []


async def test_emits_tool_events_stamped_with_the_run_id(ctx, spawned) -> None:
    await app_open.run(ctx, {"app": "vscode"})
    assert [e.type for e in ctx.events] == ["tool.called", "tool.result"]
    assert {e.run_id for e in ctx.events} == {ctx.run_id}


async def test_launch_failure_is_reported_not_raised(ctx, monkeypatch) -> None:
    async def failing_spawn(argv: list[str]) -> None:
        raise FileNotFoundError(argv[0])

    monkeypatch.setattr(app_open, "_spawn", failing_spawn)
    result = await app_open.run(ctx, {"app": "vscode"})
    assert result["opened"] is False
    assert "error" in result
    assert ctx.events[-1].type == "tool.result"


async def test_app_without_a_command_for_this_platform_is_reported(
    ctx, spawned, config_file: Path
) -> None:
    config_file.write_text(
        '[apps.vscode]\naliases = ["vscode"]\n[apps.vscode.command]\nplan9 = ["code"]\n'
    )
    result = await app_open.run(ctx, {"app": "vscode"})
    assert result["opened"] is False
    assert sys.platform in result["error"]
    assert spawned == []


def test_risk_is_low_for_allowlisted_and_medium_otherwise() -> None:
    assert app_open.assess_risk({"app": "vs code"}) == "low"
    assert app_open.assess_risk({"app": "Spotify"}) == "medium"


async def test_real_spawn_of_a_missing_binary_raises_file_not_found() -> None:
    with pytest.raises(FileNotFoundError):
        await app_open._spawn(["definitely-not-a-real-binary-xyz"])
