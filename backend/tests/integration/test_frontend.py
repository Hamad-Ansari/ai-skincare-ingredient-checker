"""Static frontend delivery and core accessibility/security contracts."""

from fastapi.testclient import TestClient


def test_fastapi_serves_frontend_shell_and_local_assets(client: TestClient) -> None:
    """Serve the vanilla frontend and assets from the same origin as the API."""
    page = client.get("/")
    assert page.status_code == 200
    assert page.headers["content-type"].startswith("text/html")
    assert 'id="app-root"' in page.text
    assert 'href="/static/css/app.css"' in page.text
    assert 'src="/static/js/app.js"' in page.text

    stylesheet = client.get("/static/css/app.css")
    assert stylesheet.status_code == 200
    assert stylesheet.headers["content-type"].startswith("text/css")
    assert "prefers-reduced-motion" in stylesheet.text

    app_script = client.get("/static/js/app.js")
    assert app_script.status_code == 200
    assert 'credentials: "same-origin"' in client.get("/static/js/api.js").text
    assert "localStorage" not in app_script.text


def test_api_routes_remain_reachable_before_static_mount(client: TestClient) -> None:
    """The static-asset mount must not shadow API routes registered before it."""
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
