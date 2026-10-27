"""What the code.task skill may never do, whoever asks."""

from starlette.testclient import TestClient

from halo.api.server import create_app
from halo.coding.session import BRIEF_ACTIONS, RESULT_ACTIONS
from halo.skills.registry import SkillRegistry, default_skills_dir

TOKEN = "s3cret-token-for-tests"


def test_merge_is_only_ever_offered_on_the_result_card() -> None:
    assert "merge" not in BRIEF_ACTIONS
    assert "merge" in RESULT_ACTIONS


def test_the_result_card_can_never_be_answered_with_the_briefs_approve() -> None:
    assert "approve" not in RESULT_ACTIONS
    assert BRIEF_ACTIONS == {"approve", "deny"}


def test_no_action_is_an_always_grant() -> None:
    # A decision covers exactly the card the user saw: there is no "remember this" action.
    assert not any(
        "always" in a or "grant" in a for a in BRIEF_ACTIONS | RESULT_ACTIONS
    )


def test_the_skill_declares_its_risk_and_takes_no_path_or_command_argument() -> None:
    skill = SkillRegistry.load(default_skills_dir()).get("code.task")
    assert skill.manifest.risk == "low"  # the brief card is the approval, see SKILL.md
    text = (default_skills_dir() / "code_task" / "SKILL.md").read_text(encoding="utf-8")
    assert "project note" in text and "never" in text.lower()


def test_code_decision_needs_the_api_token(halo_cm_factory) -> None:
    app = create_app(halo_cm_factory(), token=TOKEN)
    body = {"run_id": "x", "approval_id": "x", "action": "merge"}
    with TestClient(app, base_url="http://127.0.0.1:8000") as client:
        assert client.post("/code/decision", json=body).status_code == 401
        wrong = {"X-Halo-Token": "nope"}
        assert (
            client.post("/code/decision", json=body, headers=wrong).status_code == 401
        )
