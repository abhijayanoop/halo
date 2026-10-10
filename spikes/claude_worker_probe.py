"""Spike: run claude-agent-sdk against a scratch repo, print every message
type, and confirm the can_use_tool permission callback actually fires.

Question: does claude-agent-sdk stream messages over tests/fixtures/demo_repo
and correctly route a non-pre-approved tool call through can_use_tool?

Usage:
    uv run --with claude-agent-sdk python spikes/claude_worker_probe.py

No hardware needed - runs entirely against the demo_repo fixture, using the
already-authenticated `claude` CLI (the SDK shells out to it). No secrets
handled directly by this script.

Throwaway spike code. Never import this from halo/.
"""

import asyncio
from pathlib import Path

import claude_agent_sdk as sdk

DEMO_REPO = Path(__file__).parent.parent / "tests" / "fixtures" / "demo_repo"

can_use_tool_calls: list[tuple[str, dict]] = []


async def can_use_tool(
    tool_name: str, tool_input: dict, context: sdk.ToolPermissionContext
) -> sdk.PermissionResultAllow | sdk.PermissionResultDeny:
    can_use_tool_calls.append((tool_name, tool_input))
    print(f"[can_use_tool] tool={tool_name!r} input={tool_input!r}")
    return sdk.PermissionResultDeny(
        message="Spike probe denies every tool; this callback firing at all is what's being measured."
    )


async def main() -> None:
    if not DEMO_REPO.exists():
        raise SystemExit(f"demo_repo not found at {DEMO_REPO}")

    options = sdk.ClaudeAgentOptions(
        cwd=str(DEMO_REPO),
        can_use_tool=can_use_tool,
        max_turns=3,
    )

    prompt = (
        "List the files in this repository, then run its test suite with "
        "`uv run pytest -q` and tell me whether it passed. Do not edit any files."
    )

    message_types_seen: list[str] = []

    try:
        async for message in sdk.query(prompt=prompt, options=options):
            type_name = type(message).__name__
            message_types_seen.append(type_name)
            print(f"[{type_name}] {message!r}"[:500])
    except sdk.ResultError as exc:
        # Expected here: every tool call is denied, so Claude Code exhausts
        # max_turns still trying, and the CLI subprocess exits non-zero even
        # after streaming the final ResultMessage. The SDK re-raises that as
        # ResultError - callers must handle this, not assume a clean return.
        print(f"\n[ResultError] {exc} (expected: every tool call was denied)")

    print()
    print("=== Summary ===")
    print("Message types seen:", sorted(set(message_types_seen)))
    print("can_use_tool call count:", len(can_use_tool_calls))
    print("can_use_tool fired:", len(can_use_tool_calls) > 0)


if __name__ == "__main__":
    asyncio.run(main())
