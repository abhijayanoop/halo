import os
from pathlib import Path

import pytest

from halo.config import HaloConfig, ModelSpec, load_config, load_env


@pytest.fixture(autouse=True)
def isolated_env(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HALO_CONFIG", raising=False)
    monkeypatch.delenv("HALO_PROFILE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))


def test_the_packaged_default_is_the_token_factory_profile() -> None:
    config = load_config()
    assert config.profile == "token-factory"
    assert config.api.key_env == "NEBIUS_API_KEY"
    assert set(config.models) == {"nano", "super", "ultra", "omni"}


def test_the_nvidia_api_dev_profile_is_packaged() -> None:
    profile = load_config().profiles["nvidia-api"]
    assert profile.api.base_url == "https://integrate.api.nvidia.com/v1"
    assert profile.api.key_env == "NVIDIA_API_KEY"
    assert set(profile.models) == {"nano", "super", "ultra", "omni"}


def test_halo_profile_env_var_selects_a_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HALO_PROFILE", "nvidia-api")
    config = load_config()
    assert config.profile == "nvidia-api"
    assert config.api.key_env == "NVIDIA_API_KEY"
    assert config.api.base_url == "https://integrate.api.nvidia.com/v1"


def test_env_var_beats_the_profile_named_in_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "c.toml"
    path.write_text(
        'profile = "a"\n'
        '[profiles.a.api]\nbase_url = "https://a.test/v1"\nkey_env = "A_KEY"\n'
        '[profiles.a.models.nano]\nid = "a-nano"\n'
        '[profiles.b.api]\nbase_url = "https://b.test/v1"\nkey_env = "B_KEY"\n'
        '[profiles.b.models.nano]\nid = "b-nano"\n'
    )
    assert load_config(path).models["nano"].id == "a-nano"
    monkeypatch.setenv("HALO_PROFILE", "b")
    assert load_config(path).models["nano"].id == "b-nano"


def test_an_unknown_profile_is_a_clear_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HALO_PROFILE", "nope")
    with pytest.raises(ValueError, match="nope"):
        load_config()


def test_without_a_profile_explicit_api_and_models_are_left_alone() -> None:
    config = HaloConfig(models={"nano": ModelSpec(id="x")})
    assert config.profile == ""
    assert config.models["nano"].id == "x"


def test_structured_mode_and_extra_body_have_safe_defaults() -> None:
    api = load_config().api
    assert api.structured_mode == "json_schema"
    assert api.extra_body == {}


def test_an_invalid_structured_mode_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "c.toml"
    path.write_text('[api]\nstructured_mode = "telepathy"\n')
    with pytest.raises(ValueError):
        load_config(path)


def test_load_env_reads_dotenv_from_the_working_directory_without_overriding(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    work = tmp_path / "work"
    work.mkdir()
    (work / ".env").write_text(
        "HALO_TEST_FROM_DOTENV=file\nHALO_TEST_ALREADY_SET=file\n"
    )
    monkeypatch.chdir(work)
    monkeypatch.delenv("HALO_TEST_FROM_DOTENV", raising=False)
    monkeypatch.setenv("HALO_TEST_ALREADY_SET", "shell")
    try:
        load_env()
        assert os.environ["HALO_TEST_FROM_DOTENV"] == "file"
        assert os.environ["HALO_TEST_ALREADY_SET"] == "shell"
    finally:
        os.environ.pop("HALO_TEST_FROM_DOTENV", None)
