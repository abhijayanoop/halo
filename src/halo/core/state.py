"""The shared state every graph node reads and updates."""

import operator
from typing import Annotated, Any, TypedDict

from halo.core.contracts import ApprovalRequest, Intent, Plan


class HaloState(TypedDict):
    run_id: str
    request: str
    intent: Intent | None
    plan: Plan | None
    # Nodes append to these; the Annotated reducer concatenates instead of replacing.
    results: Annotated[list[dict[str, Any]], operator.add]
    pending_approval: ApprovalRequest | None
    messages: Annotated[list[dict[str, Any]], operator.add]
    # Executor bookkeeping: which plan step is next, whether the gate cleared
    # it. Grants ("always for this task") are not here: the checkpoint is on disk.
    step_index: int
    approved: bool


def initial_state(run_id: str, request: str) -> HaloState:
    return HaloState(
        run_id=run_id,
        request=request,
        intent=None,
        plan=None,
        results=[],
        pending_approval=None,
        messages=[],
        step_index=0,
        approved=False,
    )
