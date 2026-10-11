"""Which steps need a human yes, and what a grant covers.

Interim rules until halo/security/policy.py takes over on Day 5: low risk runs,
medium asks (and can be granted for the rest of the task), high always asks.
"""

from collections.abc import Sequence
from typing import get_args

from halo.core.contracts import ApprovalGrant, Step


def needs_approval(step: Step, granted_tools: Sequence[str]) -> bool:
    if step.risk == "low":
        return False
    if step.risk == "high":
        return True
    return step.tool not in granted_tools


def apply_grant(
    grant: str, step: Step, granted_tools: Sequence[str]
) -> tuple[bool, list[str]]:
    """Return (may the step run, the tools now granted for this task). A grant
    for the task never extends to high-risk steps."""
    if grant not in get_args(ApprovalGrant):
        raise ValueError(f"unknown approval grant: {grant!r}")
    granted = list(granted_tools)
    if grant == "deny":
        return False, granted
    if grant == "always_for_task" and step.risk == "medium":
        granted.append(step.tool)
    return True, granted
