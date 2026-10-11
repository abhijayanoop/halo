import logging
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from conftest import reply

from halo.core.contracts import HaloEvent, Intent, MemoryItem
from halo.models.client import (
    ConfigError,
    ModelUnavailableError,
    ModelValidationError,
    PrivacyViolationError,
)
from halo.models.transport import RawToolCall, TransientModelError

MSGS = [{"role": "user", "content": "open vs code"}]
GOOD = '{"skill": "app.open", "args": {"app": "vs code"}, "confidence": 0.9}'


def _memory(privacy: str, fact: str = "a fact") -> MemoryItem:
    return MemoryItem(
        fact=fact,
        source="you",
        trust="high",
        created_at=datetime.now(UTC),
        block_id="^m-1",
        note_path="Profile.md",
        privacy=privacy,  # type: ignore[arg-type]
    )


async def test_plain_call_returns_text_usage_and_cost(make_client) -> None:
    client, transport, _ = make_client(reply("hello", 1000, 500))
    result = await client.call("nano", MSGS)
    assert result.text == "hello"
    assert result.parsed is None
    assert (result.usage.prompt_tokens, result.usage.completion_tokens) == (1000, 500)
    # (1000 * 0.10 + 500 * 0.40) / 1e6 USD, at 80 INR per USD
    assert result.cost_inr == Decimal("0.024")
    assert transport.calls[0]["model_id"] == "nano-id"
    assert result.latency_ms >= 0


async def test_schema_call_parses_into_the_pydantic_model(make_client) -> None:
    client, transport, _ = make_client(reply(GOOD))
    result = await client.call("nano", MSGS, schema=Intent)
    assert result.parsed == Intent(
        skill="app.open", args={"app": "vs code"}, confidence=0.9
    )
    sent = transport.calls[0]["json_schema"]
    assert sent["name"] == "Intent"
    assert sent["schema"] == Intent.model_json_schema()


async def test_json_wrapped_in_code_fences_still_parses(make_client) -> None:
    client, _, _ = make_client(reply(f"```json\n{GOOD}\n```"))
    result = await client.call("nano", MSGS, schema=Intent)
    assert result.parsed is not None
    assert result.parsed.skill == "app.open"


async def test_invalid_output_is_retried_once_with_the_error_attached(
    make_client,
) -> None:
    client, transport, _ = make_client(reply('{"skill": "nope"}'), reply(GOOD))
    result = await client.call("nano", MSGS, schema=Intent)
    assert result.parsed is not None
    assert len(transport.calls) == 2
    retry_messages = transport.calls[1]["messages"]
    assert retry_messages[-2] == {"role": "assistant", "content": '{"skill": "nope"}'}
    assert retry_messages[-1]["role"] == "user"
    assert "skill" in retry_messages[-1]["content"]
    # both attempts are paid for
    assert result.usage.prompt_tokens == 200
    assert result.cost_inr == Decimal("0.00288")


async def test_two_invalid_outputs_raise_validation_error(make_client) -> None:
    client, transport, _ = make_client(reply("not json"), reply("still not json"))
    with pytest.raises(ModelValidationError):
        await client.call("nano", MSGS, schema=Intent)
    assert len(transport.calls) == 2


async def test_transient_errors_back_off_exponentially_then_succeed(
    make_client,
) -> None:
    client, transport, sleeps = make_client(
        TransientModelError("429"), TransientModelError("503"), reply("ok")
    )
    result = await client.call("nano", MSGS)
    assert result.text == "ok"
    assert len(transport.calls) == 3
    assert sleeps == [0.5, 1.0]


async def test_gives_up_after_retries_are_exhausted(make_client) -> None:
    client, transport, sleeps = make_client(*[TransientModelError("503")] * 4)
    with pytest.raises(ModelUnavailableError):
        await client.call("nano", MSGS)
    assert len(transport.calls) == 4
    assert sleeps == [0.5, 1.0, 2.0]


async def test_tool_calls_are_returned_with_parsed_arguments(make_client) -> None:
    raw = RawToolCall(id="c1", name="open_app", arguments='{"app": "code"}')
    client, transport, _ = make_client(reply(None, tool_calls=[raw]))
    tools = [{"type": "function", "function": {"name": "open_app", "parameters": {}}}]
    result = await client.call("super", MSGS, tools=tools)
    assert [(t.id, t.name, t.arguments) for t in result.tool_calls] == [
        ("c1", "open_app", {"app": "code"})
    ]
    assert transport.calls[0]["tools"] == tools
    assert result.text == ""


async def test_malformed_tool_arguments_raise_validation_error(make_client) -> None:
    raw = RawToolCall(id="c1", name="open_app", arguments="{oops")
    client, _, _ = make_client(reply(None, tool_calls=[raw]))
    with pytest.raises(ModelValidationError):
        await client.call("super", MSGS, tools=[{"type": "function"}])


