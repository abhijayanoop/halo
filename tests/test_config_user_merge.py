"""~/.halo/config.toml changes what it mentions and keeps the packaged defaults for the rest."""

from pathlib import Path

import pytest

from halo.config import load_config


@pytest.fixture
def home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.delenv("HALO_CONFIG", raising=False)
    monkeypatch.delenv("HALO_PROFILE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / ".halo").mkdir()
    return tmp_path


def _user_config(home: Path, text: str) -> None:
    (home / ".halo" / "config.toml").write_text(text, encoding="utf-8")


def test_a_user_file_with_only_a_vault_keeps_the_default_apps_and_models(
    home: Path,
) -> None:
    _user_config(home, '[vault]\npath = "D:/MyVault"\n')
    config = load_config()
    assert config.vault.path == Path("D:/MyVault")
    assert "vscode" in config.apps
    assert set(config.models) == {"nano", "super", "ultra", "omni"}
    assert config.api.key_env == "NEBIUS_API_KEY"
    assert "nvidia-api" in config.profiles


def test_a_section_the_user_writes_replaces_the_default_section(home: Path) -> None:
    _user_config(
        home, "[apps.baz]\naliases = []\n[apps.baz.command]\nwin32 = ['baz']\n"
    )
    assert list(load_config().apps) == ["baz"]


def test_the_user_can_pick_a_profile_and_still_get_the_packaged_profiles(
    home: Path,
) -> None:
    _user_config(home, 'profile = "nvidia-api"\n')
    config = load_config()
    assert config.profile == "nvidia-api"
    assert config.api.key_env == "NVIDIA_API_KEY"


def test_an_explicit_config_file_still_stands_alone(
    home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "only-apps.toml"
    path.write_text("[apps.bar]\naliases = []\n[apps.bar.command]\nwin32 = ['bar']\n")
    monkeypatch.setenv("HALO_CONFIG", str(path))
    _user_config(home, '[vault]\npath = "D:/MyVault"\n')
    config = load_config()
    assert list(config.apps) == ["bar"]
    assert config.vault.path is None
    assert config.models == {}
