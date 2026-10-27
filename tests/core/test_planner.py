import json

import pytest
from conftest import reply

from halo.core.contracts import Intent, Plan
from halo.core.planner import MULTI_STEP_SKILLS, PlanError, make_plan, needs_plan
from halo.models.client import ModelValidationError
from halo.skills.registry import SkillRegistry, default_skills_dir


@pytest.fixture(scope="module")
def registry() -> SkillRegistry:
    return SkillRegistry.load(default_skills_dir())


def _planned(*steps: dict, rationale: str = "because") -> str:
    return json.dumps({"rationale": rationale, "steps": list(steps)})


def _step(tool: str, risk: str = "low", **args) -> dict:
    return {"tool": tool, "args": args, "risk": risk}


def test_only_multi_step_skills_need_a_plan() -> None:
    assert MULTI_STEP_SKILLS == {"trip.plan", "work.start"}
    assert needs_plan("trip.plan")
    assert not needs_plan("app.open")
    assert not needs_plan("chat")


async def test_single_step_skill_gets_a_direct_plan_without_a_model_call(
    make_client, registry
) -> None:
    client, transport, _ = make_client()
    intent = Intent(skill="app.open", args={"app": "vs code"}, confidence=0.9)
    plan = await make_plan(client, registry, "run1", "open vs code", intent)
    assert isinstance(plan, Plan)
    assert plan.run_id == "run1"
    assert plan.skill == "app.open"
    assert [(s.tool, s.args, s.risk) for s in plan.steps] == [
        ("app.open", {"app": "vs code"}, "low")
    ]
    assert transport.calls == []


async def test_direct_plan_risk_follows_the_skills_own_assessment(
    make_client, registry
) -> None:
    client, _, _ = make_client()
    intent = Intent(skill="app.open", args={"app": "Spotify"}, confidence=0.9)
    plan = await make_plan(client, registry, "run1", "open spotify", intent)
    assert plan.steps[0].risk == "medium"


async def test_direct_plan_for_a_skill_that_is_not_installed_raises(
    make_client, registry
) -> None:
    client, _, _ = make_client()
    intent = Intent(skill="expense.log", args={}, confidence=0.9)
    with pytest.raises(PlanError, match="expense.log"):
        await make_plan(client, registry, "run1", "x", intent)


async def test_multi_step_skill_is_planned_by_super(make_client, registry) -> None:
    body = _planned(
        _step("repo_map"), _step("task_brief", "medium"), rationale="map then brief"
    )
    client, transport, _ = make_client(reply(body))
    intent = Intent(
        skill="trip.plan", args={"task": "add rate limiting"}, confidence=0.9
    )
    plan = await make_plan(client, registry, "run2", "add rate limiting", intent)
    assert plan.run_id == "run2"
    assert plan.skill == "trip.plan"
    assert plan.rationale == "map then brief"
    assert [s.tool for s in plan.steps] == ["repo_map", "task_brief"]
    assert [c["model_id"] for c in transport.calls] == ["super-id"]


async def test_planner_prompt_carries_the_request_the_intent_and_the_tools(
    make_client, registry
) -> None:
    client, transport, _ = make_client(reply(_planned(_step("repo_map"))))
    intent = Intent(skill="trip.plan", args={"task": "t"}, confidence=0.9)
    await make_plan(
        client,
        registry,
        "r",
        "add rate limiting",
        intent,
        available_tools=["repo_map", "git_ops"],
    )
    text = "\n".join(m["content"] for m in transport.calls[0]["messages"])
    assert "add rate limiting" in text
    assert "trip.plan" in text
    assert "repo_map" in text and "git_ops" in text


async def test_step_using_an_unavailable_tool_is_rejected(
    make_client, registry
) -> None:
    client, _, _ = make_client(reply(_planned(_step("rm_rf_everything", "high"))))
    intent = Intent(skill="trip.plan", args={}, confidence=0.9)
    with pytest.raises(PlanError, match="rm_rf_everything"):
        await make_plan(
            client, registry, "r", "x", intent, available_tools=["repo_map"]
        )


async def test_a_plan_with_no_steps_is_invalid(make_client, registry) -> None:
    client, _, _ = make_client(reply(_planned()), reply(_planned()))
    intent = Intent(skill="trip.plan", args={}, confidence=0.9)
    with pytest.raises(ModelValidationError):
        await make_plan(client, registry, "r", "x", intent)


async def test_a_plan_is_capped_at_eight_steps(make_client, registry) -> None:
    too_many = _planned(*[_step("t") for _ in range(9)])
    client, _, _ = make_client(reply(too_many), reply(too_many))
    intent = Intent(skill="trip.plan", args={}, confidence=0.9)
    with pytest.raises(ModelValidationError):
        await make_plan(client, registry, "r", "x", intent)


async def test_planning_cost_is_tagged_with_the_run(make_client, registry) -> None:
    events = []
    client, _, _ = make_client(reply(_planned(_step("t"))), emit=events.append)
    intent = Intent(skill="trip.plan", args={}, confidence=0.9)
    await make_plan(client, registry, "run5", "x", intent)
    assert [(e.type, e.run_id) for e in events] == [("cost.updated", "run5")]


async def test_bad_args_do_not_stop_planning_the_skill_reports_them_later(
    make_client, registry
) -> None:
    client, _, _ = make_client()
    intent = Intent(skill="app.open", args={}, confidence=0.9)
    plan = await make_plan(client, registry, "r", "open", intent)
    assert plan.steps[0].risk == "low"  # the skill manifest's own risk


async def test_code_task_is_one_direct_step_with_no_planner_call(
    make_client, registry
) -> None:
    client, transport, _ = make_client()
    args = {"task": "add rate limiting", "mode": "implement", "project": "halo"}
    intent = Intent(skill="code.task", args=args, confidence=0.9)
    plan = await make_plan(client, registry, "run1", "add rate limiting", intent)
    assert [(s.tool, s.args, s.risk) for s in plan.steps] == [
        ("code.task", args, "low")
    ]
    assert transport.calls == []
