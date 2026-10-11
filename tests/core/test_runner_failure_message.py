"""run.failed goes to the JSONL file and the /events stream, so it must carry a
fixed, safe message, never text echoed back from the model provider."""

from halo.models.transport import ModelRequestError


async def test_provider_error_text_never_reaches_the_failed_event(open_runner) -> None:
    secret = "provider echoed: Bearer abc123 and the prompt text"
    async with open_runner(ModelRequestError(f"HTTP 400: {secret}")) as (
        runner,
        events,
        *_,
    ):
        outcome = await runner.run("open vscode", run_id="r1")

    assert outcome.state == "failed"
    failed = [e for e in events if e.type == "run.failed"]
    assert len(failed) == 1
    assert secret not in str(failed[0].payload)
    assert "abc123" not in str(failed[0].payload)
    assert secret not in (outcome.error or "")
    assert failed[0].payload["reason"]  # still a plain-language reason
    assert failed[0].payload["error_type"] == "ModelRequestError"


async def test_each_failure_kind_gets_its_own_plain_reason(open_runner) -> None:
    from halo.models.transport import TransientModelError

    async with open_runner(*[TransientModelError("503")] * 8) as (runner, events, *_):
        await runner.run("open vscode", run_id="r2")
    reason = next(e for e in events if e.type == "run.failed").payload["reason"]
    assert "model" in reason.lower()
