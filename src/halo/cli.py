"""The `halo` command: run one request and watch every event as it happens."""

import asyncio
import contextlib
import sys
from collections.abc import Awaitable, Callable
from contextlib import AbstractAsyncContextManager

from rich.console import Console
from rich.text import Text

from halo.bootstrap import Halo, open_halo
from halo.config import load_config, load_env
from halo.core.contracts import (
    ApprovalDecision,
    ApprovalGrant,
    ApprovalRequest,
    HaloEvent,
)
from halo.models.client import ConfigError

USAGE = 'usage: halo "<request>"   e.g. halo "open VS Code"'

_STYLES = {
    "run.started": "bold cyan",
    "run.finished": "bold green",
    "run.failed": "bold red",
    "approval.requested": "bold yellow",
    "approval.resolved": "yellow",
    "policy.blocked": "bold red",
    "cost.updated": "dim",
}


def render_event(event: HaloEvent) -> str:
    line = f"{event.type:<19} {event.title}"
    payload = event.payload
    if event.type == "cost.updated":
        line += f" · {payload.get('model')} · ₹{payload.get('cost_inr')}"
    elif event.type == "approval.requested":
        line += f" [{payload.get('risk')}] {payload.get('detail', '')}"
    elif event.type == "run.failed":
        line += f": {payload.get('reason', '')}"
    return line


def grant_from_choice(choice: str) -> ApprovalGrant:
    match choice.strip().lower():
        case "" | "y" | "yes":
            return "allow_once"
        case "a" | "always":
            return "always_for_task"
        case _:
            return "deny"


async def ask_in_terminal(request: ApprovalRequest, console: Console) -> ApprovalGrant:
    answer = await asyncio.to_thread(
        console.input, "  Allow? [Y]es once / [n]o / [a]lways for this task: "
    )
    return grant_from_choice(answer)


async def run_request(
    request: str,
    *,
    halo_cm: Callable[[], AbstractAsyncContextManager[Halo]],
    console: Console,
    ask: Callable[[ApprovalRequest], Awaitable[ApprovalGrant]],
) -> int:
    """Run `request`, printing events live and asking on the terminal when
    approval is needed. Returns the process exit code."""
    async with halo_cm() as halo, halo.bus.subscribe() as queue:

        async def printer() -> None:
            while True:
                event = await queue.get()
                console.print(
                    Text(render_event(event), style=_STYLES.get(event.type, "")),
                    soft_wrap=True,
                )
                queue.task_done()

        printer_task = asyncio.create_task(printer())
        try:
            outcome = await halo.runner.run(request)
            while outcome.state == "paused" and outcome.approval is not None:
                await queue.join()  # let the approval card print before asking
                grant = await ask(outcome.approval)
                outcome = await halo.runner.resume(
                    outcome.run_id, ApprovalDecision(grant=grant)
                )
            await queue.join()
        finally:
            printer_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await printer_task
    return 0 if outcome.state == "finished" and outcome.result_status == "ok" else 1


def main(argv: list[str] | None = None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    console = Console()
    if not argv:
        console.print(USAGE, soft_wrap=True)
        return 2
    load_env()
    config = load_config()
    try:
        return asyncio.run(
            run_request(
                " ".join(argv),
                halo_cm=lambda: open_halo(config),
                console=console,
                ask=lambda request: ask_in_terminal(request, console),
            )
        )
    except ConfigError as exc:
        console.print(f"Halo is not set up yet: {exc}", soft_wrap=True)
        return 2


def entry() -> None:
    for stream in (sys.stdout, sys.stderr):
        with contextlib.suppress(AttributeError, OSError):
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
    sys.exit(main())
