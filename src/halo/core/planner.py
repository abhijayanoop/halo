"""The planner: turn an Intent into a Plan of Steps.

Single-step skills get a one-step plan with no model call. Multi-step skills
are planned by Super.
"""

from collections.abc import Sequence

from pydantic import Field

from halo.core.contracts import HaloModel, Intent, Plan, RiskLevel, SkillName, Step
from halo.models.client import ModelClient
from halo.skills.registry import SkillRegistry

MULTI_STEP_SKILLS: set[SkillName] = {"code.task", "trip.plan", "work.start"}

MAX_STEPS = 8


class PlanError(Exception):
    """A plan cannot be made or uses something that does not exist."""


class _PlannedSteps(HaloModel):
    """What the model returns; run_id and skill are filled in by code."""

    rationale: str
    steps: list[Step] = Field(min_length=1, max_length=MAX_STEPS)


def needs_plan(skill: SkillName) -> bool:
    return skill in MULTI_STEP_SKILLS


def _direct_plan(registry: SkillRegistry, run_id: str, intent: Intent) -> Plan:
    if intent.skill not in registry:
        raise PlanError(f"skill '{intent.skill}' is not installed")
    loaded = registry.get(intent.skill)
    risk: RiskLevel = loaded.manifest.risk
    assess = getattr(loaded.module, "assess_risk", None)
    if assess is not None:
        risk = assess(intent.args)
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
        return _direct_plan(registry, run_id, intent)

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
    return Plan(
        run_id=run_id,
        skill=intent.skill,
        rationale=planned.rationale,
        steps=planned.steps,
    )
