"""The LangGraph: route -> plan -> (gate -> run_step)* until the plan is done.

Rules that keep resume safe: a node that calls `interrupt()` is re-run from its
top on resume, so the gate does nothing observable before it. Events about the
run itself (started, approval requested/resolved, finished, failed) are emitted
by `HaloRunner`, not by nodes. Nodes emit only step and tool events.
"""

from collections.abc import Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import aiosqlite
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from halo.core.approval import apply_grant, needs_approval
from halo.core.context import HaloContext
from halo.core.contracts import ApprovalRequest, HaloEvent, HaloEventType, Step
from halo.core.events import make_event, new_event_id
from halo.core.planner import make_plan
from halo.core.router import route
from halo.core.state import HaloState
from halo.models.client import ModelClient
from halo.skills.registry import SkillRegistry

_CHECKPOINTED_TYPES = [
    ("halo.core.contracts", name)
    for name in ("Intent", "Plan", "Step", "ApprovalRequest")
]


@dataclass
class GraphDeps:
    """Everything the nodes need that must not be checkpointed."""

    model: ModelClient
    registry: SkillRegistry
    emit: Callable[[HaloEvent], None]


def checkpoint_serde() -> JsonPlusSerializer:
    """Serializer for graph state. Halo's own models are allowlisted so they
    round-trip as typed objects."""
    return JsonPlusSerializer(allowed_msgpack_modules=_CHECKPOINTED_TYPES)


@asynccontextmanager
async def open_checkpointer(path: Path | str):
    """A SQLite checkpointer on a file (created, with its folder, if missing)."""
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(str(path)) as conn:
        yield AsyncSqliteSaver(conn, serde=checkpoint_serde())


def _result_status(result: dict[str, Any]) -> str:
    if "error" in result or result.get("needs_approval"):
        return "error"
    return "ok"


def _describe(registry: SkillRegistry, step: Step) -> str:
    """The exact action shown on the approval card. A skill may describe its own
    args (so only validated fields appear); the default is the raw args."""
    if step.tool in registry:
        describe = getattr(registry.get(step.tool).module, "describe", None)
        if callable(describe):
            try:
                return str(describe(step.args))
            except ValueError:
                pass
    return str(step.args)


def _grantable(registry: SkillRegistry, step: Step) -> bool:
    """Ask the step's skill whether "always for this task" may cover it."""
    if step.tool not in registry:
        return True
    check = getattr(registry.get(step.tool).module, "grantable", None)
    return bool(check(step.args)) if callable(check) else True


def build_graph(deps: GraphDeps, checkpointer: AsyncSqliteSaver):
    def step_event(
        state: HaloState, type: HaloEventType, title: str, payload: dict[str, Any]
    ) -> None:
        deps.emit(make_event(state["run_id"], type, title, payload=payload))

    async def route_node(state: HaloState) -> dict[str, Any]:
        step_event(
            state, "step.started", "Working out what you want", {"stage": "route"}
        )
        intent = await route(deps.model, state["request"], run_id=state["run_id"])
        step_event(
            state,
            "step.finished",
            f"Understood: {intent.skill}",
            {"stage": "route", "skill": intent.skill, "confidence": intent.confidence},
        )
        return {"intent": intent}

    async def plan_node(state: HaloState) -> dict[str, Any]:
        intent = state["intent"]
        assert intent is not None
        step_event(state, "step.started", "Planning", {"stage": "plan"})
        plan = await make_plan(
            deps.model, deps.registry, state["run_id"], state["request"], intent
        )
        step_event(
            state,
            "step.finished",
            f"Plan ready: {len(plan.steps)} step{'' if len(plan.steps) == 1 else 's'}",
            {"stage": "plan", "steps": len(plan.steps)},
        )
        return {"plan": plan}

    async def gate_node(state: HaloState) -> dict[str, Any]:
        plan = state["plan"]
        assert plan is not None
        index = state["step_index"]
        step = plan.steps[index]
        if not needs_approval(step, state["granted_tools"]):
            return {"approved": True}

        request = ApprovalRequest(
            approval_id=new_event_id(),
            action=step.tool,
            detail=_describe(deps.registry, step),
            risk=step.risk,
        )
        # Nothing observable happens before this line: on resume the node runs again.
        grant = interrupt(
            {"request": request.model_dump(mode="json"), "step_index": index}
        )
        allowed, granted = apply_grant(
            grant,
            step,
            state["granted_tools"],
            grantable=_grantable(deps.registry, step),
        )
        update: dict[str, Any] = {"approved": allowed, "granted_tools": granted}
        if not allowed:
            update["results"] = [
                {"step": index, "tool": step.tool, "status": "denied", "result": {}}
            ]
        return update

    async def run_step_node(state: HaloState) -> dict[str, Any]:
        plan = state["plan"]
        assert plan is not None
        index = state["step_index"]
        step = plan.steps[index]
        progress = {
            "step": index + 1,
            "of": len(plan.steps),
            "tool": step.tool,
            "risk": step.risk,
        }
        step_event(state, "step.started", f"Running {step.tool}", progress)

        if step.tool not in deps.registry:
            result: dict[str, Any] = {"error": f"no tool named '{step.tool}'"}
        else:
            ctx = HaloContext(
                state["run_id"],
                deps.emit,
                deps.model,
                # Only a step that needed a yes carries one; a low-risk step is never "approved".
                approved=state["approved"] and step.risk != "low",
            )
            try:
                result = await deps.registry.get(step.tool).module.run(ctx, step.args)
            except ValueError as exc:  # bad arguments from the model are a step error
                result = {"error": str(exc)}

        status = _result_status(result)
        record = {"step": index, "tool": step.tool, "status": status, "result": result}
        step_event(
            state,
            "step.finished",
            f"Finished {step.tool}" if status == "ok" else f"{step.tool} did not work",
            {**progress, "status": status, "result": result},
        )
        return {"results": [record], "step_index": index + 1, "approved": False}

    def after_plan(state: HaloState) -> str:
        plan = state["plan"]
        return "gate" if plan and plan.steps else END

    def after_gate(state: HaloState) -> str:
        return "run_step" if state["approved"] else END

    def after_step(state: HaloState) -> str:
        plan = state["plan"]
        assert plan is not None
        if state["results"][-1]["status"] == "error":
            return END
        return "gate" if state["step_index"] < len(plan.steps) else END

    builder = StateGraph(HaloState)
    builder.add_node("route", route_node)
    builder.add_node("plan", plan_node)
    builder.add_node("gate", gate_node)
    builder.add_node("run_step", run_step_node)
    builder.add_edge(START, "route")
    builder.add_edge("route", "plan")
    builder.add_conditional_edges("plan", after_plan, ["gate", END])
    builder.add_conditional_edges("gate", after_gate, ["run_step", END])
    builder.add_conditional_edges("run_step", after_step, ["gate", END])
    return builder.compile(checkpointer=checkpointer)
