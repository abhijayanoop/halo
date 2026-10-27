import asyncio

import pytest

from halo.core.code_decisions import CodeDecision, CodeDecisions
from halo.core.contracts import TaskBrief

BRIEF_ACTIONS = frozenset({"approve", "deny"})
RESULT_ACTIONS = frozenset({"merge", "iterate", "discard"})


async def _waiting(
    decisions: CodeDecisions,
    allowed: frozenset[str] = BRIEF_ACTIONS,
    run_id: str = "r1",
    decision_id: str = "d1",
):
    task = asyncio.create_task(
        decisions.ask(run_id, decision_id, allowed=allowed, timeout=5)
    )
    await asyncio.sleep(0)
    return task


async def test_an_allowed_answer_resolves_the_waiting_card() -> None:
    decisions = CodeDecisions()
    task = await _waiting(decisions)
    assert decisions.owns("r1", "d1") and decisions.has_pending("r1")
    assert decisions.resolve("r1", "d1", CodeDecision(action="approve"))
    answer = await task
    assert answer is not None and answer.action == "approve"
    assert not decisions.has_pending("r1")


async def test_an_action_that_card_does_not_offer_is_refused_and_the_card_keeps_waiting() -> (
    None
):
    decisions = CodeDecisions()
    task = await _waiting(decisions, allowed=BRIEF_ACTIONS)
    with pytest.raises(ValueError):
        decisions.resolve("r1", "d1", CodeDecision(action="merge"))
    assert not task.done()
    decisions.resolve("r1", "d1", CodeDecision(action="deny"))
    assert (await task).action == "deny"  # type: ignore[union-attr]


async def test_a_result_card_cannot_be_answered_with_approve() -> None:
    decisions = CodeDecisions()
    task = await _waiting(decisions, allowed=RESULT_ACTIONS)
    with pytest.raises(ValueError):
        decisions.resolve("r1", "d1", CodeDecision(action="approve"))
    decisions.deny_run("r1")
    assert await task is None


async def test_wrong_id_or_run_is_not_resolved() -> None:
    decisions = CodeDecisions()
    task = await _waiting(decisions)
    assert not decisions.resolve("r1", "other", CodeDecision(action="approve"))
    assert not decisions.resolve("r2", "d1", CodeDecision(action="approve"))
    assert not task.done()
    decisions.deny_run("r1")
    assert await task is None


async def test_a_second_answer_is_refused() -> None:
    decisions = CodeDecisions()
    task = await _waiting(decisions)
    assert decisions.resolve("r1", "d1", CodeDecision(action="approve"))
    assert not decisions.resolve("r1", "d1", CodeDecision(action="deny"))
    assert (await task).action == "approve"  # type: ignore[union-attr]


async def test_no_answer_in_time_is_none() -> None:
    decisions = CodeDecisions()
    assert await decisions.ask("r1", "d1", allowed=BRIEF_ACTIONS, timeout=0.01) is None
    assert not decisions.has_pending("r1")


async def test_stop_clears_every_waiting_card_of_that_run_only() -> None:
    decisions = CodeDecisions()
    mine = await _waiting(decisions, run_id="r1", decision_id="a")
    other = await _waiting(decisions, run_id="r2", decision_id="b")
    decisions.deny_run("r1")
    assert await mine is None
    assert not other.done()
    decisions.deny_run("r2")
    await other


def test_a_decision_can_carry_an_edited_brief_and_feedback() -> None:
    brief = TaskBrief(goal="g", acceptance_criteria=["c"], test_cmd="t")
    d = CodeDecision(action="iterate", brief=brief, feedback="also add a header")
    assert d.brief == brief and d.feedback == "also add a header"
    with pytest.raises(ValueError):
        CodeDecision(action="iterate", feedback="x" * 2001)
    with pytest.raises(ValueError):
        CodeDecision(action="push")  # type: ignore[arg-type]
