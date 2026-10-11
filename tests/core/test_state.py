import operator
from typing import get_type_hints

from halo.core.state import HaloState, initial_state


def test_initial_state_has_the_request_and_empty_everything_else() -> None:
    state = initial_state("run1", "open vs code")
    assert state["run_id"] == "run1"
    assert state["request"] == "open vs code"
    assert state["intent"] is None
    assert state["plan"] is None
    assert state["pending_approval"] is None
    assert state["results"] == []
    assert state["messages"] == []


def test_initial_states_do_not_share_lists() -> None:
    a = initial_state("a", "x")
    b = initial_state("b", "y")
    a["results"].append({"ok": True})
    assert b["results"] == []


def test_results_and_messages_accumulate_across_nodes() -> None:
    hints = get_type_hints(HaloState, include_extras=True)
    for key in ("results", "messages"):
        assert operator.add in hints[key].__metadata__
