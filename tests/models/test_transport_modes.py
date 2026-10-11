"""Structured-output modes, reasoning-output cleanup and extra request fields,
checked against an in-process fake HTTP server: no network."""

import json

import httpx2 as httpx
import pytest

from halo.models.transport import OpenAITransport

SCHEMA = {
    "name": "Intent",
    "schema": {"type": "object", "properties": {"skill": {"type": "string"}}},
}


def _body(content="{}", **message_extra) -> dict:
    return {
        "id": "x",
        "object": "chat.completion",
        "created": 0,
        "model": "m",
        "choices": [
            {
                "index": 0,
                "finish_reason": "stop",
                "message": {"role": "assistant", "content": content, **message_extra},
            }
        ],
        "usage": {"prompt_tokens": 1, "completion_tokens": 1, "total_tokens": 2},
    }


def _transport(seen: dict, response: dict | None = None, **kwargs) -> OpenAITransport:
    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=response or _body())

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OpenAITransport(
        base_url="https://example.test/v1/", api_key="k", http_client=http, **kwargs
    )


MESSAGES = [{"role": "user", "content": "open vs code"}]


async def test_json_object_mode_asks_for_json_and_puts_the_schema_in_the_prompt() -> (
    None
):
    seen: dict = {}
    await _transport(seen, structured_mode="json_object").chat(
        model_id="m", messages=MESSAGES, json_schema=SCHEMA
    )
    body = seen["body"]
    assert body["response_format"] == {"type": "json_object"}
    assert body["messages"][0]["role"] == "system"
    assert '"skill"' in body["messages"][0]["content"]
    assert body["messages"][-1] == MESSAGES[0]


async def test_prompt_mode_sends_no_response_format_only_the_instruction() -> None:
    seen: dict = {}
    await _transport(seen, structured_mode="prompt").chat(
        model_id="m", messages=MESSAGES, json_schema=SCHEMA
    )
    assert "response_format" not in seen["body"]
    assert "JSON" in seen["body"]["messages"][0]["content"]


async def test_json_schema_mode_does_not_touch_the_messages() -> None:
    seen: dict = {}
    await _transport(seen).chat(model_id="m", messages=MESSAGES, json_schema=SCHEMA)
    assert seen["body"]["messages"] == MESSAGES
    assert seen["body"]["response_format"]["type"] == "json_schema"


async def test_the_callers_messages_are_never_mutated() -> None:
    messages = [{"role": "user", "content": "hi"}]
    await _transport({}, structured_mode="prompt").chat(
        model_id="m", messages=messages, json_schema=SCHEMA
    )
    assert messages == [{"role": "user", "content": "hi"}]


async def test_plain_calls_ignore_the_structured_mode() -> None:
    seen: dict = {}
    await _transport(seen, structured_mode="json_object").chat(
        model_id="m", messages=MESSAGES
    )
    assert "response_format" not in seen["body"]
    assert seen["body"]["messages"] == MESSAGES


@pytest.mark.parametrize(
    ("raw", "cleaned"),
    [
        ('<think>hmm, which skill?</think>{"skill": "chat"}', '{"skill": "chat"}'),
        ('<think>line one\nline two</think>\n\n{"a": 1}', '{"a": 1}'),
        ("<think>ran out of tokens while thinking", ""),
        ('{"already": "clean"}', '{"already": "clean"}'),
    ],
)
async def test_reasoning_blocks_are_stripped_from_the_reply(
    raw: str, cleaned: str
) -> None:
    out = await _transport({}, _body(raw)).chat(model_id="m", messages=MESSAGES)
    assert out.content == cleaned


async def test_a_separate_reasoning_field_never_leaks_into_the_content() -> None:
    response = _body('{"ok": true}', reasoning_content="private chain of thought")
    out = await _transport({}, response).chat(model_id="m", messages=MESSAGES)
    assert out.content == '{"ok": true}'


async def test_extra_body_fields_are_sent_to_the_provider() -> None:
    seen: dict = {}
    extra = {"chat_template_kwargs": {"enable_thinking": False}}
    await _transport(seen, extra_body=extra).chat(model_id="m", messages=MESSAGES)
    assert seen["body"]["chat_template_kwargs"] == {"enable_thinking": False}


def test_build_client_passes_the_profile_settings_to_the_transport(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from halo.config import ApiConfig, HaloConfig, ModelSpec
    from halo.models import client as client_module

    captured: dict = {}

    class RecordingTransport:
        def __init__(self, **kwargs) -> None:
            captured.update(kwargs)

    monkeypatch.setattr(client_module, "OpenAITransport", RecordingTransport)
    monkeypatch.setenv("HALO_TEST_KEY", "k")
    config = HaloConfig(
        api=ApiConfig(
            base_url="https://example.test/v1",
            key_env="HALO_TEST_KEY",
            structured_mode="json_object",
            extra_body={"x": 1},
        ),
        models={"nano": ModelSpec(id="n")},
    )
    client_module.build_client(config)
    assert captured["structured_mode"] == "json_object"
    assert captured["extra_body"] == {"x": 1}
    assert captured["base_url"] == "https://example.test/v1"
