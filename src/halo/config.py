"""Halo's configuration, loaded from a TOML file.

Lookup order: an explicit path, then $HALO_CONFIG, then ~/.halo/config.toml,
then the defaults packaged with Halo.
"""

import os
import tomllib
from decimal import Decimal
from importlib import resources
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class AppEntry(BaseModel):
    """One allowlisted app: the names it answers to, and the launch command per
    platform (keyed by `sys.platform`: win32, darwin, linux)."""

    model_config = ConfigDict(extra="forbid")

    aliases: list[str] = Field(default_factory=list)
    command: dict[str, list[str]]


ModelTier = Literal["nano", "super", "ultra", "omni"]


class ModelSpec(BaseModel):
    """One Nemotron model on Token Factory. Prices are USD per million tokens;
    leave them unset if unknown and costs are reported as not known."""

    model_config = ConfigDict(extra="forbid")

    id: str
    usd_per_m_input: Decimal | None = None
    usd_per_m_output: Decimal | None = None


class ApiConfig(BaseModel):
    """Where model calls go. The key itself is never in this file: it is read
    from the environment variable named by `key_env` (loaded from .env)."""

    model_config = ConfigDict(extra="forbid")

    base_url: str = ""
    key_env: str = "NEBIUS_API_KEY"


class HaloConfig(BaseSettings):
    model_config = SettingsConfigDict(extra="forbid", env_prefix="HALO_")

    apps: dict[str, AppEntry] = Field(default_factory=dict)
    api: ApiConfig = Field(default_factory=ApiConfig)
    models: dict[ModelTier, ModelSpec] = Field(default_factory=dict)
    usd_to_inr: Decimal = Decimal(85)


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
