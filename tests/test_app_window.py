"""The window must be able to be exactly as small as the bar, and see through to the desktop."""

from halo.app import BAR_HEIGHT, BAR_WIDTH, make_form_see_through, window_options


def test_the_window_can_shrink_to_the_bar() -> None:
    """pywebview defaults to a 200x100 minimum, which left a tall grey box around
    the 260x44 bar. The minimum must be no bigger than the bar."""
    options = window_options(1536)
    min_w, min_h = options["min_size"]
    assert min_w <= BAR_WIDTH
    assert min_h <= BAR_HEIGHT


def test_the_window_opens_as_the_bar_at_the_top_centre() -> None:
    options = window_options(1536)
    assert (options["x"], options["y"]) == ((1536 - BAR_WIDTH) // 2, 8)
    assert (options["width"], options["height"]) == (BAR_WIDTH, BAR_HEIGHT)


def test_the_window_is_frameless_on_top_and_transparent() -> None:
    options = window_options(1920)
    assert options["frameless"] is True
    assert options["on_top"] is True
    assert options["transparent"] is True
    assert options["shadow"] is False  # a native shadow would draw a box round the pill


class _Form:
    BackColor = None
    TransparencyKey = None


def test_the_form_behind_the_page_is_keyed_transparent() -> None:
    """The web view is transparent, but the form under it paints grey unless its
    back colour is also its transparency key."""
    form = _Form()
    make_form_see_through(form, "KEY")
    assert form.BackColor == "KEY"
    assert form.TransparencyKey == "KEY"


def test_the_page_url_carries_the_token_in_the_hash() -> None:
    from halo.app import page_url

    assert page_url("http://127.0.0.1:9000", "tok", demo=False) == (
        "http://127.0.0.1:9000/#token=tok"
    )


def test_demo_mode_replays_the_scripted_tour_instead_of_the_live_stream() -> None:
    from halo.app import page_url

    url = page_url("http://127.0.0.1:9000", "tok", demo=True)
    assert url.startswith("http://127.0.0.1:9000/#token=tok&")
    assert "mock=http://127.0.0.1:9000/demo/tour.jsonl" in url


def test_the_tour_ships_with_the_built_ui() -> None:
    """vite copies ui/public into ui/dist, so the packaged app has the tour too."""
    from pathlib import Path

    tour = Path(__file__).parent.parent / "ui" / "public" / "demo" / "tour.jsonl"
    assert tour.is_file()
    assert tour.read_text(encoding="utf-8").count("\n") > 30
