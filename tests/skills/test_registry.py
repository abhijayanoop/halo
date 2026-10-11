from pathlib import Path

import pytest

from halo.skills.registry import SkillLoadError, SkillRegistry, default_skills_dir

SKILL_MD = """---
name: {name}
description: A test skill
tools: [t]
risk: low
---
When to use: tests.
"""

GOOD_PY = """
async def run(ctx, args):
    return {"echo": args}
"""


def _write_skill(root: Path, dirname: str, name: str, py: str = GOOD_PY) -> None:
    folder = root / dirname
    folder.mkdir(parents=True)
    (folder / "SKILL.md").write_text(SKILL_MD.format(name=name))
    if py:
        (folder / "skill.py").write_text(py)


def test_loads_a_skill_from_its_folder(tmp_path: Path) -> None:
    _write_skill(tmp_path, "chat", "chat")
    registry = SkillRegistry.load(tmp_path)
    assert registry.names() == ["chat"]
    assert "chat" in registry
    assert registry.get("chat").manifest.risk == "low"
    assert registry.get("chat").manifest.tools == ["t"]


async def test_loaded_skill_run_is_callable(tmp_path: Path, ctx) -> None:
    _write_skill(tmp_path, "chat", "chat")
    skill = SkillRegistry.load(tmp_path).get("chat")
    assert await skill.module.run(ctx, {"a": 1}) == {"echo": {"a": 1}}


def test_dotted_skill_name_maps_to_underscored_folder(tmp_path: Path) -> None:
    _write_skill(tmp_path, "app_open", "app.open")
    assert SkillRegistry.load(tmp_path).names() == ["app.open"]


def test_unknown_skill_lookup_raises(tmp_path: Path) -> None:
    with pytest.raises(KeyError):
        SkillRegistry.load(tmp_path).get("chat")


def test_folders_without_a_manifest_are_ignored(tmp_path: Path) -> None:
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "notes").mkdir()
    assert SkillRegistry.load(tmp_path).names() == []


def test_skill_name_must_be_a_known_skill_name(tmp_path: Path) -> None:
    _write_skill(tmp_path, "bogus", "bogus")
    with pytest.raises(SkillLoadError, match="bogus"):
        SkillRegistry.load(tmp_path)


def test_manifest_name_must_match_its_folder(tmp_path: Path) -> None:
    _write_skill(tmp_path, "expense_log", "chat")
    with pytest.raises(SkillLoadError, match="folder"):
        SkillRegistry.load(tmp_path)


def test_invalid_manifest_raises(tmp_path: Path) -> None:
    folder = tmp_path / "chat"
    folder.mkdir()
    (folder / "SKILL.md").write_text("---\nname: chat\nrisk: extreme\n---\n")
    (folder / "skill.py").write_text(GOOD_PY)
    with pytest.raises(SkillLoadError, match="chat"):
        SkillRegistry.load(tmp_path)


def test_missing_skill_py_raises(tmp_path: Path) -> None:
    _write_skill(tmp_path, "chat", "chat", py="")
    with pytest.raises(SkillLoadError, match="skill.py"):
        SkillRegistry.load(tmp_path)


def test_skill_without_async_run_raises(tmp_path: Path) -> None:
    _write_skill(tmp_path, "chat", "chat", py="def run(ctx, args):\n    return {}\n")
    with pytest.raises(SkillLoadError, match="async"):
        SkillRegistry.load(tmp_path)


def test_shipped_skills_all_load() -> None:
    registry = SkillRegistry.load(default_skills_dir())
    assert "app.open" in registry
