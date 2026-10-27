"""The built HUD is served by the same local server, so the page and the API
share one origin (no CORS, no file:// null Origin)."""

from pathlib import Path

from starlette.testclient import TestClient

from halo.api.server import create_app


def _client(halo_cm_factory, dist: Path | None) -> TestClient:
    app = create_app(halo_cm_factory(), token="tok", static_dir=dist)
    return TestClient(app, base_url="http://127.0.0.1:8000")


def test_the_page_and_its_assets_are_served_without_a_token(
    halo_cm_factory, tmp_path: Path
) -> None:
    (tmp_path / "assets").mkdir()
    (tmp_path / "index.html").write_text("<html>halo hud</html>")
    (tmp_path / "assets" / "app.js").write_text("console.log(1)")

    with _client(halo_cm_factory, tmp_path) as client:
        assert "halo hud" in client.get("/").text
        assert client.get("/assets/app.js").status_code == 200


def test_the_api_routes_still_win_over_the_static_files(
    halo_cm_factory, tmp_path: Path
) -> None:
    (tmp_path / "index.html").write_text("<html>halo hud</html>")
    with _client(halo_cm_factory, tmp_path) as client:
        assert client.get("/health").json() == {"ok": True}
        assert client.post("/run", json={"request": "x"}).status_code == 401


def test_without_a_static_dir_the_root_is_not_found(halo_cm_factory) -> None:
    with _client(halo_cm_factory, None) as client:
        assert client.get("/").status_code == 404


def test_static_files_cannot_be_used_to_read_outside_the_folder(
    halo_cm_factory, tmp_path: Path
) -> None:
    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "index.html").write_text("ok")
    (tmp_path / "secret.txt").write_text("secret")
    with _client(halo_cm_factory, dist) as client:
        assert "secret" not in client.get("/..%2fsecret.txt").text
        assert "secret" not in client.get("/../secret.txt").text
