import pytest

from halo.core.approval import apply_grant, needs_approval
from halo.core.contracts import Step


def _step(risk: str, tool: str = "t") -> Step:
    return Step(tool=tool, args={}, risk=risk)  # type: ignore[arg-type]


def test_low_risk_steps_run_without_asking() -> None:
    assert not needs_approval(_step("low"), [])


def test_medium_risk_steps_ask_until_granted_for_the_task() -> None:
    assert needs_approval(_step("medium", "app.open"), [])
    assert not needs_approval(_step("medium", "app.open"), ["app.open"])
    assert needs_approval(_step("medium", "other"), ["app.open"])


def test_high_risk_steps_always_ask_even_if_the_tool_was_granted() -> None:
    assert needs_approval(_step("high", "app.open"), ["app.open"])


def test_deny_blocks_and_grants_nothing() -> None:
    allowed, granted = apply_grant("deny", _step("medium"), [])
    assert (allowed, granted) == (False, [])


def test_allow_once_runs_this_step_only() -> None:
    allowed, granted = apply_grant("allow_once", _step("medium", "x"), [])
    assert (allowed, granted) == (True, [])


def test_always_for_task_remembers_a_medium_tool() -> None:
    allowed, granted = apply_grant("always_for_task", _step("medium", "x"), ["y"])
    assert (allowed, granted) == (True, ["y", "x"])


def test_always_for_task_on_a_high_risk_step_is_only_allow_once() -> None:
    allowed, granted = apply_grant("always_for_task", _step("high", "x"), [])
    assert (allowed, granted) == (True, [])


def test_unknown_grant_values_are_rejected() -> None:
    with pytest.raises(ValueError):
        apply_grant("sure_why_not", _step("medium"), [])
