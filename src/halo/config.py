"""Halo's configuration, loaded from a TOML file.

Lookup order: an explicit path, then $HALO_CONFIG, then ~/.halo/config.toml,
then the defaults packaged with Halo.
"""

import os
import tomllib
from importlib import resources
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEntry(BaseModel):
    """One allowlisted app: the names it answers to, and the launch command per
    platform (keyed by `sys.platform`: win32, darwin, linux)."""

    model_config = ConfigDict(extra="forbid")

    aliases: list[str] = Field(default_factory=list)
    command: dict[str, list[str]]


class HaloConfig(BaseSettings):
    model_config = SettingsConfigDict(extra="forbid", env_prefix="HALO_")

    apps: dict[str, AppEntry] = Field(default_factory=dict)


def user_config_path() -> Path:
    return Path.home() / ".halo" / "config.toml"


def load_config(path: Path | None = None) -> HaloConfig:
    if path is None and (env_path := os.environ.get("HALO_CONFIG")):
        path = Path(env_path)
    if path is None and user_config_path().is_file():
        path = user_config_path()
    if path is not None:
        text = path.read_text(encoding="utf-8")
    else:
        text = (resources.files("halo") / "config.default.toml").read_text(
            encoding="utf-8"
        )
    return HaloConfig(**tomllib.loads(text))
