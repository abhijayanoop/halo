"""Planning must not hide a broken configuration behind the bad-args fallback."""

from pathlib import Path

import pytest

from halo.core.contracts import Intent
from halo.core.planner import make_plan
from halo.skills.registry import SkillRegistry, default_skills_dir


async def test_a_broken_config_is_reported_not_swallowed(
    make_client, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    broken = tmp_path / "config.toml"
    broken.write_text("surprise = 1\n")
    monkeypatch.setenv("HALO_CONFIG", str(broken))
    client, _, _ = make_client()
    registry = SkillRegistry.load(default_skills_dir())
    intent = Intent(skill="app.open", args={"app": "vscode"}, confidence=0.9)

    with pytest.raises(ValueError, match="surprise|extra"):
        await make_plan(client, registry, "r", "open vscode", intent)


async def test_invalid_args_are_still_tolerated(make_client) -> None:
    client, _, _ = make_client()
    registry = SkillRegistry.load(default_skills_dir())
    intent = Intent(skill="app.open", args={}, confidence=0.9)
    plan = await make_plan(client, registry, "r", "open", intent)
    assert plan.steps[0].risk == "low"
