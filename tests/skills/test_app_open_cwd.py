"""A program planted in the current directory must never be what "open VS Code"
runs. On Windows the shell search looks in the working directory first."""

import sys
from pathlib import Path

import pytest

from halo.skills.app_open import skill as app_open

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="cwd-first search is a Windows behaviour"
)


async def test_a_program_in_the_working_directory_is_not_launched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "pwned.txt"
    (tmp_path / "plantedtool.cmd").write_text(f'@echo off\r\necho x> "{marker}"\r\n')
    monkeypatch.chdir(tmp_path)

    with pytest.raises(FileNotFoundError):
        await app_open._spawn(["plantedtool"])

    assert not marker.exists()


async def test_a_program_found_on_path_still_launches(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    marker = tmp_path / "ran.txt"
    (bin_dir / "goodtool.cmd").write_text(f'@echo off\r\necho x> "{marker}"\r\n')
    monkeypatch.setenv("PATH", str(bin_dir) + ";" + __import__("os").environ["PATH"])
    monkeypatch.chdir(tmp_path)

    await app_open._spawn(["goodtool"])

    for _ in range(50):
        if marker.exists():
            break
        await __import__("asyncio").sleep(0.1)
    assert marker.exists()
