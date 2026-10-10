from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from halo.core.contracts import (
    ApprovalDecision,
    ApprovalGrant,
    HaloEvent,
    Intent,
    RiskLevel,
    SkillManifest,
    Step,
)


def _event_kwargs(**overrides: object) -> dict:
    base = {
        "id": "ev1",
        "run_id": "run1",
        "ts": datetime.now(UTC),
        "type": "run.started",
        "title": "Started",
    }
    base.update(overrides)
    return base


def test_haloevent_rejects_unknown_type() -> None:
    with pytest.raises(ValidationError):
        HaloEvent(**_event_kwargs(type="not.a.real.type"))


def test_haloevent_payload_default_is_independent_per_instance() -> None:
    a = HaloEvent(**_event_kwargs())
    b = HaloEvent(**_event_kwargs())
    a.payload["x"] = 1
    assert b.payload == {}


def test_haloevent_forbids_extra_fields() -> None:
    with pytest.raises(ValidationError):
        HaloEvent(**_event_kwargs(unexpected_field="nope"))


def test_intent_confidence_out_of_range_rejected() -> None:
    with pytest.raises(ValidationError):
        Intent(skill="chat", confidence=1.5)
    with pytest.raises(ValidationError):
        Intent(skill="chat", confidence=-0.1)


def test_intent_unknown_skill_rejected() -> None:
    with pytest.raises(ValidationError):
        Intent(skill="not.a.skill", confidence=0.9)  # type: ignore[arg-type]


def test_intent_accepts_valid_skill_and_confidence() -> None:
    intent = Intent(skill="app.open", confidence=0.95)
    assert intent.skill == "app.open"
    assert intent.args == {}


@pytest.mark.parametrize("risk", ["low", "medium", "high"])
def test_step_and_skillmanifest_share_risk_literal(risk: RiskLevel) -> None:
    Step(tool="shell", risk=risk)
    SkillManifest(name="app_open", description="Opens an app", risk=risk)


def test_step_and_skillmanifest_reject_invalid_risk() -> None:
    with pytest.raises(ValidationError):
        Step(tool="shell", risk="critical")  # type: ignore[arg-type]
    with pytest.raises(ValidationError):
        SkillManifest(
            name="app_open",
            description="Opens an app",
            risk="critical",  # type: ignore[arg-type]
        )


@pytest.mark.parametrize("grant", ["allow_once", "deny", "always_for_task"])
def test_approvaldecision_accepts_valid_grants(grant: ApprovalGrant) -> None:
    assert ApprovalDecision(grant=grant).grant == grant


def test_approvaldecision_rejects_invalid_grant() -> None:
    with pytest.raises(ValidationError):
        ApprovalDecision(grant="always_forever")  # type: ignore[arg-type]
