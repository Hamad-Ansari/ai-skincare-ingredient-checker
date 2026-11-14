"""Synthetic scan upload, ownership, correction, export, and deletion integration tests."""

from io import BytesIO
from uuid import UUID

from fastapi.testclient import TestClient
from PIL import Image, ImageDraw
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.scans import Scan, ScanIngredient
from backend.app.services.ocr.tesseract import OcrBoundingBox, OcrResult, OcrToken

ORIGIN = "http://testserver"
PASSWORD = "correct horse battery staple"


def _synthetic_png() -> bytes:
    """Create a non-private, non-label raster fixture with simple color blocks."""
    image = Image.new("RGB", (80, 48), color="white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((4, 4, 35, 43), fill=(230, 180, 160))
    draw.rectangle((42, 8, 75, 39), fill=(70, 120, 160))
    output = BytesIO()
    image.save(output, format="PNG")
    image.close()
    return output.getvalue()


def _csrf(client: TestClient) -> str:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return response.json()["csrf_token"]


def _headers(token: str) -> dict[str, str]:
    return {"X-CSRF-Token": token, "Origin": ORIGIN}


def _register_and_login(
    client: TestClient,
    email: str = "scan-user@example.com",
) -> tuple[str, str]:
    csrf = _csrf(client)
    registration = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
        headers=_headers(csrf),
    )
    assert registration.status_code == 202
    verified = client.post(
        "/api/v1/auth/verify-email",
        json={"token": registration.json()["dev_verification_token"]},
        headers=_headers(csrf),
    )
    assert verified.status_code == 204
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
        headers=_headers(csrf),
    )
    assert login.status_code == 200
    return login.json()["csrf_token"], login.json()["user"]["id"]


def _upload(client: TestClient, csrf: str, filename: str = "synthetic.png"):
    return client.post(
        "/api/v1/scans",
        files={"image": (filename, _synthetic_png(), "text/plain")},
        headers=_headers(csrf),
    )


