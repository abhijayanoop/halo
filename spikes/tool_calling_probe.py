"""Spike: how reliably do Nano, Super and Ultra produce valid tool calls and valid JSON?

Question: is each tier's valid-output rate >= 90%, for tool calls and for
JSON-schema output? Decisions it feeds (PLAN Day 0):
  - Nano valid tool-call rate >= 90%  -> Nano does tool calls; else Nano only routes
    and Super does tool calls.
  - JSON-schema output reliable        -> keep the profile's structured_mode; else use
    json_object / prompt mode, or add `instructor`.

Cost control (this spends credits):
  - Hard cap on calls, enforced at the transport: the call after the cap raises.
  - No retries, no debugging loops: the first API error stops the whole run.
  - A live run refuses to start without --yes. Try --dry-run first (offline, free).

Run:
  uv run python spikes/tool_calling_probe.py --dry-run
  uv run python spikes/tool_calling_probe.py --tiers nano --n 1 --max-calls 2 --yes   # smoke test
  uv run python spikes/tool_calling_probe.py --yes --write                           # the real spike

Spike code is throwaway: never import it from src/halo/.
"""

import argparse
import asyncio
import json
import os
import statistics
import sys
import time
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from pathlib import Path

from pydantic import ValidationError

from halo.config import HaloConfig, ModelTier, load_config, load_env
from halo.core.contracts import Intent
from halo.core.router import _SYSTEM as ROUTER_SYSTEM
from halo.models.transport import (
    ModelRequestError,
    OpenAITransport,
    RawToolCall,
    TransientModelError,
    Transport,
    TransportResponse,
)

RESULTS = Path(__file__).with_name("RESULTS.md")

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "open_app",
            "description": "Open a desktop app by name.",
            "parameters": {
                "type": "object",
                "properties": {"app": {"type": "string"}},
                "required": ["app"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "remember",
            "description": "Store a fact the user wants kept.",
            "parameters": {
                "type": "object",
                "properties": {"fact": {"type": "string"}},
                "required": ["fact"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_expense",
            "description": "Record money the user spent.",
            "parameters": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number"},
                    "category": {"type": "string"},
                    "merchant": {"type": "string"},
                },
                "required": ["amount", "category", "merchant"],
            },
        },
    },
]

# (prompt, expected tool, expected amount for log_expense)
TOOL_CASES: list[tuple[str, str, float | None]] = [
    ("open VS Code", "open_app", None),
    ("launch spotify", "open_app", None),
    ("start the calculator", "open_app", None),
    ("remember that I picked pywebview for the HUD window", "remember", None),
    ("note that my gym day is Tuesday", "remember", None),
    ("keep in mind my passport expires in 2029", "remember", None),
    ("spent 450 on lunch at Cafe X", "log_expense", 450),
    ("log 1200 for the auto to the airport", "log_expense", 1200),
    ("I paid 99 for a movie ticket at PVR", "log_expense", 99),
    ("bought groceries for 2300 at BigBasket", "log_expense", 2300),
]

# (prompt, expected skill)
SCHEMA_CASES: list[tuple[str, str]] = [
    ("open notepad", "app.open"),
    ("hi there, how are you?", "chat"),
    ("add logging to the api module", "code.task"),
    ("plan a long weekend in Jaipur", "trip.plan"),
    ("paid 300 for coffee at Starbucks", "expense.log"),
    ("what was my total spend on travel last month?", "expense.query"),
    ("remember that my wifi password hint is the dog's name", "memory.remember"),
    ("what's my gym day?", "memory.recall"),
    ("forget my old address", "memory.forget"),
    ("let's begin the work day", "work.start"),
]


class CallCapExceeded(Exception):
    pass


class CountingTransport:
    """Wraps a transport and refuses the call after the cap."""

    def __init__(self, inner: Transport, max_calls: int) -> None:
        self.inner, self.max_calls, self.calls = inner, max_calls, 0

    async def chat(self, **kwargs) -> TransportResponse:
        if self.calls >= self.max_calls:
            raise CallCapExceeded(f"hard cap of {self.max_calls} calls reached")
        self.calls += 1
        return await self.inner.chat(**kwargs)


class DryRunTransport:
    """Offline stand-in that answers every probe correctly, to test the harness."""

    async def chat(
        self, *, model_id, messages, json_schema=None, tools=None
    ) -> TransportResponse:
        prompt = messages[-1]["content"]
        if tools:
            for text, tool, amount in TOOL_CASES:
                if text == prompt:
                    args = {
                        "open_app": {"app": prompt},
                        "remember": {"fact": prompt},
                        "log_expense": {
                            "amount": amount,
                            "category": "food",
                            "merchant": "x",
                        },
                    }[tool]
                    call = RawToolCall("c1", tool, json.dumps(args))
                    return TransportResponse(None, 120, 25, [call])
        for text, skill in SCHEMA_CASES:
            if text == prompt:
                body = json.dumps({"skill": skill, "args": {}, "confidence": 0.9})
                return TransportResponse(body, 300, 30)
        raise AssertionError(f"dry-run saw an unknown prompt: {prompt!r}")


