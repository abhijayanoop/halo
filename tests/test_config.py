from pathlib import Path

import pytest

from halo.config import load_config


def test_packaged_defaults_allowlist_vscode(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HALO_CONFIG", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    assert "vscode" in load_config().apps


def test_explicit_path_wins(tmp_path: Path) -> None:
    path = tmp_path / "c.toml"
    path.write_text(
        '[apps.foo]\naliases = ["f"]\n[apps.foo.command]\nwin32 = ["foo"]\n'
    )
    assert list(load_config(path).apps) == ["foo"]


def test_halo_config_env_var_selects_the_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "c.toml"
    path.write_text("[apps.bar]\naliases = []\n[apps.bar.command]\nwin32 = ['bar']\n")
    monkeypatch.setenv("HALO_CONFIG", str(path))
    assert list(load_config().apps) == ["bar"]


def test_user_config_in_halo_home_overrides_packaged_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.delenv("HALO_CONFIG", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    (tmp_path / ".halo").mkdir()
    (tmp_path / ".halo" / "config.toml").write_text(
        "[apps.baz]\naliases = []\n[apps.baz.command]\nwin32 = ['baz']\n"
    )
    assert list(load_config().apps) == ["baz"]


def test_unknown_top_level_keys_are_rejected(tmp_path: Path) -> None:
    path = tmp_path / "c.toml"
    path.write_text("surprise = 1\n")
    with pytest.raises(ValueError):
        load_config(path)
