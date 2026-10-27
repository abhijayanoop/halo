"""'let's get to work' through the whole app: no model call, answered in under 1.5 s."""

import time

import pytest


@pytest.mark.parametrize(
    "phrase", ["let's get to work", "Let's get started", "lets get to work"]
)
async def test_the_phrase_reaches_work_start_without_any_model_call(
    halo_cm_factory, phrase: str
) -> None:
    # No scripted model replies at all: any model call would fail the run.
    async with halo_cm_factory()() as halo:
        assert halo.memory is not None
        notes = halo.memory.vault / "Projects"
        notes.mkdir(parents=True, exist_ok=True)
        (notes / "halo.md").write_text(
            '---\nprivacy: shared\npath: C:/x\ntest_cmd: pytest\nlast_stop: "2026-10-27: kept: Add rate limiting"\n---\n# Halo\n',
            encoding="utf-8",
        )
        started = time.perf_counter()
        outcome = await halo.runner.run(phrase, run_id="r1")
        elapsed = time.perf_counter() - started

    assert outcome.result_status == "ok"
    result = outcome.results[0]["result"]
    assert outcome.results[0]["tool"] == "work.start"
    assert result["answer"].startswith("You stopped at: Add rate limiting")
    assert result["proposals"][0]["project"] == "halo"
    assert elapsed < 1.5
