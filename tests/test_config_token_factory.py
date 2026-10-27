"""The submission profile points at Nebius Token Factory with its real model ids."""

import pytest

from halo.config import ModelTier, load_config


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HALO_CONFIG", raising=False)
    monkeypatch.delenv("HALO_PROFILE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))


def test_the_token_factory_profile_has_its_base_url() -> None:
    profile = load_config().profiles["token-factory"]
    assert profile.api.base_url == "https://api.tokenfactory.nebius.com/v1/"
    assert profile.api.key_env == "NEBIUS_API_KEY"


@pytest.mark.parametrize(
    ("tier", "model_id"),
    [
        ("nano", "nvidia/NVIDIA-Nemotron-3-Nano-30B-A3B"),
        ("super", "nvidia/nemotron-3-super-120b-a12b"),
        ("ultra", "nvidia/Nemotron-3-Ultra-550b-a55b"),
    ],
)
def test_nano_super_and_ultra_use_the_ids_listed_by_token_factory(
    tier: ModelTier, model_id: str
) -> None:
    assert load_config().profiles["token-factory"].models[tier].id == model_id


def test_only_models_that_are_nemotron_are_used() -> None:
    """The project rule: LLM calls go only to NVIDIA Nemotron."""
    for tier, spec in load_config().profiles["token-factory"].models.items():
        assert spec.id.startswith("UNSET") or "nemotron" in spec.id.lower(), tier
