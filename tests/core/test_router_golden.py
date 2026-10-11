"""The router's golden set. The structure test runs offline; the accuracy test
calls live Nano and costs credits, so it is marked `live`."""

from collections import Counter
from pathlib import Path
from typing import get_args

import pytest
import yaml

from halo.core.contracts import SkillName

GOLDEN = Path(__file__).resolve().parents[2] / "evals" / "router_golden.yaml"


def _cases() -> list[dict]:
    return yaml.safe_load(GOLDEN.read_text(encoding="utf-8"))


def test_golden_set_has_20_cases_5_of_them_ambiguous() -> None:
    cases = _cases()
    assert len(cases) == 20
    assert sum(1 for c in cases if c.get("ambiguous")) == 5


def test_every_case_names_a_real_skill_and_utterances_are_unique() -> None:
    cases = _cases()
    skills = set(get_args(SkillName))
    assert all(c["skill"] in skills for c in cases)
    utterances = [c["utterance"] for c in cases]
    assert len(set(utterances)) == len(utterances)


def test_every_skill_appears_in_the_golden_set() -> None:
    covered = Counter(c["skill"] for c in _cases())
    assert set(covered) == set(get_args(SkillName))


@pytest.mark.live
async def test_router_scores_at_least_18_of_20_on_live_nano() -> None:
    from halo.config import load_config
    from halo.core.router import route
    from halo.models.client import build_client

    client = build_client(load_config())
    cases = _cases()
    hits = 0
    misses = []
    for case in cases:
        intent = await route(client, case["utterance"])
        if intent.skill == case["skill"]:
            hits += 1
        else:
            misses.append((case["utterance"], case["skill"], intent.skill))
    assert hits >= 18, f"{hits}/20; misses: {misses}"
