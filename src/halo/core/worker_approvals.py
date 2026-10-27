"""Permission requests that come from inside a coding worker.

A worker (Claude Code) asks before a tool use that is not pre-approved. Unlike a
plan step there is no graph node waiting, so the request waits on a Future that
`POST /approve` resolves, matched by run id and approval id. Worker tools never
get an "always" grant: a card answer covers exactly the call the user saw.
"""

import asyncio
from typing import get_args

from halo.core.contracts import ApprovalGrant, ApprovalRequest

Answer = str  # "allow_once" or "deny"


class WorkerApprovals:
    def __init__(self) -> None:
        self._waiting: dict[tuple[str, str], asyncio.Future[Answer]] = {}

    async def ask(
        self, run_id: str, request: ApprovalRequest, *, timeout: float
    ) -> Answer:
        """Wait for the user's answer. No answer in time is a denial."""
        key = (run_id, request.approval_id)
        future: asyncio.Future[Answer] = asyncio.get_running_loop().create_future()
        self._waiting[key] = future
        try:
            return await asyncio.wait_for(future, timeout)
        except TimeoutError:
            return "deny"
        finally:
            self._waiting.pop(key, None)

    def owns(self, run_id: str, approval_id: str) -> bool:
        return (run_id, approval_id) in self._waiting

    def has_pending(self, run_id: str) -> bool:
        return any(r == run_id for r, _ in self._waiting)

    def resolve(self, run_id: str, approval_id: str, grant: ApprovalGrant) -> bool:
        """Answer one request. False if it is not waiting (stale, repeated or wrong run)."""
        if grant not in get_args(ApprovalGrant):
            raise ValueError(f"unknown approval grant: {grant!r}")
        future = self._waiting.get((run_id, approval_id))
        if future is None or future.done():
            return False
        future.set_result("deny" if grant == "deny" else "allow_once")
        return True

    def deny_run(self, run_id: str) -> None:
        """Deny everything a run is waiting on (Stop, or the worker ended)."""
        for (r, _), future in list(self._waiting.items()):
            if r == run_id and not future.done():
                future.set_result("deny")
