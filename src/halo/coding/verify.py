"""Halo runs the project's tests itself, in the worktree, instead of trusting the
worker's report. The verdict is the exit code; the output is shown, never believed."""

import asyncio
import logging
import os
import re
import shlex
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

from halo.security.reader import wrap_untrusted
from halo.security.taint import Tainted

log = logging.getLogger(__name__)

DEFAULT_MAX_OUTPUT = 4000
_SECRET_NAME = re.compile(r"KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|PASSWD", re.IGNORECASE)


@dataclass(frozen=True)
class TestRun:
    __test__ = False  # not a pytest class

    passed: bool
    exit_code: int | None
    timed_out: bool
    output: Tainted[str]


def _clean_env() -> dict[str, str]:
    """The tests run user code: keep the environment but not Halo's own keys."""
    return {k: v for k, v in os.environ.items() if not _SECRET_NAME.search(k)}


async def _kill_tree(proc: asyncio.subprocess.Process) -> None:
    if proc.returncode is not None:
        return
    if sys.platform == "win32":
        killer = await asyncio.create_subprocess_exec(
            "taskkill",
            "/F",
            "/T",
            "/PID",
            str(proc.pid),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        await killer.wait()
    else:
        import signal

        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    try:
        await asyncio.wait_for(proc.wait(), 5)
    except TimeoutError:
        log.warning("test process did not exit after being killed")


async def _read_tail(stream: asyncio.StreamReader, keep: int) -> bytes:
    tail = b""
    while chunk := await stream.read(8192):
        tail = (tail + chunk)[-keep:]
    return tail


def _failed(reason: str) -> TestRun:
    return TestRun(False, None, False, wrap_untrusted(reason, source="test_run"))


async def run_tests(
    test_cmd: str,
    cwd: Path,
    *,
    timeout_s: float,
    max_output: int = DEFAULT_MAX_OUTPUT,
) -> TestRun:
    try:
        argv = shlex.split(test_cmd)
    except ValueError:
        return _failed("The test command could not be read.")
    if not argv:
        return _failed("There is no test command.")
    try:
        proc = await asyncio.create_subprocess_exec(
            *argv,
            cwd=cwd,
            env=_clean_env(),
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            start_new_session=sys.platform != "win32",
        )
    except OSError:
        return _failed("The test command could not be started.")

    assert proc.stdout is not None
    reader = asyncio.create_task(_read_tail(proc.stdout, max_output * 4))
    timed_out = False
    try:
        try:
            await asyncio.wait_for(proc.wait(), timeout_s)
        except TimeoutError:
            timed_out = True
            await _kill_tree(proc)
        raw = await asyncio.wait_for(reader, 10)
    finally:
        # Cancelled (Stop) or failed: never leave the tests running.
        await _kill_tree(proc)
        if not reader.done():
            reader.cancel()
    text = raw.decode("utf-8", errors="replace")[-max_output:]
    exit_code = None if timed_out else proc.returncode
    return TestRun(
        passed=exit_code == 0,
        exit_code=exit_code,
        timed_out=timed_out,
        output=wrap_untrusted(text, source="test_run"),
    )
