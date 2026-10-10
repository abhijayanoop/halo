"""Halo's shared contracts.

Every component (router, planner, executor, HUD, memory, skills, the coding
worker) talks to every other component only through these types. Frozen per
CLAUDE.md: changes go through the /add-event skill, not ad-hoc edits.
"""

from datetime import date, datetime
from decimal import Decimal
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field


class HaloModel(BaseModel):
    """Base for every Halo contract. Rejects unexpected fields so schema
    drift between producers and consumers fails loudly, not silently."""

    model_config = ConfigDict(extra="forbid")


# --- Shared vocabularies -----------------------------------------------

RiskLevel = Literal["low", "medium", "high"]

MemorySource = Literal["you", "web", "tool", "agent"]
TrustLevel = Literal["high", "medium", "low"]

SkillName = Literal[
    "chat",
    "app.open",
    "code.task",
    "trip.plan",
    "expense.log",
    "expense.query",
    "memory.remember",
    "memory.recall",
    "memory.forget",
    "work.start",
]

ApprovalGrant = Literal["allow_once", "deny", "always_for_task"]

HaloEventType = Literal[
    "run.started",
    "run.finished",
    "run.failed",
    "step.started",
    "step.finished",
    "agent.spawned",
    "agent.finished",
    "tool.called",
    "tool.result",
    "approval.requested",
    "approval.resolved",
    "memory.proposed",
    "memory.saved",
    "memory.forgotten",
    "egress.sent",
    "cost.updated",
    "policy.blocked",
    "voice.listening",
    "voice.heard",
    "mood",
]


# --- The event bus -------------------------------------------------------


class HaloEvent(HaloModel):
    """One typed event. Everything the HUD shows and the flight recorder
    saves is a HaloEvent; UI state is derived only from these."""

    id: str  # ulid
    run_id: str  # one user request
    ts: datetime
    type: HaloEventType
    agent_id: str | None = None
    parent_agent_id: str | None = None
    title: str  # short human text, e.g. "Searching hotels in Anjuna"
    payload: dict = Field(default_factory=dict)


# --- Router / planner / executor -----------------------------------------


class Intent(HaloModel):
    """The router's output: which skill, with what arguments, and how
    confident it is. Confidence < 0.7 escalates Nano to Super."""

    skill: SkillName
    args: dict = Field(default_factory=dict)
    confidence: float = Field(ge=0.0, le=1.0)


class Step(HaloModel):
    """One step of a Plan: a tool call with its arguments and risk tier."""

    tool: str
    args: dict = Field(default_factory=dict)
    risk: RiskLevel


class Plan(HaloModel):
    """The planner's multi-step output for skills that need one. Single-step
    skills skip planning entirely."""

    run_id: str
    skill: SkillName
    rationale: str
    steps: list[Step] = Field(default_factory=list)


# --- The coding work session ----------------------------------------------


class TaskBrief(HaloModel):
    """The contract for a coding task: what the worker builds against and
    what the reviewer grades against. Shown in the approval card and
    editable there before you approve it."""

    goal: str
    acceptance_criteria: list[str]
    likely_files: list[str] = Field(default_factory=list)
    test_cmd: str
    constraints: list[str] = Field(default_factory=list)
    out_of_scope: list[str] = Field(default_factory=list)


class Review(HaloModel):
    """A verdict against a TaskBrief's acceptance criteria (or, reused
    as-is, an eval judge's verdict). `summary` always carries a
    plain-language reason, even for an infra-level failure like a worker
    timeout; `issues` is for itemized review comments."""

    result: Literal["pass", "concerns"]
    summary: str
    issues: list[str] = Field(default_factory=list)


# --- Memory -----------------------------------------------------------------


class MemoryItem(HaloModel):
    """A stored, provenanced memory. `privacy` is copied from the
    destination note's frontmatter at write/parse time — the raising check
    in halo/models/client.py that forbids `privacy: local` content from
    reaching a cloud prompt only ever sees MemoryItems, never raw notes."""

    fact: str
    source: MemorySource
    trust: TrustLevel
    created_at: datetime
    expires_at: datetime | None = None
    block_id: str  # Obsidian block id, e.g. "^m-4f2a"
    note_path: str
    superseded: bool = False
    privacy: Literal["shared", "local"]


class MemoryCandidate(HaloModel):
    """An extracted memory proposal, before approval. Not yet tied to any
    note, so it carries no `privacy` — that's decided once a skill picks
    the destination note and it becomes a MemoryItem."""

    fact: str
    subject: str
    source: MemorySource
    trust: TrustLevel


# --- Expenses -----------------------------------------------------------


class Expense(HaloModel):
    """A logged expense. SQL computes every total from these — never a
    model — so this is a pure data record with no computed fields."""

    amount: Decimal
    currency: str = "INR"
    category: str
    merchant: str
    date: date
    note: str | None = None
    confidence: float | None = Field(default=None, ge=0.0, le=1.0)


# --- Approvals -----------------------------------------------------------


class ApprovalRequest(HaloModel):
    """The payload behind an approval.requested event / the HUD's
    permission card. The "high-risk can never be an always-grant" rule is
    enforced in halo/security/policy.py, not here — the request and the
    eventual decision are separate payloads that only meet at the policy
    engine."""

    action: str
    detail: str  # the exact command, or a diff summary
    risk: RiskLevel


class ApprovalDecision(HaloModel):
    """The POST /approve body that resumes a paused LangGraph node via
    Command(resume=decision). "always_for_task" grants are session-scoped
    only — enforced by the policy engine, never persisted to disk."""

    grant: ApprovalGrant


# --- Skills ----------------------------------------------------------------


class SkillManifest(HaloModel):
    """Parsed from a skill's SKILL.md frontmatter."""

    name: str
    description: str
    tools: list[str] = Field(default_factory=list)
    risk: RiskLevel


@runtime_checkable
class RunContext(Protocol):
    """What a Skill needs to stamp and publish events as it runs."""

    run_id: str

    def emit(self, event: HaloEvent) -> None: ...


@runtime_checkable
class Skill(Protocol):
    """A skill module exposes a top-level `async def run(ctx, args)`. A
    module-level function isn't bound like a class method, so `module.run`
    satisfies this Protocol's `run(self, ctx, args)` signature directly
    once `self` is excluded for attribute access."""

    async def run(self, ctx: RunContext, args: dict) -> dict: ...