async def test_cost_updated_event_is_emitted_with_running_run_total(
    make_client,
) -> None:
    events: list[HaloEvent] = []
    client, _, _ = make_client(
        reply("a", 1000, 500), reply("b", 1000, 500), emit=events.append
    )
    await client.call("nano", MSGS, run_id="run1")
    await client.call("nano", MSGS, run_id="run1")
    assert [e.type for e in events] == ["cost.updated", "cost.updated"]
    assert events[0].run_id == "run1"
    assert events[0].payload["model"] == "nano"
    assert events[0].payload["cost_inr"] == "0.024"
    assert events[1].payload["run_total_inr"] == "0.048"
    assert client.run_cost("run1") == Decimal("0.048")
    assert client.run_cost("other") == Decimal(0)


async def test_no_event_without_a_run_id(make_client) -> None:
    events: list[HaloEvent] = []
    client, _, _ = make_client(reply("a"), emit=events.append)
    await client.call("nano", MSGS)
    assert events == []


async def test_note_is_merged_into_the_cost_event_payload(make_client) -> None:
    events: list[HaloEvent] = []
    client, _, _ = make_client(reply("a"), emit=events.append)
    await client.call("super", MSGS, run_id="r", note={"escalated_from": "nano"})
    assert events[0].payload["escalated_from"] == "nano"


async def test_local_memory_item_in_a_prompt_raises_before_any_network_call(
    make_client,
) -> None:
    client, transport, _ = make_client(reply("never sent"))
    with pytest.raises(PrivacyViolationError):
        await client.call("nano", MSGS, memory=[_memory("shared"), _memory("local")])
    assert transport.calls == []


async def test_shared_memory_items_are_allowed(make_client) -> None:
    client, transport, _ = make_client(reply("fine"))
    await client.call("nano", MSGS, memory=[_memory("shared")])
    assert len(transport.calls) == 1


async def test_text_of_a_local_note_in_any_message_raises(make_client) -> None:
    client, transport, _ = make_client(
        reply("never sent"), local_texts=lambda: ["Salary is 5 lakh a month"]
    )
    messages = [
        {"role": "user", "content": "context: SALARY IS 5 LAKH A MONTH, plan a trip"}
    ]
    with pytest.raises(PrivacyViolationError):
        await client.call("nano", messages)
    assert transport.calls == []


async def test_unconfigured_model_raises_config_error() -> None:
    from conftest import FakeTransport

    from halo.config import HaloConfig
    from halo.models.client import ModelClient

    client = ModelClient(HaloConfig(), FakeTransport())
    with pytest.raises(ConfigError, match="nano"):
        await client.call("nano", MSGS)


async def test_placeholder_model_ids_raise_config_error() -> None:
    from conftest import FakeTransport

    from halo.config import HaloConfig, ModelSpec
    from halo.models.client import ModelClient

    config = HaloConfig(models={"nano": ModelSpec(id="UNSET-nano")})
    with pytest.raises(ConfigError, match="nano"):
        await ModelClient(config, FakeTransport()).call("nano", MSGS)


async def test_missing_price_is_flagged_not_silently_free(make_client, caplog) -> None:
    from conftest import FakeTransport

    from halo.config import HaloConfig, ModelSpec
    from halo.models.client import ModelClient

    events: list[HaloEvent] = []
    config = HaloConfig(models={"nano": ModelSpec(id="n")})
    client = ModelClient(config, FakeTransport(reply("x")), emit=events.append)
    with caplog.at_level(logging.WARNING):
        await client.call("nano", MSGS, run_id="r")
    assert events[0].payload["cost_known"] is False
    assert "price" in caplog.text


def _real_config(base_url: str = "https://example.test/v1/"):
    from halo.config import ApiConfig, HaloConfig, ModelSpec

    return HaloConfig(
        api=ApiConfig(base_url=base_url, key_env="HALO_TEST_KEY"),
        models={"nano": ModelSpec(id="n")},
    )


def test_build_client_needs_the_api_key(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from halo.models.client import build_client

    monkeypatch.chdir(tmp_path)  # no .env here
    monkeypatch.delenv("HALO_TEST_KEY", raising=False)
    with pytest.raises(ConfigError, match="HALO_TEST_KEY"):
        build_client(_real_config())


def test_build_client_needs_a_real_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    from halo.models.client import build_client

    monkeypatch.setenv("HALO_TEST_KEY", "k")
    with pytest.raises(ConfigError, match="base_url"):
        build_client(_real_config("UNSET-copy-the-url"))


def test_build_client_succeeds_when_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    from halo.models.client import ModelClient, build_client

    monkeypatch.setenv("HALO_TEST_KEY", "k")
    assert isinstance(build_client(_real_config()), ModelClient)
