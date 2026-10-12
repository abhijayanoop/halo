"""The desktop shell: the local API on a background thread, and a frameless,
always-on-top pywebview window showing the HUD.

The window is the only thing that needs pywebview, so it is imported inside
main(); everything else here is plain Python and testable on its own.
"""

import importlib
import logging
import math
import os
import secrets
import socket
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any, Protocol

import uvicorn
from fastapi import FastAPI
from rich.console import Console

from halo.bootstrap import default_home, open_halo
from halo.config import load_config, load_env

logger = logging.getLogger(__name__)

BAR_WIDTH, BAR_HEIGHT, BAR_TOP = 260, 44, 8
MIN_SIZE = (200, 40)
MAX_SIZE = (800, 900)
MIN_VISIBLE = (100, 40)  # how much of the window must stay on screen
DEV_API_PORT = 8765  # the Vite dev server proxies to this port


class Window(Protocol):
    def resize(self, width: int, height: int) -> None: ...
    def move(self, x: int, y: int) -> None: ...


def bar_geometry(screen_width: int) -> tuple[int, int, int, int]:
    """(x, y, width, height) of the collapsed bar: top centre, 8 px from the edge."""
    return (screen_width - BAR_WIDTH) // 2, BAR_TOP, BAR_WIDTH, BAR_HEIGHT


def _whole(value: object) -> int | None:
    """The page's number as an int, or None if it is not a whole finite number."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        return int(value)
    return None


def _clamp(value: int, low: int, high: int) -> int:
    return max(low, min(high, value))


def _launch(argv: list[str]) -> None:
    """Hand a path to the OS. An argument list, never a shell string."""
    if sys.platform == "win32":
        os.startfile(argv[-1])  # pyright: ignore[reportAttributeAccessIssue]
    else:
        subprocess.Popen(argv, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL)


class HudApi:
    """What the page may call as `window.pywebview.api`. Everything the page
    sends is untrusted: sizes are clamped, paths must sit inside an allowed
    root. Public methods are exposed to JavaScript, so helpers start with `_`."""

    def __init__(
        self,
        window: Window | None,
        screen: tuple[int, int],
        *,
        allowed_roots: Sequence[Path] | None = None,
        launcher: Callable[[list[str]], None] = _launch,
    ) -> None:
        self._window = window
        self._screen = screen
        self._roots = [root.resolve() for root in (allowed_roots or [default_home()])]
        self._launcher = launcher

    def _attach(self, window: Window) -> None:
        self._window = window

    def resize(self, width: int, height: int) -> None:
        """Resize in place: the window keeps its top edge and stays centred."""
        w, h = _whole(width), _whole(height)
        if self._window is None or w is None or h is None:
            return
        w = _clamp(w, MIN_SIZE[0], MAX_SIZE[0])
        h = _clamp(h, MIN_SIZE[1], MAX_SIZE[1])
        self._window.resize(w, h)
        self._window.move((self._screen[0] - w) // 2, BAR_TOP)

    def move(self, x: int, y: int) -> None:
        px, py = _whole(x), _whole(y)
        if self._window is None or px is None or py is None:
            return
        self._window.move(
            _clamp(px, 0, self._screen[0] - MIN_VISIBLE[0]),
            _clamp(py, 0, self._screen[1] - MIN_VISIBLE[1]),
        )

    def open_path(self, path: str) -> bool:
        """Open a file or folder with the OS default app, only if it exists and
        sits inside an allowed root (symlinks and `..` are resolved first)."""
        if not isinstance(path, str) or not path.strip():
            return False
        raw = Path(path)
        if not raw.is_absolute():
            return False
        try:
            target = raw.resolve(strict=True)
        except OSError:
            return False
        if not any(target.is_relative_to(root) for root in self._roots):
            logger.warning("refused to open a path outside the allowed folders")
            return False
        resolved = str(target)
        argv = {"darwin": ["open", resolved], "win32": [resolved]}.get(
            sys.platform, ["xdg-open", resolved]
        )
        self._launcher(argv)
        return True


def free_port() -> int:
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def ui_dist_dir() -> Path:
    """The built HUD: $HALO_UI_DIST, else ui/dist in the repository."""
    if given := os.environ.get("HALO_UI_DIST"):
        return Path(given)
    return Path(__file__).resolve().parents[2] / "ui" / "dist"


class ServerThread(threading.Thread):
    """Runs uvicorn on a background thread; `start()` returns once it accepts."""

    def __init__(self, app: FastAPI, port: int) -> None:
        super().__init__(name="halo-api", daemon=True)
        self.port = port
        self._server = uvicorn.Server(
            uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning")
        )

    @property
    def url(self) -> str:
        return f"http://127.0.0.1:{self.port}"

    def run(self) -> None:
        self._server.run()

    def start(self, timeout: float = 20.0) -> None:
        super().start()
        deadline = time.monotonic() + timeout
        while not self._server.started:
            if not self.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("the local API did not start")
            time.sleep(0.02)

    def stop(self, timeout: float = 10.0) -> None:
        self._server.should_exit = True
        self.join(timeout)


def main() -> int:

    console = Console(stderr=True)
    load_env()
    config = load_config()

    dev_url = os.environ.get("HALO_UI_URL")
    dist = ui_dist_dir()
    if not dev_url and not (dist / "index.html").is_file():
        console.print("The HUD is not built. Run: cd ui && npm ci && npm run build")
        return 1
    try:
        webview: Any = importlib.import_module("webview")
    except ImportError:
        console.print("pywebview is not installed. Run: uv add pywebview")
        return 1

    from halo.api.server import create_app

    token = secrets.token_urlsafe(32)
    app = create_app(
        lambda: open_halo(config), token=token, static_dir=None if dev_url else dist
    )
    server = ServerThread(app, DEV_API_PORT if dev_url else free_port())
    server.start()

    page = f"{dev_url or server.url}/#token={token}"
    screen = webview.screens[0]
    api = HudApi(None, (screen.width, screen.height))
    x, y, w, h = bar_geometry(screen.width)
    window = webview.create_window(
        "Halo",
        url=page,
        width=w,
        height=h,
        x=x,
        y=y,
        frameless=True,
        on_top=True,
        easy_drag=True,
        js_api=api,
    )
    api._attach(window)  # pyright: ignore[reportPrivateUsage]
    try:
        webview.start()
    finally:
        server.stop()
    return 0


def entry() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    entry()
