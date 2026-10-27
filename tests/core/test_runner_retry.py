"""A retried run announces itself, so the HUD and the mood engine drop the old
failure instead of showing it while the retry works."""

from halo.models.transport import ModelRequestError


async def test_retry_starts_the_run_again_with_the_original_request(
    open_runner,
) -> None:
    async with open_runner(*[ModelRequestError("HTTP 400")] * 3) as (
        runner,
        events,
        *_,
    ):
        await runner.run("open vscode", run_id="r1")
        events.clear()
        await runner.retry("r1")

    started = [e for e in events if e.type == "run.started"]
    assert len(started) == 1
    assert started[0].run_id == "r1"
    assert started[0].payload["request"] == "open vscode"
    assert started[0].payload["retry"] is True
    # The announcement comes before anything else the retry does.
    assert events[0].type == "run.started"


async def test_a_first_run_is_not_marked_as_a_retry(open_runner) -> None:
    async with open_runner(ModelRequestError("HTTP 400")) as (runner, events, *_):
        await runner.run("open vscode", run_id="r2")
    first = next(e for e in events if e.type == "run.started")
    assert "retry" not in first.payload
