"""Drives the graph for one request and tells the world about it.

The runner owns the run-level events: `run.started`, `approval.requested`,
`approval.resolved`, `run.finished` and `run.failed`. Graph nodes can be
re-executed on resume, so they never emit those.
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any, Literal

from langgraph.types import Command

from halo.core.contracts import ApprovalDecision, ApprovalRequest, HaloEvent
from halo.core.events import make_event, new_event_id
from halo.core.state import initial_state

logger = logging.getLogger(__name__)

RunState = Literal["finished", "paused", "failed"]
ResultStatus = Literal["ok", "denied", "error"]


@dataclass
class RunOutcome:
    run_id: str
    state: RunState
    result_status: ResultStatus | None = None
    results: list[dict[str, Any]] = field(default_factory=list)
    approval: ApprovalRequest | None = None
    error: str | None = None


def _failure_reason(exc: Exception) -> str:
    """A fixed plain-language reason per kind of failure. The exception text is
    logged but never put in an event: events reach the JSONL file and the
    /events stream, and provider errors can echo request content."""
    from halo.models.client import (
        ConfigError,
        ModelUnavailableError,
        ModelValidationError,
        PrivacyViolationError,
    )
    from halo.models.transport import ModelRequestError

    if isinstance(exc, ModelUnavailableError):
        return "Couldn't reach the model service. Try again in a moment."
    if isinstance(exc, ModelValidationError):
        return "The model's answer wasn't in the expected format."
    if isinstance(exc, ModelRequestError):
        return "The model service rejected the request."
    if isinstance(exc, ConfigError):
        return "Model access isn't set up."
    if isinstance(exc, PrivacyViolationError):
        return "Blocked: private note text was about to be sent to the cloud."
    return "Something went wrong while running this request."


def _result_status(results: list[dict[str, Any]]) -> ResultStatus:
    statuses = {r["status"] for r in results}
    if "denied" in statuses:
        return "denied"
    if "error" in statuses:
        return "error"
    return "ok"


class HaloRunner:
    def __init__(self, graph: Any, emit: Callable[[HaloEvent], None]) -> None:
        self._graph = graph
        self._emit = emit

    @staticmethod
    def _config(run_id: str) -> dict[str, Any]:
        return {"configurable": {"thread_id": run_id}, "recursion_limit": 50}

    async def run(self, request: str, *, run_id: str | None = None) -> RunOutcome:
        run_id = run_id or new_event_id()
        self._emit(
            make_event(
                run_id, "run.started", request[:80], payload={"request": request}
            )
        )
        return await self._drive(run_id, initial_state(run_id, request))

    async def resume(self, run_id: str, decision: ApprovalDecision) -> RunOutcome:
        if await self.pending_approval(run_id) is None:
            raise ValueError(f"run {run_id} is not waiting for approval")
        self._emit(
            make_event(
                run_id,
                "approval.resolved",
                "Decision received",
                payload={"grant": decision.grant},
            )
        )
        return await self._drive(run_id, Command(resume=decision.grant))

    async def retry(self, run_id: str) -> RunOutcome:
        """Continue a failed run from its last checkpoint."""
        return await self._drive(run_id, None)

    async def pending_approval(self, run_id: str) -> ApprovalRequest | None:
        snapshot = await self._graph.aget_state(self._config(run_id))
        for task in snapshot.tasks:
            for interruption in task.interrupts:
                return ApprovalRequest.model_validate(interruption.value["request"])
        return None

    async def _drive(self, run_id: str, graph_input: Any) -> RunOutcome:
        try:
            result = await self._graph.ainvoke(graph_input, self._config(run_id))
        except Exception as exc:
            logger.exception("run %s failed", run_id)
            reason = _failure_reason(exc)
            self._emit(
                make_event(
                    run_id,
                    "run.failed",
                    "That didn't work",
                    payload={"reason": reason, "error_type": type(exc).__name__},
                )
            )
            return RunOutcome(run_id, "failed", error=reason)

        if interruptions := result.get("__interrupt__"):
            value = interruptions[0].value
            request = ApprovalRequest.model_validate(value["request"])
            self._emit(
                make_event(
                    run_id,
                    "approval.requested",
                    f"Can I run {request.action}?",
                    payload={
                        **request.model_dump(mode="json"),
                        "step_index": value["step_index"],
                    },
                )
            )
            return RunOutcome(run_id, "paused", approval=request)

        results = result["results"]
        status = _result_status(results)
        self._emit(
            make_event(
                run_id,
                "run.finished",
                "Done" if status == "ok" else f"Finished ({status})",
                payload={"status": status, "results": results},
            )
        )
        return RunOutcome(run_id, "finished", result_status=status, results=results)
