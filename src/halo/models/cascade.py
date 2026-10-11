"""Model cascade: ask the cheap model first, move up only when needed.

Escalation signals: confidence below the threshold, a validation failure that
survived the client's one retry, or the model being unavailable. Every hop is
logged and marked on the `cost.updated` event of the call it caused.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any, Literal

from pydantic import BaseModel

from halo.config import ModelTier
from halo.models.client import (
    CallResult,
    ModelClient,
    ModelUnavailableError,
    ModelValidationError,
)

logger = logging.getLogger(__name__)

EscalationReason = Literal["low_confidence", "validation_failed", "unavailable"]


@dataclass(frozen=True)
class Escalation:
    from_tier: ModelTier
    reason: EscalationReason


@dataclass(frozen=True)
class CascadeResult[T]:
    parsed: T
    tier: ModelTier
    call: CallResult[T]
    escalations: list[Escalation]


async def cascade_call[T: BaseModel](
    client: ModelClient,
    messages: Sequence[dict[str, Any]],
    schema: type[T],
    *,
    tiers: Sequence[ModelTier] = ("nano", "super"),
    min_confidence: float = 0.7,
    run_id: str | None = None,
) -> CascadeResult[T]:
    """`schema` must have a `confidence` field. The last tier's answer is
    returned whatever its confidence; failures on it are raised."""
    if "confidence" not in schema.model_fields:
        raise TypeError(
            f"{schema.__name__} needs a 'confidence' field to be used in a cascade"
        )

    escalations: list[Escalation] = []
    for index, tier in enumerate(tiers):
        is_last = index == len(tiers) - 1
        note: dict[str, Any] | None = None
        if escalations:
            last = escalations[-1]
            note = {"escalated_from": last.from_tier, "escalation_reason": last.reason}

        reason: EscalationReason
        try:
            result = await client.call(
                tier, messages, schema=schema, run_id=run_id, note=note
            )
        except ModelValidationError:
            if is_last:
                raise
            reason = "validation_failed"
        except ModelUnavailableError:
            if is_last:
                raise
            reason = "unavailable"
        else:
            assert result.parsed is not None
            confidence = getattr(result.parsed, "confidence")  # noqa: B009
            if confidence >= min_confidence or is_last:
                return CascadeResult(result.parsed, tier, result, escalations)
            reason = "low_confidence"

        escalations.append(Escalation(tier, reason))
        logger.info("escalating %s -> %s (%s)", tier, tiers[index + 1], reason)
    raise ValueError("cascade needs at least one tier")
