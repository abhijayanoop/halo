"""The desktop shell: window geometry, the js_api the page can call, and the
local server thread. The webview itself is never imported here."""

import json
import sys
from pathlib import Path

import httpx2 as httpx
import pytest
from conftest import reply

from halo.api.server import create_app
from halo.app import HudApi, ServerThread, bar_geometry, free_port, ui_dist_dir


class FakeWindow:
    def __init__(self) -> None:
        self.resized: list[tuple[int, int]] = []
        self.moved: list[tuple[int, int]] = []

    def resize(self, width: int, height: int) -> None:
        self.resized.append((width, height))

    def move(self, x: int, y: int) -> None:
        self.moved.append((x, y))


SCREEN = (1536, 960)


def _api(
    tmp_path: Path, launched: list[list[str]] | None = None
) -> tuple[HudApi, FakeWindow]:
    window = FakeWindow()
    api = HudApi(
        window,
        SCREEN,
        allowed_roots=[tmp_path / "allowed"],
        launcher=(launched.append if launched is not None else lambda argv: None),
    )
    return api, window


def test_the_collapsed_bar_sits_top_centre_8px_from_the_edge() -> None:
    assert bar_geometry(1536) == (638, 8, 260, 44)
    assert bar_geometry(1920)[0] == (1920 - 260) // 2


def test_resize_keeps_the_window_centred_at_the_top(tmp_path: Path) -> None:
    api, window = _api(tmp_path)
    api.resize(420, 600)
    assert window.resized == [(420, 600)]
    assert window.moved == [((1536 - 420) // 2, 8)]


@pytest.mark.parametrize(
    ("asked", "expected"),
    [((5000, 5000), (800, 900)), ((1, 1), (200, 40)), ((380, 140), (380, 140))],
)
def test_resize_is_clamped_to_sane_sizes(
    tmp_path: Path, asked: tuple[int, int], expected: tuple[int, int]
) -> None:
    api, window = _api(tmp_path)
    api.resize(*asked)
    assert window.resized == [expected]


@pytest.mark.parametrize("bad", ["wide", None, 3.5, True, float("nan")])
def test_resize_ignores_garbage_from_the_page(tmp_path: Path, bad) -> None:
    api, window = _api(tmp_path)
    api.resize(bad, 100)
    api.resize(100, bad)
    assert window.resized == []


def test_move_stays_on_screen(tmp_path: Path) -> None:
    api, window = _api(tmp_path)
    api.move(-500, -500)
    api.move(99999, 99999)
    assert window.moved == [(0, 0), (SCREEN[0] - 100, SCREEN[1] - 40)]


def test_open_path_opens_a_file_inside_an_allowed_root(tmp_path: Path) -> None:
    root = tmp_path / "allowed"
    root.mkdir()
    note = root / "note.md"
    note.write_text("hi")
    launched: list[list[str]] = []
    api, _ = _api(tmp_path, launched)

    assert api.open_path(str(note)) is True
    assert len(launched) == 1
    assert launched[0][-1] == str(note.resolve())


@pytest.mark.parametrize(
    "how", ["outside", "traversal", "missing", "relative", "blank"]
)
def test_open_path_refuses_anything_outside_the_allowed_roots(
    tmp_path: Path, how: str
) -> None:
    root = tmp_path / "allowed"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("x")
    target = {
        "outside": str(outside),
        "traversal": str(root / ".." / "secret.txt"),
        "missing": str(root / "nope.md"),
        "relative": "note.md",
        "blank": "  ",
    }[how]
    launched: list[list[str]] = []
    api, _ = _api(tmp_path, launched)

    assert api.open_path(target) is False
    assert launched == []


@pytest.mark.skipif(
    sys.platform == "win32", reason="symlinks need privileges on Windows"
)
def test_open_path_refuses_a_symlink_that_leaves_the_allowed_root(
    tmp_path: Path,
) -> None:
    root = tmp_path / "allowed"
    root.mkdir()
    outside = tmp_path / "secret.txt"
    outside.write_text("x")
    (root / "link.txt").symlink_to(outside)
    launched: list[list[str]] = []
    api, _ = _api(tmp_path, launched)

    assert api.open_path(str(root / "link.txt")) is False
    assert launched == []


def test_open_path_refuses_something_that_is_not_a_string(tmp_path: Path) -> None:
    api, _ = _api(tmp_path)
    assert api.open_path(None) is False  # type: ignore[arg-type]
    assert api.open_path(["a"]) is False  # type: ignore[arg-type]


def test_free_port_returns_a_port_nothing_is_listening_on() -> None:
    port = free_port()
    assert 1024 < port < 65536


def test_ui_dist_dir_prefers_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("HALO_UI_DIST", str(tmp_path))
    assert ui_dist_dir() == tmp_path


async def test_the_server_thread_serves_the_api_and_stops_cleanly(
    halo_cm_factory, tmp_path: Path
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("<html>halo</html>")
    app = create_app(halo_cm_factory(reply(json.dumps({}))), token="t", static_dir=dist)
    server = ServerThread(app, free_port())

    server.start()
    try:
        async with httpx.AsyncClient(base_url=server.url) as client:
            assert (await client.get("/health")).json() == {"ok": True}
            assert "halo" in (await client.get("/")).text
            assert (await client.post("/run", json={"request": "x"})).status_code == 401
    finally:
        server.stop()
    assert not server.is_alive()


# --- found in review: lexical checks before the filesystem is touched -------


@pytest.mark.parametrize(
    "path",
    [
        r"\\attacker\share\x.md",
        "//attacker/share/x.md",
        r"\\?\C:\x.md",
        r"\\.\pipe\x",
    ],
)
def test_open_path_refuses_network_paths_without_touching_them(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, path: str
) -> None:
    def boom(self, *args, **kwargs):
        raise AssertionError("resolved a network path: that would connect to it")

    launched: list[list[str]] = []
    api = HudApi(
        FakeWindow(), SCREEN, allowed_roots=[tmp_path], launcher=launched.append
    )
    monkeypatch.setattr(Path, "resolve", boom)

    assert api.open_path(path) is False
    assert launched == []


@pytest.mark.parametrize(
    "name", ["run.exe", "setup.cmd", "x.bat", "y.ps1", "z.lnk", "noext"]
)
def test_open_path_only_opens_documents_not_programs(tmp_path: Path, name: str) -> None:
    root = tmp_path / "allowed"
    root.mkdir()
    (root / name).write_text("x")
    launched: list[list[str]] = []
    api, _ = _api(tmp_path, launched)

    assert api.open_path(str(root / name)) is False
    assert launched == []
