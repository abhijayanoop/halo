"""The real transport, driven against an in-process fake HTTP server: no network."""

import json

import httpx2 as httpx
import pytest

from halo.models.transport import (
    ModelRequestError,
    OpenAITransport,
    TransientModelError,
)

BODY = {
    "id": "x",
    "object": "chat.completion",
    "created": 0,
    "model": "m",
    "choices": [
        {
            "index": 0,
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": "hi there"},
        }
    ],
    "usage": {"prompt_tokens": 11, "completion_tokens": 3, "total_tokens": 14},
}


def _transport(handler) -> OpenAITransport:
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    return OpenAITransport(
        base_url="https://example.test/v1/", api_key="secret-key", http_client=http
    )


async def test_request_shape_and_response_mapping() -> None:
    seen: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json=BODY)

    schema = {"name": "Intent", "schema": {"type": "object"}}
    out = await _transport(handler).chat(
        model_id="the-model",
        messages=[{"role": "user", "content": "hello"}],
        json_schema=schema,
    )
    assert seen["auth"] == "Bearer secret-key"
    assert seen["path"].endswith("/chat/completions")
    assert seen["body"]["model"] == "the-model"
    assert seen["body"]["response_format"]["type"] == "json_schema"
    assert seen["body"]["response_format"]["json_schema"]["name"] == "Intent"
    assert (out.content, out.prompt_tokens, out.completion_tokens) == (
        "hi there",
        11,
        3,
    )


async def test_tool_calls_are_mapped() -> None:
    body = json.loads(json.dumps(BODY))
    body["choices"][0]["message"] = {
        "role": "assistant",
        "content": None,
        "tool_calls": [
            {
                "id": "c1",
                "type": "function",
                "function": {"name": "open_app", "arguments": '{"app": "code"}'},
            }
        ],
    }
    out = await _transport(lambda r: httpx.Response(200, json=body)).chat(
        model_id="m", messages=[], tools=[{"type": "function"}]
    )
    assert [(t.id, t.name, t.arguments) for t in out.tool_calls] == [
        ("c1", "open_app", '{"app": "code"}')
    ]


@pytest.mark.parametrize("status", [429, 500, 503])
async def test_rate_limits_and_server_errors_are_transient(status: int) -> None:
    transport = _transport(
        lambda r: httpx.Response(status, json={"error": {"message": "x"}})
    )
    with pytest.raises(TransientModelError):
        await transport.chat(model_id="m", messages=[])


async def test_connection_failures_are_transient() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    with pytest.raises(TransientModelError):
        await _transport(handler).chat(model_id="m", messages=[])


@pytest.mark.parametrize("status", [400, 401, 404])
async def test_client_errors_are_permanent_and_never_leak_the_key(status: int) -> None:
    transport = _transport(
        lambda r: httpx.Response(status, json={"error": {"message": "bad"}})
    )
    with pytest.raises(ModelRequestError) as info:
        await transport.chat(model_id="m", messages=[])
    assert "secret-key" not in str(info.value)


async def test_the_sdk_does_not_retry_on_its_own() -> None:
    calls = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        return httpx.Response(503, json={"error": {"message": "x"}})

    with pytest.raises(TransientModelError):
        await _transport(handler).chat(model_id="m", messages=[])
    assert calls == 1
