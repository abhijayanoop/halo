"""Loads skills from `<skills_dir>/<name>/{SKILL.md,skill.py}`.

A folder is named after its skill with dots as underscores (`app.open` lives in
`app_open/`). Folders without a SKILL.md are ignored.
"""

import importlib.util
import inspect
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import get_args

import frontmatter
from pydantic import ValidationError

from halo.core.contracts import SkillManifest, SkillName


class SkillLoadError(Exception):
    """A skill folder is malformed."""


@dataclass(frozen=True)
class LoadedSkill:
    manifest: SkillManifest
    module: ModuleType


def default_skills_dir() -> Path:
    return Path(__file__).parent


def _load_skill(folder: Path) -> LoadedSkill:
    try:
        meta = frontmatter.load(str(folder / "SKILL.md")).metadata
        manifest = SkillManifest.model_validate(meta)
    except (ValidationError, OSError, ValueError) as exc:
        raise SkillLoadError(f"invalid SKILL.md in {folder.name}: {exc}") from exc

    if manifest.name not in get_args(SkillName):
        raise SkillLoadError(
            f"{folder.name}: '{manifest.name}' is not a known skill name"
        )
    if manifest.name.replace(".", "_") != folder.name:
        raise SkillLoadError(
            f"skill '{manifest.name}' must live in folder '{manifest.name.replace('.', '_')}'"
            f", not '{folder.name}'"
        )

    code = folder / "skill.py"
    if not code.is_file():
        raise SkillLoadError(f"skill '{manifest.name}' has no skill.py")
    spec = importlib.util.spec_from_file_location(f"halo_skill_{folder.name}", code)
    if spec is None or spec.loader is None:
        raise SkillLoadError(f"cannot import {code}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    if not inspect.iscoroutinefunction(getattr(module, "run", None)):
        raise SkillLoadError(
            f"skill '{manifest.name}' must define 'async def run(ctx, args)'"
        )
    return LoadedSkill(manifest, module)


class SkillRegistry:
    def __init__(self, skills: dict[str, LoadedSkill]) -> None:
        self._skills = skills

    @classmethod
    def load(cls, skills_dir: Path) -> "SkillRegistry":
        skills: dict[str, LoadedSkill] = {}
        for folder in sorted(skills_dir.iterdir()):
            if folder.is_dir() and (folder / "SKILL.md").is_file():
                loaded = _load_skill(folder)
                skills[loaded.manifest.name] = loaded
        return cls(skills)

    def names(self) -> list[str]:
        return sorted(self._skills)

    def get(self, name: str) -> LoadedSkill:
        return self._skills[name]

    def __contains__(self, name: object) -> bool:
        return name in self._skills
