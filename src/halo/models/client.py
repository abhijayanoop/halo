"""The only door to a model.

Every LLM call in Halo goes through `ModelClient.call`, to Nemotron on Token
Factory. It parses structured output into Pydantic models (one retry with the
validation error attached), retries transient failures with exponential
backoff, prices every call in rupees, emits `cost.updated`, and refuses to send
anything from a `privacy: local` note.
"""

import asyncio
import json
import logging
import os
import re
import time
from collections import defaultdict
from collections.abc import Awaitable, Callable, Iterable, Sequence
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ValidationError

from halo.config import HaloConfig, ModelSpec, ModelTier
from halo.core.contracts import HaloEvent, MemoryItem
from halo.core.events import make_event
from halo.models.transport import (
    OpenAITransport,
    TransientModelError,
    Transport,
    TransportResponse,
)

logger = logging.getLogger(__name__)

_FENCE = re.compile(r"^```(?:json)?\s*(.*?)\s*```$", re.DOTALL)


class ConfigError(Exception):
    """Model access is not configured (missing key, URL or model id)."""


class PrivacyViolationError(Exception):
    """Text from a `privacy: local` note was about to go into a cloud prompt."""


class ModelValidationError(Exception):
    """The model's output did not match the requested schema, even after a retry."""


class ModelUnavailableError(Exception):
    """The model could not be reached after retrying."""


@dataclass(frozen=True)
class Usage:
    prompt_tokens: int
    completion_tokens: int


@dataclass(frozen=True)
class ToolCall:
    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class CallResult[T]:
    tier: ModelTier
    model_id: str
    text: str
    parsed: T | None
    tool_calls: list[ToolCall]
    usage: Usage
    cost_inr: Decimal
    latency_ms: float
    cost_known: bool = True


def _money(value: Decimal) -> str:
    return format(value.normalize(), "f")


_SHINGLE_WORDS = 4
_MIN_WHOLE_NOTE_CHARS = 10


def _words(text: str) -> str:
    """Lower-case, with every run of punctuation or whitespace collapsed to one
    space, so case, line breaks and spacing cannot hide a copied passage."""
    return " ".join(re.sub(r"\W+", " ", text.casefold()).split())


def _protected_chunks(note: str) -> set[str]:
    """What must not appear in a cloud prompt: every run of four consecutive words
    of the note (so an excerpt or a single copied line is caught), or the whole
    note if it is shorter than that but not trivially short."""
    words = _words(note).split()
    if len(words) >= _SHINGLE_WORDS:
        return {
            " ".join(words[i : i + _SHINGLE_WORDS])
            for i in range(len(words) - _SHINGLE_WORDS + 1)
        }
    whole = " ".join(words)
    return {whole} if len(whole) >= _MIN_WHOLE_NOTE_CHARS else set()


def _message_text(message: dict[str, Any]) -> str:
    content = message.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            part["text"]
            for part in content
            if isinstance(part, dict) and "text" in part
        )
    return ""


