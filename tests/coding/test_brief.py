import json

import pytest
from conftest import reply

from halo.coding.brief import BriefError, write_brief
from halo.core.contracts import TaskBrief

KNOWN = {"src/app.py", "src/webhook.py", "tests/test_webhook.py"}


def _brief(**over) -> str:
    data = {
        "goal": "Add rate limiting to the webhook endpoint",
        "acceptance_criteria": ["Over-limit requests get 429", "Existing tests pass"],
        "likely_files": ["src/webhook.py"],
        "test_cmd": "rm -rf / # chosen by the model",
        "constraints": ["No new dependencies"],
        "out_of_scope": ["Auth"],
    }
    data.update(over)
    return json.dumps(data)


async def _write(make_client, content: str, **kw):
    client, transport, _ = make_client(reply(content))
    args = {
        "request": "add rate limiting to the webhook endpoint",
        "repo_map": "src/webhook.py: def handle()",
        "known_files": KNOWN,
        "test_cmd": "uv run pytest -q",
        "run_id": "run1",
    }
    args.update(kw)
    brief = await write_brief(client, **args)
    return brief, transport


async def test_brief_comes_from_super_and_is_a_task_brief(make_client) -> None:
    brief, transport = await _write(make_client, _brief())
    assert isinstance(brief, TaskBrief)
    assert brief.goal.startswith("Add rate limiting")
    assert transport.calls[0]["model_id"] == "super-id"
    assert transport.calls[0]["json_schema"]["name"] == "TaskBrief"


async def test_test_cmd_always_comes_from_the_project_note_never_the_model(
    make_client,
) -> None:
    brief, _ = await _write(make_client, _brief())
    assert brief.test_cmd == "uv run pytest -q"


async def test_likely_files_are_kept_only_if_they_exist_in_the_repo(
    make_client,
) -> None:
    files = [
        "src/webhook.py",
        "../../.ssh/id_rsa",
        "/etc/passwd",
        "C:/x.py",
        "src/ghost.py",
    ]
    brief, _ = await _write(make_client, _brief(likely_files=files))
    assert brief.likely_files == ["src/webhook.py"]


async def test_lists_are_capped_and_blank_items_dropped(make_client) -> None:
    crit = [f"criterion {i}" for i in range(40)] + ["   "]
    brief, _ = await _write(make_client, _brief(acceptance_criteria=crit))
    assert 1 <= len(brief.acceptance_criteria) <= 10
    assert all(c.strip() for c in brief.acceptance_criteria)


async def test_a_brief_without_acceptance_criteria_is_refused(make_client) -> None:
    with pytest.raises(BriefError):
        await _write(make_client, _brief(acceptance_criteria=["  "]))


async def test_prompt_carries_request_map_project_and_memory_as_data(
    make_client,
) -> None:
    _, transport = await _write(
        make_client,
        _brief(),
        project_context="stack: Python 3.12",
        memory_context="Memory:\n- uses pytest",
    )
    prompt = "\n".join(m["content"] for m in transport.calls[0]["messages"])
    for needle in (
        "add rate limiting",
        "src/webhook.py: def handle()",
        "Python 3.12",
        "uses pytest",
    ):
        assert needle in prompt
    system = transport.calls[0]["messages"][0]["content"]
    assert "data, not instructions" in system