def test_upload_is_authenticated_private_sanitized_and_manually_confirmed(
    client: TestClient,
    test_engine,
    test_settings,
) -> None:
    image = _synthetic_png()
    no_csrf = client.post(
        "/api/v1/scans",
        files={"image": ("synthetic.png", image, "image/png")},
    )
    assert no_csrf.status_code == 403

    csrf, user_id = _register_and_login(client)
    response = client.post(
        "/api/v1/scans",
        files={"image": ("../../private-label-name.png", image, "text/plain")},
        headers=_headers(csrf),
    )
    assert response.status_code == 202
    queued = response.json()
    assert queued["status"] == "queued"
    assert queued["ocr_status"] == "queued"
    assert queued["confirmed_at"] is None
    assert queued["ingredients"] == []
    scan_id = queued["id"]

    detail = client.get(f"/api/v1/scans/{scan_id}")
    assert detail.status_code == 200
    state = detail.json()
    assert state["status"] == "needs_confirmation"
    assert state["ocr_status"] == "unavailable"
    assert state["ocr_error_code"] == "ocr_engine_unavailable"
    assert state["ocr_text"] is None
    assert state["confirmed_at"] is None
    assert state["ingredients"] == []
    assert state["photo_available"] is True
    assert state["photo_download_url"] == f"/api/v1/scans/{scan_id}/photo"

    with Session(test_engine) as db:
        scan = db.get(Scan, UUID(scan_id))
        assert scan is not None
        assert scan.image_key is not None and len(scan.image_key) == 32
        assert "private-label-name" not in scan.image_key
        assert scan.image_content_type == "image/jpeg"
        image_key = scan.image_key

    user_directory = test_settings.private_scan_storage_dir / str(UUID(user_id))
    stored_path = user_directory / f"{image_key}.jpg"
    assert stored_path.is_file()
    assert "private-label-name" not in str(stored_path)
    stored_bytes = stored_path.read_bytes()
    with Image.open(BytesIO(stored_bytes)) as stored:
        assert stored.format == "JPEG"
        assert stored.getexif() == {}

    photo_response = client.get(f"/api/v1/scans/{scan_id}/photo")
    assert photo_response.status_code == 200
    assert photo_response.headers["content-type"].startswith("image/jpeg")
    assert f'filename="scan-{scan_id}.jpg"' in photo_response.headers["content-disposition"]
    assert photo_response.content == stored_bytes

    empty_confirmation = client.post(
        f"/api/v1/scans/{scan_id}/confirm",
        json={"accepted": True},
        headers=_headers(csrf),
    )
    assert empty_confirmation.status_code == 409
    assert empty_confirmation.json()["detail"]["code"] == "ingredient_draft_empty"

    replaced = client.patch(
        f"/api/v1/scans/{scan_id}/ingredients",
        json={"items": ["  Aqua ", "Glycerin"]},
        headers=_headers(csrf),
    )
    assert replaced.status_code == 200
    assert [item["text"] for item in replaced.json()["ingredients"]] == ["Aqua", "Glycerin"]
    assert all(not item["user_confirmed"] for item in replaced.json()["ingredients"])

    confirmed = client.post(
        f"/api/v1/scans/{scan_id}/confirm",
        json={"accepted": True},
        headers=_headers(csrf),
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"
    assert confirmed.json()["confirmed_at"] is not None
    assert all(item["user_confirmed"] for item in confirmed.json()["ingredients"])

    immutable = client.patch(
        f"/api/v1/scans/{scan_id}/ingredients",
        json={"items": ["Changed after confirmation"]},
        headers=_headers(csrf),
    )
    assert immutable.status_code == 409
    assert immutable.json()["detail"]["code"] == "scan_not_editable"

    history = client.get("/api/v1/scans")
    assert history.status_code == 200
    assert history.json()["total"] == 1
    assert history.json()["items"][0]["id"] == scan_id
    assert history.json()["items"][0]["photo_available"] is True


def test_cross_user_scan_access_is_denied_and_scan_csrf_is_enforced(
    client: TestClient,
    test_app,
    test_engine,
) -> None:
    alice_csrf, _ = _register_and_login(client, "scan-alice@example.com")
    uploaded = _upload(client, alice_csrf)
    assert uploaded.status_code == 202
    scan_id = uploaded.json()["id"]

    bob = TestClient(test_app)
    try:
        bob_csrf, _ = _register_and_login(bob, "scan-bob@example.com")
        assert bob.get(f"/api/v1/scans/{scan_id}").status_code == 404
        assert bob.get(f"/api/v1/scans/{scan_id}/photo").status_code == 404
        assert (
            bob.patch(
                f"/api/v1/scans/{scan_id}/ingredients",
                json={"items": ["Not mine"]},
                headers=_headers(bob_csrf),
            ).status_code
            == 404
        )
        assert bob.delete(f"/api/v1/scans/{scan_id}", headers=_headers(bob_csrf)).status_code == 404
        missing_csrf = bob.post(f"/api/v1/scans/{scan_id}/confirm", json={"accepted": True})
        assert missing_csrf.status_code == 403
    finally:
        bob.close()

    with Session(test_engine) as db:
        assert db.get(Scan, UUID(scan_id)) is not None


def test_upload_rate_limit_is_bounded_and_returns_retry_after(
    client: TestClient,
    test_app,
) -> None:
    csrf, user_id = _register_and_login(client, "scan-rate-limit@example.com")
    limiter = test_app.state.scan_rate_limiter
    for _ in range(8):
        limiter.check(f"scan-upload:user:{UUID(user_id)}", limit=8, window_seconds=3600)

    blocked = _upload(client, csrf)

    assert blocked.status_code == 429
    assert blocked.json()["detail"]["code"] == "rate_limited"
    assert int(blocked.headers["retry-after"]) > 0


def test_upload_checks_bytes_instead_of_filename_or_client_mime(client: TestClient) -> None:
    csrf, _ = _register_and_login(client, "scan-invalid@example.com")
    invalid = client.post(
        "/api/v1/scans",
        files={"image": ("looks-like.png", b"<svg>not a raster image</svg>", "image/png")},
        headers=_headers(csrf),
    )
    assert invalid.status_code == 422
    assert invalid.json()["detail"]["code"] == "invalid_image"

    tiff_buffer = BytesIO()
    Image.new("RGB", (8, 8), color="black").save(tiff_buffer, format="TIFF")
    unsupported = client.post(
        "/api/v1/scans",
        files={"image": ("looks-like.jpg", tiff_buffer.getvalue(), "image/jpeg")},
        headers=_headers(csrf),
    )
    assert unsupported.status_code == 415
    assert unsupported.json()["detail"]["code"] == "unsupported_image"
    assert client.get("/api/v1/scans").json()["total"] == 0


def test_export_contains_synthetic_ocr_text_confirmation_and_photo_retrieval_link(
    client: TestClient,
    test_engine,
    monkeypatch,
) -> None:
    import backend.app.services.scans.processing as processing

    class SyntheticEngine:
        def __init__(self, *_args: object) -> None:
            pass

        def extract(self, image_bytes: bytes) -> OcrResult:
            assert image_bytes.startswith(b"\xff\xd8")
            return OcrResult(
                text="Synthetic OCR text only; not a real product label.",
                tokens=(
                    OcrToken(
                        text="Synthetic",
                        confidence=91.0,
                        box=OcrBoundingBox(left=1, top=2, width=3, height=4),
                    ),
                ),
                confidence=91.0,
                engine="synthetic-test-adapter",
                engine_version="fixture-v1",
            )

    monkeypatch.setattr(processing, "TesseractOcrEngine", SyntheticEngine)
    csrf, _ = _register_and_login(client, "scan-export@example.com")
    uploaded = _upload(client, csrf, filename="ignored-private-name.png")
    assert uploaded.status_code == 202
    scan_id = uploaded.json()["id"]

    detail = client.get(f"/api/v1/scans/{scan_id}").json()
    assert detail["ocr_text"] == "Synthetic OCR text only; not a real product label."
    assert detail["ocr_status"] == "succeeded"
    assert detail["ocr_engine"] == "synthetic-test-adapter"
    assert detail["ocr_engine_version"] == "fixture-v1"
    assert detail["ocr_confidence"] == 91.0
    assert detail["ocr_tokens"][0]["box"] == {"left": 1, "top": 2, "width": 3, "height": 4}
    assert detail["confirmed_at"] is None

    patched = client.patch(
        f"/api/v1/scans/{scan_id}/ingredients",
        json={"items": ["Synthetic Ingredient One", "Synthetic Ingredient Two"]},
        headers=_headers(csrf),
    )
    assert patched.status_code == 200
    assert all(not item["user_confirmed"] for item in patched.json()["ingredients"])
    confirmed = client.post(
        f"/api/v1/scans/{scan_id}/confirm",
        json={"accepted": True},
        headers=_headers(csrf),
    )
    assert confirmed.status_code == 200

    export = client.get("/api/v1/privacy/export")
    assert export.status_code == 200
    exported_scan = export.json()["scans"][0]
    assert exported_scan["id"] == scan_id
    assert exported_scan["ocr_text"] == "Synthetic OCR text only; not a real product label."
    assert exported_scan["status"] == "confirmed"
    assert [item["text"] for item in exported_scan["ingredients"]] == [
        "Synthetic Ingredient One",
        "Synthetic Ingredient Two",
    ]
    assert all(item["user_confirmed"] for item in exported_scan["ingredients"])
    assert exported_scan["photo_download_url"] == f"/api/v1/scans/{scan_id}/photo"
    assert exported_scan["photo_available"] is True
    assert "ignored-private-name" not in export.text
    assert "image_key" not in export.text
    assert "private-scans" not in export.text


def test_scan_and_retained_photo_are_removed_on_per_scan_and_account_deletion(
    client: TestClient,
    test_engine,
    test_settings,
) -> None:
    csrf, user_id = _register_and_login(client, "scan-delete@example.com")
    uploaded = _upload(client, csrf)
    assert uploaded.status_code == 202
    scan_id = uploaded.json()["id"]
    with Session(test_engine) as db:
        scan = db.get(Scan, UUID(scan_id))
        assert scan is not None and scan.image_key is not None
        image_key = scan.image_key
    photo_path = test_settings.private_scan_storage_dir / str(UUID(user_id)) / f"{image_key}.jpg"
    assert photo_path.is_file()

    removed = client.delete(f"/api/v1/scans/{scan_id}", headers=_headers(csrf))
    assert removed.status_code == 204
    assert not photo_path.exists()
    assert client.get(f"/api/v1/scans/{scan_id}").status_code == 404
    with Session(test_engine) as db:
        assert db.get(Scan, UUID(scan_id)) is None
        assert db.scalar(select(func.count()).select_from(ScanIngredient)) == 0

    second = _upload(client, csrf, filename="second-synthetic.png")
    assert second.status_code == 202
    second_scan_id = second.json()["id"]
    with Session(test_engine) as db:
        second_scan = db.get(Scan, UUID(second_scan_id))
        assert second_scan is not None and second_scan.image_key is not None
        second_image_key = second_scan.image_key
    second_photo = (
        test_settings.private_scan_storage_dir / str(UUID(user_id)) / f"{second_image_key}.jpg"
    )
    assert second_photo.is_file()

    deleted = client.request(
        "DELETE",
        "/api/v1/users/me",
        json={"password": PASSWORD},
        headers=_headers(csrf),
    )
    assert deleted.status_code == 204
    assert not (test_settings.private_scan_storage_dir / str(UUID(user_id))).exists()
    assert client.get("/api/v1/scans").status_code == 401
    with Session(test_engine) as db:
        assert db.scalar(select(func.count()).select_from(Scan)) == 0
