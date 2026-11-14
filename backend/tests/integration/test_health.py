"""API health and security-header integration tests."""

from fastapi.testclient import TestClient
from sqlalchemy.exc import SQLAlchemyError

from backend.app.api.v1.routes import health


def test_liveness_is_available(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_checks_database(client: TestClient) -> None:
    response = client.get("/health/ready")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_readiness_returns_safe_503_on_database_error(
    client: TestClient,
    monkeypatch,
) -> None:
    def fail_database_check(_engine) -> None:
        raise SQLAlchemyError("private connection details")

    monkeypatch.setattr(health, "check_database", fail_database_check)
    response = client.get("/health/ready")

    assert response.status_code == 503
    assert response.json() == {"status": "not_ready"}
    assert "private connection details" not in response.text


def test_liveness_does_not_depend_on_database(client: TestClient, monkeypatch) -> None:
    def fail_database_check(_engine) -> None:
        raise AssertionError("Liveness must not query the database")

    monkeypatch.setattr(health, "check_database", fail_database_check)
    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_response_has_baseline_security_headers(client: TestClient) -> None:
    response = client.get("/health/live")

    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"
    assert response.headers["referrer-policy"] == "no-referrer"
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["pragma"] == "no-cache"
    assert response.headers["x-request-id"]


def test_development_openapi_is_available(client: TestClient) -> None:
    response = client.get("/openapi.json")

    assert response.status_code == 200
    assert "/health/ready" in response.json()["paths"]
