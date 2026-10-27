import pytest
from conftest import FakeContext

from halo.core.context import HaloContext
from halo.skills.registry import SkillRegistry, default_skills_dir


@pytest.fixture(scope="module")
def skill():
    return SkillRegistry.load(default_skills_dir()).get("code.task")


def test_the_skill_is_registered_with_its_manifest(skill) -> None:
    assert skill.manifest.name == "code.task"
    assert skill.manifest.risk == "low"
    assert (
        "project" in skill.manifest.description.lower()
        or "code" in skill.manifest.description.lower()
    )


async def test_it_needs_a_halo_context(skill) -> None:
    with pytest.raises(TypeError):
        await skill.module.run(FakeContext(), {"task": "x"})


async def test_without_coding_set_up_it_says_so(skill, make_client) -> None:
    client, transport, _ = make_client()
    ctx = HaloContext("run1", lambda e: None, client)
    out = await skill.module.run(ctx, {"task": "add a thing"})
    assert "error" in out
    assert transport.calls == []