class ModelClient:
    def __init__(
        self,
        config: HaloConfig,
        transport: Transport,
        *,
        emit: Callable[[HaloEvent], None] | None = None,
        local_texts: Callable[[], Iterable[str]] | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        max_retries: int = 3,
        backoff_base: float = 0.5,
    ) -> None:
        self._config = config
        self._transport = transport
        self._emit = emit
        self._local_texts = local_texts
        self._sleep = sleep
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._run_costs: defaultdict[str, Decimal] = defaultdict(Decimal)

    def run_cost(self, run_id: str) -> Decimal:
        return self._run_costs.get(run_id, Decimal(0))

    async def call[T: BaseModel](
        self,
        tier: ModelTier,
        messages: Sequence[dict[str, Any]],
        *,
        schema: type[T] | None = None,
        tools: list[dict[str, Any]] | None = None,
        run_id: str | None = None,
        memory: Sequence[MemoryItem] = (),
        note: dict[str, Any] | None = None,
    ) -> CallResult[T]:
        spec = self._spec(tier)
        self._check_privacy(messages, memory)

        json_schema = (
            {"name": schema.__name__, "schema": schema.model_json_schema()}
            if schema
            else None
        )
        convo = [dict(m) for m in messages]
        prompt_tokens = completion_tokens = 0
        sent = False
        text = ""
        parsed: T | None = None
        tool_calls: list[ToolCall] = []
        started = time.perf_counter()
        try:
            for attempt in range(2 if schema else 1):
                response = await self._send(spec.id, convo, json_schema, tools)
                sent = True
                prompt_tokens += response.prompt_tokens
                completion_tokens += response.completion_tokens
                tool_calls = self._parse_tool_calls(response)
                text = response.content or ""
                if schema is None:
                    parsed = None
                    break
                try:
                    parsed = self._parse(schema, text)
                    break
                except (ValidationError, ValueError) as exc:
                    if attempt == 1:
                        raise ModelValidationError(
                            f"{tier} output did not match {schema.__name__}: {exc}"
                        ) from exc
                    logger.info(
                        "%s output failed %s validation; retrying",
                        tier,
                        schema.__name__,
                    )
                    convo += [
                        {"role": "assistant", "content": text},
                        {
                            "role": "user",
                            "content": (
                                f"Your previous reply was invalid: {self._describe(exc)}. "
                                "Reply again with only valid JSON matching the schema."
                            ),
                        },
                    ]
        finally:
            latency_ms = (time.perf_counter() - started) * 1000
            usage = Usage(prompt_tokens, completion_tokens)
            cost_inr, cost_known = self._price(tier, spec, usage)
            if sent:
                self._record_cost(
                    tier, spec, usage, cost_inr, cost_known, latency_ms, run_id, note
                )

        return CallResult(
            tier=tier,
            model_id=spec.id,
            text=text,
            parsed=parsed,
            tool_calls=tool_calls,
            usage=usage,
            cost_inr=cost_inr,
            latency_ms=latency_ms,
            cost_known=cost_known,
        )

    # -- internals ---------------------------------------------------------

    def _spec(self, tier: ModelTier) -> ModelSpec:
        spec = self._config.models.get(tier)
        if spec is None or spec.id.startswith("UNSET"):
            raise ConfigError(f"model id for tier '{tier}' is not configured")
        return spec

    def _check_privacy(
        self, messages: Sequence[dict[str, Any]], memory: Sequence[MemoryItem]
    ) -> None:
        if any(item.privacy == "local" for item in memory):
            raise PrivacyViolationError(
                "a memory item from a privacy: local note is in the prompt"
            )
        if self._local_texts is None:
            return
        padded = f" {_words('\n'.join(_message_text(m) for m in messages))} "
        for text in self._local_texts():
            if any(f" {chunk} " in padded for chunk in _protected_chunks(text)):
                raise PrivacyViolationError(
                    "text from a privacy: local note is in the prompt"
                )

    async def _send(
        self,
        model_id: str,
        messages: list[dict[str, Any]],
        json_schema: dict[str, Any] | None,
        tools: list[dict[str, Any]] | None,
    ) -> TransportResponse:
        for attempt in range(self._max_retries + 1):
            try:
                return await self._transport.chat(
                    model_id=model_id,
                    messages=messages,
                    json_schema=json_schema,
                    tools=tools,
                )
            except TransientModelError as exc:
                if attempt == self._max_retries:
                    raise ModelUnavailableError(
                        f"model unavailable after {attempt + 1} attempts: {exc}"
                    ) from exc
                delay = self._backoff_base * 2**attempt
                logger.warning(
                    "transient model error (%s); retrying in %.1fs", exc, delay
                )
                await self._sleep(delay)
        raise AssertionError("unreachable")

    @staticmethod
    def _parse[T: BaseModel](schema: type[T], text: str) -> T:
        stripped = text.strip()
        if fenced := _FENCE.match(stripped):
            stripped = fenced.group(1)
        return schema.model_validate_json(stripped)

    @staticmethod
    def _parse_tool_calls(response: TransportResponse) -> list[ToolCall]:
        calls: list[ToolCall] = []
        for raw in response.tool_calls:
            try:
                arguments = json.loads(raw.arguments or "{}")
            except json.JSONDecodeError as exc:
                raise ModelValidationError(
                    f"tool call '{raw.name}' has malformed arguments"
                ) from exc
            if not isinstance(arguments, dict):
                raise ModelValidationError(
                    f"tool call '{raw.name}' arguments are not an object"
                )
            calls.append(ToolCall(raw.id, raw.name, arguments))
        return calls

    @staticmethod
    def _describe(exc: Exception) -> str:
        if isinstance(exc, ValidationError):
            return "; ".join(
                f"{'.'.join(str(p) for p in err['loc']) or 'output'}: {err['msg']}"
                for err in exc.errors()
            )
        return str(exc)

    def _price(
        self, tier: ModelTier, spec: ModelSpec, usage: Usage
    ) -> tuple[Decimal, bool]:
        if spec.usd_per_m_input is None or spec.usd_per_m_output is None:
            logger.warning("no price configured for %s; its cost is not counted", tier)
            return Decimal(0), False
        usd = (
            spec.usd_per_m_input * usage.prompt_tokens
            + spec.usd_per_m_output * usage.completion_tokens
        ) / Decimal(1_000_000)
        return usd * self._config.usd_to_inr, True

    def _record_cost(
        self,
        tier: ModelTier,
        spec: ModelSpec,
        usage: Usage,
        cost_inr: Decimal,
        cost_known: bool,
        latency_ms: float,
        run_id: str | None,
        note: dict[str, Any] | None,
    ) -> None:
        if run_id is None:
            return
        self._run_costs[run_id] += cost_inr
        if self._emit is None:
            return
        payload: dict[str, Any] = {
            "model": tier,
            "model_id": spec.id,
            "prompt_tokens": usage.prompt_tokens,
            "completion_tokens": usage.completion_tokens,
            "cost_inr": _money(cost_inr),
            "run_total_inr": _money(self._run_costs[run_id]),
            "cost_known": cost_known,
            "latency_ms": round(latency_ms, 1),
            **(note or {}),
        }
        self._emit(
            make_event(
                run_id, "cost.updated", f"{tier.capitalize()} call", payload=payload
            )
        )


def build_client(
    config: HaloConfig,
    *,
    emit: Callable[[HaloEvent], None] | None = None,
    local_texts: Callable[[], Iterable[str]] | None = None,
) -> ModelClient:
    """The real client: key from the environment (entry points load .env first), endpoint from config."""
    api_key = os.environ.get(config.api.key_env)
    if not api_key:
        raise ConfigError(
            f"set {config.api.key_env} in .env to call the model API "
            f"(profile: {config.profile or 'none'})"
        )
    if not config.api.base_url or config.api.base_url.startswith("UNSET"):
        raise ConfigError("api.base_url is not configured")
    transport = OpenAITransport(
        base_url=config.api.base_url,
        api_key=api_key,
        structured_mode=config.api.structured_mode,
        extra_body=config.api.extra_body,
    )
    return ModelClient(config, transport, emit=emit, local_texts=local_texts)


__all__ = [
    "CallResult",
    "ConfigError",
    "ModelClient",
    "ModelUnavailableError",
    "ModelValidationError",
    "PrivacyViolationError",
    "ToolCall",
    "Usage",
    "build_client",
]
