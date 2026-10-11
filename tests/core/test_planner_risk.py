"""The model may raise a step's risk but can never lower it: risk is re-derived
in code from the skill itself, because a plan can be steered by untrusted context."""

import json

import pytest
from conftest import reply

from halo.core.contracts import Intent
from halo.core.planner import make_plan
from halo.skills.registry import SkillRegistry, default_skills_dir


@pytest.fixture(scope="module")
def registry() -> SkillRegistry:
    return SkillRegistry.load(default_skills_dir())


def _plan_json(tool: str, risk: str, **args) -> str:
    return json.dumps(
        {"rationale": "r", "steps": [{"tool": tool, "args": args, "risk": risk}]}
    )


async def _risk_of(make_client, registry, tool: str, risk: str, **args) -> str:
    client, _, _ = make_client(reply(_plan_json(tool, risk, **args)))
    intent = Intent(skill="code.task", args={}, confidence=0.9)
    plan = await make_plan(client, registry, "r", "x", intent)
    return plan.steps[0].risk


async def test_the_model_cannot_downgrade_a_step_the_skill_says_needs_approval(
    make_client, registry
) -> None:
    # app.open of an app that is not on the allowlist is medium risk by the skill's own rule
    assert (
        await _risk_of(make_client, registry, "app.open", "low", app="Spotify")
        == "medium"
    )


async def test_the_model_can_raise_risk_above_what_the_skill_says(
    make_client, registry
) -> None:
    assert (
        await _risk_of(make_client, registry, "app.open", "high", app="vscode")
        == "high"
    )


async def test_a_low_risk_step_stays_low_when_everything_agrees(
    make_client, registry
) -> None:
    assert (
        await _risk_of(make_client, registry, "app.open", "low", app="vscode") == "low"
    )


async def test_a_step_with_bad_args_keeps_at_least_the_manifest_risk(
    make_client, registry
) -> None:
    assert await _risk_of(make_client, registry, "app.open", "low") == "low"


async def test_a_tool_that_is_not_a_skill_keeps_the_models_label(
    make_client, registry
) -> None:
    # nothing can run for an unknown tool (the executor reports an error), so the label only
    # decides whether a prompt appears
    assert await _risk_of(make_client, registry, "teleport", "high") == "high"
