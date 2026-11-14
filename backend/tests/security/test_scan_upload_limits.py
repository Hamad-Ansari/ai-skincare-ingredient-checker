"""Scan request-body byte caps are enforced before multipart payload spooling."""

from io import BytesIO

from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy.engine import Engine

from backend.app.core.config import Settings
from backend.app.main import create_app

ORIGIN = "http://testserver"
PASSWORD = "correct horse battery staple"


def _image_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (8, 8), color="white").save(output, format="PNG")
    return output.getvalue()


def _headers(token: str) -> dict[str, str]:
    return {"X-CSRF-Token": token, "Origin": ORIGIN}


def test_multipart_request_body_limit_returns_413(
    test_engine: Engine,
    test_settings: Settings,
) -> None:
    settings = test_settings.model_copy(update={"scan_max_upload_bytes": 1024})
    app = create_app(settings=settings, db_engine=test_engine)
    with TestClient(app) as client:
        csrf = client.get("/api/v1/auth/csrf").json()["csrf_token"]
        registration = client.post(
            "/api/v1/auth/register",
            json={"email": "scan-limit@example.com", "password": PASSWORD},
            headers=_headers(csrf),
        )
        assert registration.status_code == 202
        assert (
            client.post(
                "/api/v1/auth/verify-email",
                json={"token": registration.json()["dev_verification_token"]},
                headers=_headers(csrf),
            ).status_code
            == 204
        )
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "scan-limit@example.com", "password": PASSWORD},
            headers=_headers(csrf),
        )
        assert login.status_code == 200
        csrf = login.json()["csrf_token"]

        oversized = client.post(
            "/api/v1/scans",
            files={"image": ("synthetic.png", _image_bytes() + b"x" * 70_000, "image/png")},
            headers=_headers(csrf),
        )

    assert oversized.status_code == 413
    assert oversized.json()["detail"]["code"] == "image_too_large"
