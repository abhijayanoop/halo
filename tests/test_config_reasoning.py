"""Nemotron thinks by default, which made a Nano call take about 4 s on the dev
profile; with thinking off it took under 1 s and the router still scored 20/20
(measured live, dev numbers only)."""

import pytest

from halo.config import load_config


@pytest.fixture(autouse=True)
def isolated_env(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HALO_CONFIG", raising=False)
    monkeypatch.delenv("HALO_PROFILE", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))


def test_the_dev_profile_turns_thinking_off() -> None:
    profile = load_config().profiles["nvidia-api"]
    assert profile.api.extra_body == {
        "chat_template_kwargs": {"enable_thinking": False}
    }


def test_selecting_the_dev_profile_sends_it_with_every_request(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("HALO_PROFILE", "nvidia-api")
    assert (
        load_config().api.extra_body["chat_template_kwargs"]["enable_thinking"] is False
    )


def test_the_token_factory_profile_is_not_changed_by_a_dev_measurement() -> None:
    assert load_config().api.extra_body == {}
