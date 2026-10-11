"""The wire to Token Factory: one chat-completions request in, one response out.

`Transport` is the seam the model client is tested through. `OpenAITransport` is
the real one, built on the `openai` SDK pointed at Token Factory's
OpenAI-compatible endpoint.
"""

from dataclasses import dataclass, field
from typing import Any, Protocol

import openai
from openai import AsyncOpenAI


class TransientModelError(Exception):
    """A failure worth retrying: rate limit, server error, timeout, no connection."""


class ModelRequestError(Exception):
    """A failure that retrying will not fix: bad request, bad key, unknown model."""


@dataclass(frozen=True)
class RawToolCall:
    id: str
    name: str
    arguments: str  # JSON text exactly as the model produced it


@dataclass(frozen=True)
class TransportResponse:
    content: str | None
    prompt_tokens: int
    completion_tokens: int
    tool_calls: list[RawToolCall] = field(default_factory=list)


class Transport(Protocol):
    async def chat(
        self,
        *,
        model_id: str,
        messages: list[dict[str, Any]],
        json_schema: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> TransportResponse: ...


class OpenAITransport:
    def __init__(
        self,
        *,
        base_url: str,
        api_key: str,
        http_client: Any = None,
        timeout: float = 60.0,
    ) -> None:
        # The SDK's own retries are off: ModelClient owns retry and backoff.
        self._client = AsyncOpenAI(
            base_url=base_url,
            api_key=api_key,
            max_retries=0,
            timeout=timeout,
            http_client=http_client,
        )

    async def chat(
        self,
        *,
        model_id: str,
        messages: list[dict[str, Any]],
        json_schema: dict[str, Any] | None = None,
        tools: list[dict[str, Any]] | None = None,
    ) -> TransportResponse:
        kwargs: dict[str, Any] = {"model": model_id, "messages": messages}
        if json_schema is not None:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": json_schema,
            }
        if tools:
            kwargs["tools"] = tools
        try:
            completion = await self._client.chat.completions.create(**kwargs)
        except (openai.APIConnectionError, openai.RateLimitError) as exc:
            raise TransientModelError(type(exc).__name__) from exc
        except openai.APIStatusError as exc:
            if exc.status_code >= 500 or exc.status_code == 408:
                raise TransientModelError(f"HTTP {exc.status_code}") from exc
            raise ModelRequestError(f"HTTP {exc.status_code}: {exc.message}") from exc

        message = completion.choices[0].message
        tool_calls = [
            RawToolCall(
                id=call.id, name=call.function.name, arguments=call.function.arguments
            )
            for call in (message.tool_calls or [])
            if call.type == "function"
        ]
        usage = completion.usage
        return TransportResponse(
            content=message.content,
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            tool_calls=tool_calls,
        )