@dataclass
class TierStats:
    tier: str
    tool_valid: int = 0
    tool_correct: int = 0
    tool_total: int = 0
    schema_valid: int = 0
    schema_correct: int = 0
    schema_total: int = 0
    latencies_ms: list[float] = field(default_factory=list)
    prompt_tokens: int = 0
    completion_tokens: int = 0
    notes: list[str] = field(default_factory=list)


def check_tool_call(
    response: TransportResponse, expected: str, amount: float | None
) -> tuple[bool, bool]:
    """(structurally valid, correct): valid = exactly one well-formed call to a known tool;
    correct = it is the expected tool with sensible arguments."""
    if len(response.tool_calls) != 1:
        return False, False
    call = response.tool_calls[0]
    try:
        args = json.loads(call.arguments or "{}")
    except json.JSONDecodeError:
        return False, False
    tool = next(
        (t["function"] for t in TOOLS if t["function"]["name"] == call.name), None
    )
    if tool is None or not isinstance(args, dict):
        return False, False
    if any(key not in args for key in tool["parameters"]["required"]):
        return False, False
    if call.name != expected:
        return True, False
    if expected == "log_expense":
        value = args.get("amount")
        ok = (
            isinstance(value, int | float)
            and not isinstance(value, bool)
            and value == amount
        )
        return True, bool(
            ok
            and isinstance(args.get("category"), str)
            and isinstance(args.get("merchant"), str)
        )
    key = "app" if expected == "open_app" else "fact"
    return True, isinstance(args.get(key), str) and bool(args[key].strip())


def price(config: HaloConfig, tier: ModelTier, p: int, c: int) -> Decimal | None:
    spec = config.models[tier]
    if spec.usd_per_m_input is None or spec.usd_per_m_output is None:
        return None
    return (
        (spec.usd_per_m_input * p + spec.usd_per_m_output * c)
        / Decimal(1_000_000)
        * config.usd_to_inr
    )


async def probe_tier(
    config: HaloConfig, transport: CountingTransport, tier: ModelTier, n: int
) -> TierStats:
    stats = TierStats(tier)
    model_id = config.models[tier].id
    schema = {"name": "Intent", "schema": Intent.model_json_schema()}

    for prompt, expected, amount in TOOL_CASES[:n]:
        started = time.perf_counter()
        response = await transport.chat(
            model_id=model_id,
            messages=[{"role": "user", "content": prompt}],
            tools=TOOLS,
        )
        stats.latencies_ms.append((time.perf_counter() - started) * 1000)
        stats.prompt_tokens += response.prompt_tokens
        stats.completion_tokens += response.completion_tokens
        valid, correct = check_tool_call(response, expected, amount)
        stats.tool_total += 1
        stats.tool_valid += valid
        stats.tool_correct += correct

    for prompt, expected_skill in SCHEMA_CASES[:n]:
        started = time.perf_counter()
        response = await transport.chat(
            model_id=model_id,
            messages=[
                {"role": "system", "content": ROUTER_SYSTEM},
                {"role": "user", "content": prompt},
            ],
            json_schema=schema,
        )
        stats.latencies_ms.append((time.perf_counter() - started) * 1000)
        stats.prompt_tokens += response.prompt_tokens
        stats.completion_tokens += response.completion_tokens
        stats.schema_total += 1
        try:
            intent = Intent.model_validate_json((response.content or "").strip())
        except ValidationError:
            continue  # first attempt only: the client's retry is deliberately not used here
        stats.schema_valid += 1
        stats.schema_correct += intent.skill == expected_skill
    return stats


def rate(hit: int, total: int) -> str:
    return f"{hit}/{total} ({hit / total:.0%})" if total else "-"


