"""Admin source/import workflow and conservative ingredient-resolution integration tests."""

import json
from pathlib import Path
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.accounts import User
from backend.app.models.ingredient_catalog import (
    AdminAuditEvent,
    EvidenceSource,
    Ingredient,
    IngredientImportBatch,
)

ORIGIN = "http://testserver"
PASSWORD = "correct horse battery staple"
PROJECT_ROOT = Path(__file__).resolve().parents[3]
FIXTURE_PATH = (
    PROJECT_ROOT / "backend" / "tests" / "fixtures" / "ambiguous_ingredient_manifest.json"
)


def _csrf(client: TestClient) -> str:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return response.json()["csrf_token"]


def _headers(token: str) -> dict[str, str]:
    return {"X-CSRF-Token": token, "Origin": ORIGIN}


def _register_and_login(client: TestClient, email: str) -> tuple[str, str]:
    csrf = _csrf(client)
    registration = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PASSWORD},
        headers=_headers(csrf),
    )
    assert registration.status_code == 202
    verification_token = registration.json()["dev_verification_token"]
    verified = client.post(
        "/api/v1/auth/verify-email",
        json={"token": verification_token},
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


def _fixture_records() -> list[dict[str, object]]:
    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert fixture["fixture_only"] is True
    return fixture["records"]


def _source_payload() -> dict[str, object]:
    return {
        "publisher": "Synthetic test fixture",
        "title": "Synthetic ingredient aliases (tests only)",
        "canonical_url": "https://fixture.example.invalid/catalog",
        "source_type": "dataset",
        "license_name": "Test fixture only; no external source",
        "attribution_text": "Synthetic fixture; not a real ingredient or evidence source.",
    }


def test_non_admin_cannot_read_or_change_catalog_sources(client: TestClient) -> None:
    csrf, _ = _register_and_login(client, "catalog-user@example.com")
    assert client.get("/api/v1/admin/sources").status_code == 403
    denied = client.post(
        "/api/v1/admin/sources",
        json=_source_payload(),
        headers=_headers(csrf),
    )
    assert denied.status_code == 403
    self_promotion = client.patch(
        "/api/v1/users/me",
        json={"role": "admin"},
        headers=_headers(csrf),
    )
    assert self_promotion.status_code == 422


def test_reviewed_import_requires_approved_rights_and_keeps_ambiguous_names_unresolved(
    client: TestClient,
    test_engine,
) -> None:
    csrf, admin_id = _register_and_login(client, "catalog-admin@example.com")
    with Session(test_engine) as db:
        admin = db.get(User, UUID(admin_id))
        assert admin is not None
        admin.role = "admin"
        db.commit()

    source_response = client.post(
        "/api/v1/admin/sources",
        json=_source_payload(),
        headers=_headers(csrf),
    )
    assert source_response.status_code == 201
    source_id = source_response.json()["id"]
    assert source_response.json()["rights_status"] == "pending"
    assert source_response.json()["can_reproduce_excerpt"] is False

    manifest = {
        "source_id": source_id,
        "dataset_version": "synthetic-test-fixture-v1",
        "records": _fixture_records(),
    }
    not_reviewed = client.post(
        "/api/v1/admin/ingredient-imports",
        json=manifest,
        headers=_headers(csrf),
    )
    assert not_reviewed.status_code == 409
    assert not_reviewed.json()["detail"]["code"] == "source_rights_not_approved"

    approved_without_excerpt = client.post(
        f"/api/v1/admin/sources/{source_id}/rights-review",
        json={
            "decision": "approved",
            "note": "Synthetic test-only rights decision; not production source approval.",
            "can_reproduce_excerpt": False,
        },
        headers=_headers(csrf),
    )
    assert approved_without_excerpt.status_code == 200
    excerpt_denied = client.post(
        "/api/v1/admin/ingredient-imports",
        json=manifest,
        headers=_headers(csrf),
    )
    assert excerpt_denied.status_code == 422
    assert excerpt_denied.json()["detail"]["code"] == "source_excerpt_not_permitted"

    approved_with_excerpt = client.post(
        f"/api/v1/admin/sources/{source_id}/rights-review",
        json={
            "decision": "approved",
            "note": "Synthetic test-only excerpt permission for this isolated test database.",
            "can_reproduce_excerpt": True,
        },
        headers=_headers(csrf),
    )
    assert approved_with_excerpt.status_code == 200

    created = client.post(
        "/api/v1/admin/ingredient-imports",
        json=manifest,
        headers=_headers(csrf),
    )
    assert created.status_code == 201
    batch = created.json()
    assert batch["status"] == "in_review"
    assert [row["decision"] for row in batch["rows"]] == ["pending", "pending", "pending"]

    duplicate = client.post(
        "/api/v1/admin/ingredient-imports",
        json=manifest,
        headers=_headers(csrf),
    )
    assert duplicate.status_code == 409
    incomplete = client.post(
        f"/api/v1/admin/ingredient-imports/{batch['id']}/activate",
        headers=_headers(csrf),
    )
    assert incomplete.status_code == 409
    assert incomplete.json()["detail"]["code"] == "import_review_incomplete"

    decisions = ["approved", "approved", "rejected"]
    for row, decision in zip(batch["rows"], decisions, strict=True):
        reviewed = client.post(
            f"/api/v1/admin/ingredient-imports/{batch['id']}/rows/{row['id']}/review",
            json={
                "decision": decision,
                "note": "Synthetic fixture reviewed for ambiguity workflow tests.",
            },
            headers=_headers(csrf),
        )
        assert reviewed.status_code == 200
        assert reviewed.json()["decision"] == decision

    activated = client.post(
        f"/api/v1/admin/ingredient-imports/{batch['id']}/activate",
        headers=_headers(csrf),
    )
    assert activated.status_code == 200
    assert activated.json()["status"] == "activated"
    assert [row["decision"] for row in activated.json()["rows"]] == decisions

    ambiguous = client.post(
        "/api/v1/ingredients/resolve",
        json={"term": "  SHARED\tSYNTHETIC alias  "},
        headers=_headers(csrf),
    )
    assert ambiguous.status_code == 200
    assert ambiguous.json()["status"] == "ambiguous"
    assert ambiguous.json()["ingredient"] is None
    assert len(ambiguous.json()["candidates"]) == 2

    exact = client.post(
        "/api/v1/ingredients/resolve",
        json={"term": "synthetic ingredient a"},
        headers=_headers(csrf),
    )
    assert exact.status_code == 200
    assert exact.json()["status"] == "resolved"
    ingredient_id = exact.json()["ingredient"]["id"]

    fuzzy = client.post(
        "/api/v1/ingredients/resolve",
        json={"term": "synthetic ingrediant a"},
        headers=_headers(csrf),
    )
    assert fuzzy.status_code == 200
    assert fuzzy.json()["status"] == "unresolved"
    assert fuzzy.json()["candidates"] == []

    wrong_locale = client.post(
        "/api/v1/ingredients/resolve",
        json={"term": "shared synthetic alias", "locale": "fr"},
        headers=_headers(csrf),
    )
    assert wrong_locale.status_code == 200
    assert wrong_locale.json()["status"] == "unresolved"

    detail = client.get(f"/api/v1/ingredients/{ingredient_id}")
    assert detail.status_code == 200
    assert detail.json()["name"] == "Synthetic Ingredient A"
    assert detail.json()["source"]["canonical_url"] == _source_payload()["canonical_url"]
    assert len(detail.json()["evidence"]) == 1
    assert "Test-only excerpt" in detail.json()["evidence"][0]["excerpt"]

    rejected = client.post(
        "/api/v1/ingredients/resolve",
        json={"term": "rejected synthetic alias"},
        headers=_headers(csrf),
    )
    assert rejected.status_code == 200
    assert rejected.json()["status"] == "unresolved"

    audit = client.get("/api/v1/admin/audit-events")
    assert audit.status_code == 200
    actions = {event["action"] for event in audit.json()}
    assert {
        "source_registered",
        "source_rights_reviewed",
        "ingredient_import_submitted",
        "ingredient_import_row_reviewed",
        "ingredient_import_activated",
    }.issubset(actions)
    assert all(event["request_id"] for event in audit.json())
    assert "password" not in audit.text.lower()
    assert "token" not in audit.text.lower()

    with Session(test_engine) as db:
        source = db.get(EvidenceSource, UUID(source_id))
        assert source is not None and source.rights_status == "approved"
        assert db.scalar(select(Ingredient).where(Ingredient.status == "active")) is not None
        saved_batch = db.get(IngredientImportBatch, UUID(batch["id"]))
        assert saved_batch is not None and saved_batch.content_sha256
        assert db.scalar(select(AdminAuditEvent.id)) is not None

    revoked = client.post(
        f"/api/v1/admin/sources/{source_id}/rights-review",
        json={
            "decision": "restricted",
            "note": "Synthetic test-only source restriction after activation.",
            "can_reproduce_excerpt": False,
        },
        headers=_headers(csrf),
    )
    assert revoked.status_code == 200
    hidden = client.post(
        "/api/v1/ingredients/resolve",
        json={"term": "synthetic ingredient a"},
        headers=_headers(csrf),
    )
    assert hidden.status_code == 200
    assert hidden.json()["status"] == "unresolved"
    assert client.get(f"/api/v1/ingredients/{ingredient_id}").status_code == 404
