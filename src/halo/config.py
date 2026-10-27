"""Halo's configuration, loaded from a TOML file.

Lookup order: an explicit path, then $HALO_CONFIG, then ~/.halo/config.toml,
then the defaults packaged with Halo.

Model access is described by *profiles*. The active profile (the `profile` key,
or $HALO_PROFILE, which wins) fills in `api` and `models`. The packaged default
is `token-factory`, the submission target; `nvidia-api` serves the same Nemotron
models from NVIDIA's hosted API for development.
"""

import os
import tomllib
from decimal import Decimal
from importlib import resources
from pathlib import Path
from typing import Any, Literal

from dotenv import find_dotenv, load_dotenv
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
)


class AppEntry(BaseModel):
    """One allowlisted app: the names it answers to, and the launch command per
    platform (keyed by `sys.platform`: win32, darwin, linux)."""

    model_config = ConfigDict(extra="forbid")

    aliases: list[str] = Field(default_factory=list)
    command: dict[str, list[str]]


ModelTier = Literal["nano", "super", "ultra", "omni"]
StructuredMode = Literal["json_schema", "json_object", "prompt"]


class ModelSpec(BaseModel):
    """One Nemotron model. Prices are USD per million tokens; leave them unset
    if unknown and costs are reported as not known."""

    model_config = ConfigDict(extra="forbid")

    id: str
    usd_per_m_input: Decimal | None = None
    usd_per_m_output: Decimal | None = None


class ApiConfig(BaseModel):
    """Where model calls go. The key itself is never in this file: it is read
    from the environment variable named by `key_env` (loaded from .env).

    `structured_mode` is how schema-constrained output is requested: the
    provider's `json_schema` response format, plain `json_object`, or just an
    instruction in the prompt. `extra_body` is merged into every request (for
    provider-specific switches such as turning reasoning off)."""

    model_config = ConfigDict(extra="forbid")

    base_url: str = ""
    key_env: str = "NEBIUS_API_KEY"
    structured_mode: StructuredMode = "json_schema"
    extra_body: dict[str, Any] = Field(default_factory=dict)


class VaultConfig(BaseModel):
    """Where the Obsidian vault lives. Unset means ~/HaloVault."""

    model_config = ConfigDict(extra="forbid")

    path: Path | None = None


class CodingConfig(BaseModel):
    """Limits for one coding work session (Claude Code in a worktree)."""

    model_config = ConfigDict(extra="forbid")

    max_cost_inr: Decimal = Decimal(40)
    max_turns: int = Field(default=30, ge=1)
    timeout_s: float = Field(default=900, gt=0)
    approval_timeout_s: float = Field(default=300, gt=0)


class ProfileConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    api: ApiConfig = Field(default_factory=ApiConfig)
    models: dict[ModelTier, ModelSpec] = Field(default_factory=dict)


class HaloConfig(BaseSettings):
    # Only what is passed in (from the TOML file) counts: the environment is
    # read explicitly in load_config, so a stray HALO_* variable cannot change
    # a config built in code or in a test.
    model_config = SettingsConfigDict(extra="forbid")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (init_settings,)

    apps: dict[str, AppEntry] = Field(default_factory=dict)
    profile: str = ""
    profiles: dict[str, ProfileConfig] = Field(default_factory=dict)
    api: ApiConfig = Field(default_factory=ApiConfig)
    models: dict[ModelTier, ModelSpec] = Field(default_factory=dict)
    vault: VaultConfig = Field(default_factory=VaultConfig)
    coding: CodingConfig = Field(default_factory=CodingConfig)
    usd_to_inr: Decimal = Decimal(85)

    @model_validator(mode="after")
    def _apply_profile(self) -> "HaloConfig":
        if self.profile:
            chosen = self.profiles.get(self.profile)
            if chosen is None:
                known = ", ".join(sorted(self.profiles)) or "none defined"
                raise ValueError(f"unknown profile '{self.profile}' (known: {known})")
            self.api = chosen.api
            self.models = dict(chosen.models)
        return self


def user_config_path() -> Path:
    return Path.home() / ".halo" / "config.toml"


def load_env() -> None:
    """Load `.env` (searching up from the working directory) into the process
    environment, without overriding variables that are already set."""
    load_dotenv(find_dotenv(usecwd=True))


def load_config(path: Path | None = None) -> HaloConfig:
    if path is None and (env_path := os.environ.get("HALO_CONFIG")):
        path = Path(env_path)
    defaults = (resources.files("halo") / "config.default.toml").read_text(
        encoding="utf-8"
    )
    if path is None and user_config_path().is_file():
        # The user's file changes the sections it writes and leaves the rest as
        # packaged: a file with only a [vault] must not drop the apps or models.
        data = {
            **tomllib.loads(defaults),
            **tomllib.loads(user_config_path().read_text(encoding="utf-8")),
        }
    elif path is not None:
        # An explicit file (or $HALO_CONFIG) stands alone.
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    else:
        data = tomllib.loads(defaults)
    if env_profile := os.environ.get("HALO_PROFILE"):
        data["profile"] = env_profile
    return HaloConfig(**data)