def render(
    config: HaloConfig, all_stats: list[TierStats], calls: int, dry_run: bool
) -> str:
    lines = [
        (
            f"## {date.today().isoformat()} — Tool calling and JSON-schema validity "
            f"(profile `{config.profile or 'none'}`{', DRY RUN' if dry_run else ''})"
        ),
        "",
        (
            "**Question.** Does each Nemotron tier produce valid tool calls and valid JSON-schema "
            "output at >= 90%, and at what latency and cost?"
        ),
        "",
        (
            f"**Method.** `spikes/tool_calling_probe.py`: per tier, 10 tool-call prompts (3 tools) and "
            f"10 router prompts against the `Intent` schema, structured_mode "
            f"`{config.api.structured_mode}`, first attempt only (no retry), one call at a time. "
            f"{calls} calls total, hard-capped."
        ),
        "",
        (
            "| tier | model id | tool call valid | tool call correct | JSON valid | JSON correct "
            "| median latency | tokens in/out | cost |"
        ),
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for s in all_stats:
        cost = price(config, s.tier, s.prompt_tokens, s.completion_tokens)  # type: ignore[arg-type]
        median = (
            f"{statistics.median(s.latencies_ms):.0f} ms" if s.latencies_ms else "-"
        )
        lines.append(
            f"| {s.tier} | `{config.models[s.tier].id}` | {rate(s.tool_valid, s.tool_total)} "  # type: ignore[index]
            f"| {rate(s.tool_correct, s.tool_total)} | {rate(s.schema_valid, s.schema_total)} "
            f"| {rate(s.schema_correct, s.schema_total)} | {median} "
            f"| {s.prompt_tokens}/{s.completion_tokens} | {'₹' + format(cost, '.4f') if cost is not None else 'price unknown'} |"
        )
    nano = next((s for s in all_stats if s.tier == "nano"), None)
    lines += ["", "**Decisions.**"]
    if nano and nano.tool_total:
        ok = (
            nano.tool_valid / nano.tool_total >= 0.9
            and nano.tool_correct / nano.tool_total >= 0.9
        )
        lines.append(
            "- Nano tool calls >= 90%: "
            + (
                "**yes**, Nano does tool calls."
                if ok
                else "**no**, Nano only routes; Super does tool calls."
            )
        )
    if nano and nano.schema_total:
        ok = nano.schema_valid / nano.schema_total >= 0.9
        lines.append(
            "- JSON-schema output reliable on Nano: "
            + (
                f"**yes** in `{config.api.structured_mode}` mode."
                if ok
                else f"**no** in `{config.api.structured_mode}` mode; try json_object/prompt mode or add `instructor`."
            )
        )
    return "\n".join(lines) + "\n"


async def main() -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    parser.add_argument("--tiers", default="nano,super,ultra")
    parser.add_argument(
        "--n", type=int, default=10, help="cases per kind per tier (max 10)"
    )
    parser.add_argument(
        "--max-calls", type=int, default=60, help="hard cap on API calls"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="offline harness check, no API calls"
    )
    parser.add_argument(
        "--yes", action="store_true", help="confirm a live run that spends credits"
    )
    parser.add_argument(
        "--write", action="store_true", help="append the result to spikes/RESULTS.md"
    )
    args = parser.parse_args()

    tiers: list[ModelTier] = [t for t in args.tiers.split(",") if t]  # type: ignore[misc]
    n = min(args.n, 10)
    planned = len(tiers) * n * 2
    load_env()
    config = load_config()

    if args.dry_run:
        inner: Transport = DryRunTransport()
        # dry-run needs ids that look configured
        for tier in tiers:
            config.models.setdefault(tier, config.models.get(tier) or _fake_spec(tier))
    else:
        for tier in tiers:
            spec = config.models.get(tier)
            if spec is None or spec.id.startswith("UNSET"):
                print(
                    f"Model id for '{tier}' is not set in profile '{config.profile}'. Run spikes/list_models.py."
                )
                return 2
        key = os.environ.get(config.api.key_env)
        if not key or config.api.base_url.startswith("UNSET"):
            print(f"Set {config.api.key_env} in .env and a real base_url first.")
            return 2
        if planned > args.max_calls:
            print(
                f"Plan needs {planned} calls but --max-calls is {args.max_calls}. Raise it or lower --n/--tiers."
            )
            return 2
        if not args.yes:
            print(
                f"LIVE run on profile '{config.profile}': {planned} calls "
                f"({len(tiers)} tiers x {n} tool + {n} JSON), cap {args.max_calls}. "
                "Re-run with --yes to spend the credits."
            )
            return 1
        inner = OpenAITransport(
            base_url=config.api.base_url,
            api_key=key,
            structured_mode=config.api.structured_mode,
            extra_body=config.api.extra_body,
        )

    transport = CountingTransport(inner, args.max_calls)
    all_stats: list[TierStats] = []
    try:
        for tier in tiers:
            all_stats.append(await probe_tier(config, transport, tier, n))
    except (TransientModelError, ModelRequestError, CallCapExceeded) as exc:
        print(f"STOPPED after {transport.calls} calls: {type(exc).__name__}: {exc}")
        print(
            "No retries by design. Fix the cause (key, model id, base_url), then re-run."
        )
        return 1

    report = render(config, all_stats, transport.calls, args.dry_run)
    print(report)
    if args.write and not args.dry_run:
        with RESULTS.open("a", encoding="utf-8") as f:
            f.write("\n---\n\n" + report)
        print(f"Appended to {RESULTS}")
    return 0


def _fake_spec(tier: str):
    from halo.config import ModelSpec

    return ModelSpec(id=f"dry-run-{tier}")


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
