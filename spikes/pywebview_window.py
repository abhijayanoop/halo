"""Spike: pywebview frameless, always-on-top window, resized from JS.

Question: can pywebview create a frameless, always-on-top window at
260x44 top-centre on Windows, and can a JS call resize it to 420x600
live, without flicker or losing always-on-top?

Usage:
    uv run --with pywebview python spikes/pywebview_window.py

What to look for (report back, since I can't see your screen):
  1. Does the window appear frameless (no title bar/border) at roughly
     260x44px, horizontally centred, near the top of the screen?
  2. Does it stay on top of other windows (click another app, the window
     should stay visible on top)?
  3. Click the "Resize to HUD" link - does it grow to 420x600 in place,
     still frameless and on top, without flicker?
  4. Any square corners where you'd expect rounded ones (set by the HTML's
     border-radius, not the OS window), or any flicker on resize, is worth
     noting even if resize technically works.
  5. Close the window (or Ctrl+C in the terminal) when you're done looking.

Throwaway spike code. Never import this from halo/.
"""

import webview

HTML = """
<!doctype html>
<html>
<body style="margin:0;background:#1a1a1a;color:#eee;font-family:sans-serif;
             display:flex;align-items:center;justify-content:center;height:100vh;
             border-radius:12px;overflow:hidden;">
  <a id="resize-link" href="#" style="color:#9cf;font-size:13px;">Resize to HUD (420x600)</a>
  <script>
    window.addEventListener('pywebviewready', function () {
      document.getElementById('resize-link').addEventListener('click', function (e) {
        e.preventDefault();
        window.pywebview.api.resize();
      });
    });
  </script>
</body>
</html>
"""


class Api:
    def resize(self) -> None:
        webview.windows[0].resize(420, 600)


def main() -> None:
    screen = webview.screens[0]
    bar_w, bar_h = 260, 44
    x = (screen.width - bar_w) // 2
    y = 8

    webview.create_window(
        "Halo spike",
        html=HTML,
        width=bar_w,
        height=bar_h,
        x=x,
        y=y,
        frameless=True,
        on_top=True,
        easy_drag=True,
        js_api=Api(),
    )
    webview.start(debug=False)


if __name__ == "__main__":
    main()
