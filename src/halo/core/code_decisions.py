"""Answers to the two cards of a coding session: the task brief and the result.

Like `WorkerApprovals`, a card waits on a Future that `POST /code/decision` resolves,
bound by run id and decision id. Each card offers only some actions, so an answer
the card never showed (Merge on the brief card) is refused. Nothing here is
persisted, and no answer can be remembered for a later card: a click covers exactly
the card the user saw.
"""

import asyncio
from typing import Literal

from pydantic import Field

from halo.core.contracts import HaloModel, TaskBrief

Action = Literal["approve", "deny", "merge", "iterate", "discard"]


class CodeDecision(HaloModel):
    action: Action
    brief: TaskBrief | None = None  # an edited brief, with "approve"
    feedback: str | None = Field(default=None, max_length=2000)  # with "iterate"


class CodeDecisions:
    def __init__(self) -> None:
        self._waiting: dict[
            tuple[str, str], tuple[frozenset[str], asyncio.Future[CodeDecision | None]]
        ] = {}

    async def ask(
        self,
        run_id: str,
        decision_id: str,
        *,
        allowed: frozenset[str],
        timeout: float,
    ) -> CodeDecision | None:
        """Wait for the user. None means no answer: it timed out, or the run was stopped."""
        key = (run_id, decision_id)
        future: asyncio.Future[CodeDecision | None] = (
            asyncio.get_running_loop().create_future()
        )
        self._waiting[key] = (allowed, future)
        try:
            return await asyncio.wait_for(future, timeout)
        except TimeoutError:
            return None
        finally:
            self._waiting.pop(key, None)

    def owns(self, run_id: str, decision_id: str) -> bool:
        return (run_id, decision_id) in self._waiting

    def has_pending(self, run_id: str) -> bool:
        return any(r == run_id for r, _ in self._waiting)

    def resolve(self, run_id: str, decision_id: str, decision: CodeDecision) -> bool:
        """Answer one card. False if it is not waiting (stale, repeated, wrong run);
        ValueError if the card did not offer that action, in which case it keeps waiting."""
        entry = self._waiting.get((run_id, decision_id))
        if entry is None or entry[1].done():
            return False
        allowed, future = entry
        if decision.action not in allowed:
            raise ValueError(f"this card does not offer '{decision.action}'")
        future.set_result(decision)
        return True

    def deny_run(self, run_id: str) -> None:
        """Clear every card a run is waiting on (Stop, or the session ended)."""
        for (r, _), (_, future) in list(self._waiting.items()):
            if r == run_id and not future.done():
                future.set_result(None)
