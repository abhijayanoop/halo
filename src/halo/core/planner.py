"""The planner: turn an Intent into a Plan of Steps.

Single-step skills get a one-step plan with no model call. Multi-step skills
are planned by Super.
"""

import asyncio
from collections.abc import Sequence

from pydantic import Field

from halo.core.contracts import HaloModel, Intent, Plan, RiskLevel, SkillName, Step
from halo.models.client import ModelClient
from halo.skills.errors import SkillArgsError
from halo.skills.registry import SkillRegistry

# code.task and work.start are not here: each runs itself as a single step (a coding
# session with its own cards; a work session read straight from the vault, no model).
MULTI_STEP_SKILLS: set[SkillName] = {"trip.plan"}

MAX_STEPS = 8


class PlanError(Exception):
    """A plan cannot be made or uses something that does not exist."""


class _PlannedSteps(HaloModel):
    """What the model returns; run_id and skill are filled in by code."""

    rationale: str
    steps: list[Step] = Field(min_length=1, max_length=MAX_STEPS)


def needs_plan(skill: SkillName) -> bool:
    return skill in MULTI_STEP_SKILLS


_RISK_ORDER: dict[RiskLevel, int] = {"low": 0, "medium": 1, "high": 2}


def _higher(a: RiskLevel, b: RiskLevel) -> RiskLevel:
    return a if _RISK_ORDER[a] >= _RISK_ORDER[b] else b


async def _skill_risk(
    registry: SkillRegistry, tool: str, args: dict
) -> RiskLevel | None:
    """The risk a skill itself assigns to a call: its manifest risk, raised by its
    own `assess_risk(args)` if it has one. None if `tool` is not a skill. Bad args
    keep the manifest risk (the skill reports the error when it runs); a broken
    configuration is not hidden."""
    if tool not in registry:
        return None
    loaded = registry.get(tool)
    risk: RiskLevel = loaded.manifest.risk
    assess = getattr(loaded.module, "assess_risk", None)
    if assess is not None:
        try:
            # skills may read config from disk, so keep that off the event loop
            risk = _higher(risk, await asyncio.to_thread(assess, args))
        except SkillArgsError:
            pass
    return risk


async def _direct_plan(registry: SkillRegistry, run_id: str, intent: Intent) -> Plan:
    risk = await _skill_risk(registry, intent.skill, intent.args)
    if risk is None:
        raise PlanError(f"skill '{intent.skill}' is not installed")
    return Plan(
        run_id=run_id,
        skill=intent.skill,
        rationale=f"{intent.skill} is a single step",
        steps=[Step(tool=intent.skill, args=intent.args, risk=risk)],
    )


async def make_plan(
    client: ModelClient,
    registry: SkillRegistry,
    run_id: str,
    request: str,
    intent: Intent,
    *,
    available_tools: Sequence[str] | None = None,
    context: str = "",
) -> Plan:
    if not needs_plan(intent.skill):
        return await _direct_plan(registry, run_id, intent)

    system = (
        "You are the planner for Halo, a personal desktop assistant. Break the request into "
        f"at most {MAX_STEPS} ordered steps. Each step is a tool call: tool, args, and risk "
        "(low: read-only; medium: writes something easy to undo; high: irreversible, "
        "external or financial).\n"
    )
    if available_tools is not None:
        system += f"Use only these tools: {', '.join(available_tools)}.\n"
    if context:
        system += f"\nWhat you know, with sources:\n{context}\n"
    system += 'Reply with JSON only: {"rationale": "...", "steps": [{"tool": ..., "args": {...}, "risk": ...}]}.'
    user = f"Request: {request}\nSkill: {intent.skill}\nArgs: {intent.args}"

    result = await client.call(
        "super",
        [{"role": "system", "content": system}, {"role": "user", "content": user}],
        schema=_PlannedSteps,
        run_id=run_id,
    )
    planned = result.parsed
    assert planned is not None

    if available_tools is not None:
        unknown = [s.tool for s in planned.steps if s.tool not in available_tools]
        if unknown:
            raise PlanError(f"plan uses tools that do not exist: {', '.join(unknown)}")
    # The model may raise a step's risk but never lower it: a plan can be steered by
    # untrusted context, so for real skills the floor comes from the skill itself.
    steps: list[Step] = []
    for step in planned.steps:
        floor = await _skill_risk(registry, step.tool, step.args)
        risk = step.risk if floor is None else _higher(step.risk, floor)
        steps.append(step.model_copy(update={"risk": risk}))
    return Plan(
        run_id=run_id,
        skill=intent.skill,
        rationale=planned.rationale,
        steps=steps,
    )
