"""The window is exactly as big as the HUD, opaque, and cut to a rounded shape.

Transparency was tried first: a colour-keyed form makes every pixel the window
itself draws click-through (the web page is drawn by a separate layer), so clicks
fell through to the app behind. An opaque window with a rounded region keeps
clicks inside the shape and draws nothing outside it.
"""

from pathlib import Path
from typing import Any

import pytest

from halo.app import (
    BAR_HEIGHT,
    BAR_WIDTH,
    HudApi,
    corner_radius,
    page_url,
    window_options,
)


def test_the_window_can_shrink_to_the_bar() -> None:
    """pywebview defaults to a 200x100 minimum, which left a tall box around the
    260x44 bar. The minimum must be no bigger than the bar."""
    min_w, min_h = window_options(1536)["min_size"]
    assert min_w <= BAR_WIDTH
    assert min_h <= BAR_HEIGHT


def test_the_window_opens_as_the_bar_at_the_top_centre() -> None:
    options = window_options(1536)
    assert (options["x"], options["y"]) == ((1536 - BAR_WIDTH) // 2, 8)
    assert (options["width"], options["height"]) == (BAR_WIDTH, BAR_HEIGHT)


def test_the_window_is_frameless_on_top_and_opaque_in_the_hud_colour() -> None:
    options = window_options(1920)
    assert options["frameless"] is True
    assert options["on_top"] is True
    assert options["shadow"] is False
    # Opaque on purpose: a transparent window lets clicks fall through to the app behind.
    assert options["transparent"] is False
    assert options["background_color"].lower() == "#0b0c0f"


@pytest.mark.parametrize(
    ("size", "radius"),
    [((260, 44), 22), ((380, 140), 16), ((640, 360), 16)],
)
def test_the_corners_match_the_view(size: tuple[int, int], radius: int) -> None:
    """The bar is a full pill (half its height); the card and panel are softer boxes."""
    assert corner_radius(*size) == radius


# --- the shape follows every resize --------------------------------------------------


class _Window:
    def __init__(self) -> None:
        self.calls: list[tuple[str, int, int]] = []

    def resize(self, width: int, height: int) -> None:
        self.calls.append(("resize", width, height))

    def move(self, x: int, y: int) -> None:
        self.calls.append(("move", x, y))


def _api(shaper: Any, tmp_path: Path) -> tuple[HudApi, _Window]:
    window = _Window()
    return HudApi(window, (1536, 960), allowed_roots=[tmp_path], shaper=shaper), window


def test_the_window_is_reshaped_after_each_resize(tmp_path: Path) -> None:
    shaped: list[tuple[Any, int, int]] = []
    api, window = _api(
        lambda w, width, height: shaped.append((w, width, height)), tmp_path
    )
    api.resize(640, 360)
    api.resize(260, 44)
    assert shaped == [(window, 640, 360), (window, 260, 44)]


def test_the_shape_gets_the_size_after_clamping(tmp_path: Path) -> None:
    shaped: list[tuple[int, int]] = []
    api, _ = _api(lambda w, width, height: shaped.append((width, height)), tmp_path)
    api.resize(5000, 5000)
    assert shaped == [(800, 900)]


def test_garbage_sizes_neither_resize_nor_reshape(tmp_path: Path) -> None:
    shaped: list[tuple[int, int]] = []
    api, window = _api(
        lambda w, width, height: shaped.append((width, height)), tmp_path
    )
    api.resize("wide", 100)  # type: ignore[arg-type]
    assert shaped == []
    assert window.calls == []


def test_without_a_shaper_resizing_still_works(tmp_path: Path) -> None:
    api, window = _api(None, tmp_path)
    api.resize(260, 44)
    assert ("resize", 260, 44) in window.calls


# --- the page address ------------------------------------------------------------------


def test_the_page_url_carries_the_token_in_the_hash() -> None:
    assert page_url("http://127.0.0.1:9000", "tok", demo=False) == (
        "http://127.0.0.1:9000/#token=tok"
    )


def test_demo_mode_replays_the_scripted_tour_instead_of_the_live_stream() -> None:
    url = page_url("http://127.0.0.1:9000", "tok", demo=True)
    assert url.startswith("http://127.0.0.1:9000/#token=tok&")
    assert "mock=http://127.0.0.1:9000/demo/tour.jsonl" in url


def test_the_tour_ships_with_the_built_ui() -> None:
    """vite copies ui/public into ui/dist, so the packaged app has the tour too."""
    tour = Path(__file__).parent.parent / "ui" / "public" / "demo" / "tour.jsonl"
    assert tour.is_file()
    assert tour.read_text(encoding="utf-8").count("\n") > 30
