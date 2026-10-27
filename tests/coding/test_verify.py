import sys
from pathlib import Path

import pytest

from halo.coding.verify import run_tests
from halo.security.taint import Tainted


def _py(code: str) -> str:
    # forward slashes keep the interpreter path intact under shlex on Windows
    return f'"{Path(sys.executable).as_posix()}" -c "{code}"'


async def test_exit_code_zero_is_a_pass(tmp_path: Path) -> None:
    out = await run_tests(_py("print('5 passed')"), tmp_path, timeout_s=30)
    assert out.passed and out.exit_code == 0 and not out.timed_out
    assert isinstance(out.output, Tainted) and "5 passed" in out.output.value


async def test_the_verdict_comes_from_the_exit_code_not_from_the_text(
    tmp_path: Path,
) -> None:
    out = await run_tests(
        _py("print('ALL TESTS PASSED'); raise SystemExit(1)"), tmp_path, timeout_s=30
    )
    assert not out.passed and out.exit_code == 1


async def test_a_run_that_prints_nothing_but_exits_zero_passes(tmp_path: Path) -> None:
    out = await run_tests(_py("pass"), tmp_path, timeout_s=30)
    assert out.passed


async def test_a_timeout_is_a_failure_and_stops_the_process(tmp_path: Path) -> None:
    marker = tmp_path / "late.txt"
    code = (
        "import time,pathlib;time.sleep(5);"
        f"pathlib.Path(r'{marker.as_posix()}').write_text('x')"
    )
    out = await run_tests(_py(code), tmp_path, timeout_s=0.5)
    assert out.timed_out and not out.passed and out.exit_code is None
    import asyncio

    await asyncio.sleep(0.5)
    assert not marker.exists()


async def test_a_command_that_does_not_exist_is_a_failure_not_a_crash(
    tmp_path: Path,
) -> None:
    out = await run_tests("definitely-not-a-program-xyz --flag", tmp_path, timeout_s=5)
    assert not out.passed and out.exit_code is None


async def test_output_is_capped_cleaned_and_tainted(tmp_path: Path) -> None:
    out = await run_tests(
        _py("print('A'*50000); print('last-line')"),
        tmp_path,
        timeout_s=30,
        max_output=1000,
    )
    assert len(out.output.value) <= 1000
    assert "last-line" in out.output.value  # the tail is what matters
    assert out.output.source == "test_run"


async def test_secrets_in_the_environment_do_not_reach_the_tests(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NVIDIA_API_KEY", "nvapi-secret-value")
    monkeypatch.setenv("NEBIUS_TOKEN", "tok-secret-value")
    monkeypatch.setenv("HARMLESS_SETTING", "visible")
    code = "import os;print(os.environ.get('NVIDIA_API_KEY'), os.environ.get('NEBIUS_TOKEN'), os.environ.get('HARMLESS_SETTING'))"
    out = await run_tests(_py(code), tmp_path, timeout_s=30)
    assert "secret" not in out.output.value
    assert "visible" in out.output.value


async def test_an_empty_command_is_refused(tmp_path: Path) -> None:
    out = await run_tests("   ", tmp_path, timeout_s=5)
    assert not out.passed and out.exit_code is None
