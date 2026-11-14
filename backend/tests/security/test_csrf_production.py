"""Production-only CSRF and secure-cookie configuration tests."""

from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.main import create_app
from backend.app.models.accounts import User
from backend.app.services.auth.passwords import hash_password

PRODUCTION_SETTINGS = {
    "app_env": "production",
    "app_secret_key": "a stable secret with more than thirty two characters",
    "database_url": "postgresql+psycopg://user:password@localhost/clarity",
    "mail_host": "smtp.example.com",
    "mail_from": "no-reply@example.com",
}
PASSWORD = "correct horse battery staple"


def test_production_unsafe_requests_require_an_origin(test_engine: Engine) -> None:
    settings = Settings(**PRODUCTION_SETTINGS)
    app = create_app(settings=settings, db_engine=test_engine)
    with TestClient(app, base_url="https://testserver") as client:
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        response = client.post(
            "/api/v1/auth/register",
            json={"email": "secure@example.com", "password": PASSWORD},
            headers={"X-CSRF-Token": csrf},
        )

    assert response.status_code == 403
    assert response.json()["detail"]["code"] == "origin_required"


def test_production_frontend_has_a_restrictive_content_security_policy(test_engine: Engine) -> None:
    app = create_app(settings=Settings(**PRODUCTION_SETTINGS), db_engine=test_engine)
    with TestClient(app, base_url="https://testserver") as client:
        page = client.get("/")
        script = client.get("/static/js/app.js")

    assert page.status_code == 200
    assert script.status_code == 200
    policy = page.headers["content-security-policy"]
    assert "default-src 'self'" in policy
    assert "script-src 'self'" in policy
    assert "object-src 'none'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "connect-src 'self'" in policy
    assert "content-security-policy" in script.headers


def test_production_session_cookies_are_secure_and_http_only(test_engine: Engine) -> None:
    with Session(test_engine) as db:
        db.add(
            User(
                email="secure@example.com",
                password_hash=hash_password(PASSWORD),
                email_verified_at=datetime.now(UTC),
            )
        )
        db.commit()

    app = create_app(settings=Settings(**PRODUCTION_SETTINGS), db_engine=test_engine)
    with TestClient(app, base_url="https://testserver") as client:
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "secure@example.com", "password": PASSWORD},
            headers={"X-CSRF-Token": csrf, "Origin": "https://testserver"},
        )

    assert login.status_code == 200
    cookies = login.headers.get_list("set-cookie")
    session_cookie = next(item for item in cookies if item.startswith("clarity_session="))
    csrf_cookie = next(item for item in cookies if item.startswith("clarity_csrf="))
    assert "Secure" in session_cookie
    assert "HttpOnly" in session_cookie
    assert "SameSite=lax" in session_cookie
    assert "Secure" in csrf_cookie
    assert "HttpOnly" not in csrf_cookie
