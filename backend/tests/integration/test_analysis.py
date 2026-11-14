"""Synthetic-only rule review, exact resolution, Qdrant, citation, and analysis tests."""

from datetime import UTC, datetime
from io import BytesIO
from uuid import UUID, uuid4

from fastapi.testclient import TestClient
from PIL import Image
from qdrant_client import QdrantClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.app.models.accounts import User
from backend.app.models.ingredient_catalog import EvidenceRecord, EvidenceSource, Ingredient
from backend.app.models.safety_rules import (
    AnalysisFinding,
    AnalysisFindingEvidence,
    RuleVersion,
    ScanAnalysis,
)
from backend.app.services.llm.explanations import ExplanationError
from backend.app.services.rag.qdrant_store import QdrantEvidenceStore
from backend.app.services.rag.runtime import RagRuntimeUnavailable

ORIGIN = "http://testserver"
PASSWORD = "correct horse battery staple"


class SyntheticEmbeddingProvider:
    """A deterministic vector fixture; it is not a skincare embedding/evaluation model."""

    def embed(self, text: str) -> list[float]:
        assert text
        return [1.0, 0.0]


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
    verification = client.post(
        "/api/v1/auth/verify-email",
        json={"token": registration.json()["dev_verification_token"]},
        headers=_headers(csrf),
    )
    assert verification.status_code == 204
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": PASSWORD},
        headers=_headers(csrf),
    )
    assert login.status_code == 200
    return login.json()["csrf_token"], login.json()["user"]["id"]


def _make_png() -> bytes:
    image = Image.new("RGB", (32, 32), color="white")
    output = BytesIO()
    image.save(output, format="PNG")
    image.close()
    return output.getvalue()


def _create_confirmed_scan(client: TestClient, csrf: str, items: list[str]) -> str:
    uploaded = client.post(
        "/api/v1/scans",
        files={"image": ("synthetic-test.png", _make_png(), "image/png")},
        headers=_headers(csrf),
    )
    assert uploaded.status_code == 202
    scan_id = uploaded.json()["id"]
    assert client.get(f"/api/v1/scans/{scan_id}").json()["status"] == "needs_confirmation"
    patched = client.patch(
        f"/api/v1/scans/{scan_id}/ingredients",
        json={"items": items},
        headers=_headers(csrf),
    )
    assert patched.status_code == 200
    confirmed = client.post(
        f"/api/v1/scans/{scan_id}/confirm",
        json={"accepted": True},
        headers=_headers(csrf),
    )
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "confirmed"
    assert all(item["user_confirmed"] for item in confirmed.json()["ingredients"])
    return scan_id


def _make_synthetic_evidence(test_engine, admin_id: str) -> tuple[str, str, str]:
    """Persist explicitly synthetic, non-factual catalog/evidence fixtures only."""
    source_id, ingredient_id, evidence_id = uuid4(), uuid4(), uuid4()
    now = datetime.now(UTC)
    with Session(test_engine) as db:
        source = EvidenceSource(
            id=source_id,
            publisher="Synthetic test fixture",
            title="Synthetic evidence source (tests only)",
            canonical_url=f"https://{source_id}.example.invalid/synthetic-source",
            source_type="other",
            license_name="Synthetic fixture only; not an external license",
            attribution_text="Synthetic test content only; not a real evidence source.",
            rights_status="pending",
            can_reproduce_excerpt=False,
            created_by=UUID(admin_id),
        )
        ingredient = Ingredient(
            id=ingredient_id,
            name="Synthetic Ingredient Alpha",
            normalized_name="synthetic ingredient alpha",
            name_kind="other",
            status="active",
            source_id=source_id,
            source_locator="synthetic fixture row 1",
            dataset_version="synthetic-test-v1",
        )
        evidence = EvidenceRecord(
            id=evidence_id,
            ingredient_id=ingredient_id,
            source_id=source_id,
            evidence_kind="other",
            summary="Synthetic test-only evidence summary; not a real skincare finding.",
            scope="Synthetic fixture scope only.",
            locator="synthetic fixture locator 1",
            excerpt="Synthetic-only excerpt that must remain hidden without permission.",
            review_status="approved",
            review_note="Synthetic test fixture; not a factual evidence review.",
            reviewed_at=now,
            reviewed_by=UUID(admin_id),
        )
        db.add(source)
        db.flush()
        db.add(ingredient)
        db.flush()
        db.add(evidence)
        db.commit()
    return str(source_id), str(ingredient_id), str(evidence_id)


def _create_and_activate_rule(
    client: TestClient,
    csrf: str,
    ingredient_id: str,
    evidence_id: str,
    version: str,
) -> dict[str, object]:
    created = client.post(
        "/api/v1/admin/rule-versions",
        json={
            "rule_key": "fixture.synthetic-presence",
            "version": version,
            "condition": {"ingredient_ids": [ingredient_id]},
            "title": "Synthetic test-only rule notice",
            "message": "Synthetic fixture message; not a real product or safety claim.",
            "severity": "notice",
            "evidence_record_ids": [evidence_id],
        },
        headers=_headers(csrf),
    )
    assert created.status_code == 201, created.text
    rule = created.json()
    mapping_id = rule["evidence_mappings"][0]["id"]
    assert rule["status"] == "draft"

    mapping_review = client.post(
        f"/api/v1/admin/rule-versions/{rule['id']}/evidence-mappings/{mapping_id}/review",
        json={
            "decision": "approved",
            "note": "Synthetic fixture mapping review only; not a factual safety review.",
        },
        headers=_headers(csrf),
    )
    assert mapping_review.status_code == 200, mapping_review.text
    approved = client.post(
        f"/api/v1/admin/rule-versions/{rule['id']}/review",
        json={
            "decision": "approved",
            "note": "Synthetic fixture rule review only; not approved for production.",
        },
        headers=_headers(csrf),
    )
    assert approved.status_code == 200, approved.text
    activated = client.post(
        f"/api/v1/admin/rule-versions/{rule['id']}/activate",
        headers=_headers(csrf),
    )
    assert activated.status_code == 200, activated.text
    assert activated.json()["status"] == "active"
    return activated.json()


def test_analysis_requires_confirmation_and_empty_findings_are_not_a_safety_result(
    client: TestClient,
    test_engine,
) -> None:
    csrf, _ = _register_and_login(client, "analysis-empty@example.com")
    uploaded = client.post(
        "/api/v1/scans",
        files={"image": ("synthetic.png", _make_png(), "image/png")},
        headers=_headers(csrf),
    )
    assert uploaded.status_code == 202
    scan_id = uploaded.json()["id"]

    premature = client.post(f"/api/v1/scans/{scan_id}/analysis", headers=_headers(csrf))
    assert premature.status_code == 409
    assert premature.json()["detail"]["code"] == "scan_not_confirmed"

    patched = client.patch(
        f"/api/v1/scans/{scan_id}/ingredients",
        json={"items": ["Synthetic Unlisted Ingredient"]},
        headers=_headers(csrf),
    )
    assert patched.status_code == 200
    confirmed = client.post(
        f"/api/v1/scans/{scan_id}/confirm",
        json={"accepted": True},
        headers=_headers(csrf),
    )
    assert confirmed.status_code == 200

    response = client.post(f"/api/v1/scans/{scan_id}/analysis", headers=_headers(csrf))
    assert response.status_code == 201, response.text
    result = response.json()
    assert result["status"] == "no_active_rules"
    assert result["findings"] == []
    assert result["retrieval_status"] == "not_run"
    assert "not an assessment of safety" in result["notice"]
    assert "not a guarantee of safety" in result["disclaimer"]
    assert result["ingredients"][0]["resolution"]["status"] == "unresolved"
    assert result["ingredients"][0]["resolution"]["ingredient"] is None
    assert "safety_score" not in result

    with Session(test_engine) as db:
        assert db.scalar(select(func.count()).select_from(EvidenceSource)) == 0
        assert db.scalar(select(func.count()).select_from(RuleVersion)) == 0
        assert db.scalar(select(func.count()).select_from(ScanAnalysis)) == 1

    fetched = client.get(f"/api/v1/scans/{scan_id}/analysis")
    assert fetched.status_code == 200
    assert fetched.json()["id"] == result["id"]
    assert fetched.json()["findings"] == []
    assert "not an assessment of safety" in fetched.json()["notice"]
    exported = client.get("/api/v1/privacy/export")
    assert exported.status_code == 200
    assert [item["id"] for item in exported.json()["analyses"]] == [result["id"]]


def test_reviewed_rules_qdrant_citations_versioning_and_source_rights_revocation(
    client: TestClient,
    test_app,
    test_engine,
    monkeypatch,
) -> None:
    csrf, admin_id = _register_and_login(client, "analysis-admin@example.com")
    with Session(test_engine) as db:
        admin = db.get(User, UUID(admin_id))
        assert admin is not None
        admin.role = "admin"
        db.commit()

    qdrant_client = QdrantClient(":memory:")
    store = QdrantEvidenceStore(qdrant_client, "m6-synthetic-test")
    test_app.state.rag_store = store
    test_app.state.rag_embedding_provider = SyntheticEmbeddingProvider()
    try:
        source_id, ingredient_id, evidence_id = _make_synthetic_evidence(test_engine, admin_id)

        # A pending source cannot supply a live rule or index entry.
        pending_rule = client.post(
            "/api/v1/admin/rule-versions",
            json={
                "rule_key": "fixture.synthetic-presence",
                "version": "1.0.0",
                "condition": {"ingredient_ids": [ingredient_id]},
                "title": "Synthetic test-only rule notice",
                "message": "Synthetic fixture message only; not a real claim.",
                "severity": "notice",
                "evidence_record_ids": [evidence_id],
            },
            headers=_headers(csrf),
        )
        assert pending_rule.status_code == 409
        assert pending_rule.json()["detail"]["code"] == "rule_target_not_approved"

        rights = client.post(
            f"/api/v1/admin/sources/{source_id}/rights-review",
            json={
                "decision": "approved",
                "note": "Synthetic fixture rights review for this isolated test only.",
                "can_reproduce_excerpt": False,
            },
            headers=_headers(csrf),
        )
        assert rights.status_code == 200

        # Rule cannot activate before its evidence map and the rule itself are reviewed.
        created = client.post(
            "/api/v1/admin/rule-versions",
            json={
                "rule_key": "fixture.synthetic-presence",
                "version": "1.0.0",
                "condition": {"ingredient_ids": [ingredient_id]},
                "title": "Synthetic test-only rule notice",
                "message": "Synthetic fixture message; not a real product or safety claim.",
                "severity": "notice",
                "evidence_record_ids": [evidence_id],
            },
            headers=_headers(csrf),
        )
        assert created.status_code == 201, created.text
        rule_id = created.json()["id"]
        map_id = created.json()["evidence_mappings"][0]["id"]
        early_activation = client.post(
            f"/api/v1/admin/rule-versions/{rule_id}/activate", headers=_headers(csrf)
        )
        assert early_activation.status_code == 409
        assert early_activation.json()["detail"]["code"] == "rule_version_not_approved"
        early_review = client.post(
            f"/api/v1/admin/rule-versions/{rule_id}/review",
            json={
                "decision": "approved",
                "note": "Synthetic fixture rule review only; not approved for production.",
            },
            headers=_headers(csrf),
        )
        assert early_review.status_code == 409
        assert early_review.json()["detail"]["code"] == "rule_evidence_review_incomplete"

        # A user-supplied URL is not accepted as a rule citation; only stored evidence IDs are.
        with_url = client.post(
            "/api/v1/admin/rule-versions",
            json={
                "rule_key": "fixture.other-rule",
                "version": "1.0.0",
                "condition": {"ingredient_ids": [ingredient_id]},
                "title": "Synthetic test-only rule notice",
                "message": "Synthetic fixture message only; not a real claim.",
                "severity": "notice",
                "evidence_record_ids": [evidence_id],
                "source_url": "https://attacker.example.invalid/fake-citation",
            },
            headers=_headers(csrf),
        )
        assert with_url.status_code == 422

        mapping_review = client.post(
            f"/api/v1/admin/rule-versions/{rule_id}/evidence-mappings/{map_id}/review",
            json={
                "decision": "approved",
                "note": "Synthetic fixture mapping review only; not a factual safety review.",
            },
            headers=_headers(csrf),
        )
        assert mapping_review.status_code == 200, mapping_review.text
        approved = client.post(
            f"/api/v1/admin/rule-versions/{rule_id}/review",
            json={
                "decision": "approved",
                "note": "Synthetic fixture rule review only; not approved for production.",
            },
            headers=_headers(csrf),
        )
        assert approved.status_code == 200, approved.text
        activated_one = client.post(
            f"/api/v1/admin/rule-versions/{rule_id}/activate",
            headers=_headers(csrf),
        )
        assert activated_one.status_code == 200, activated_one.text
        assert activated_one.json()["id"] == rule_id
        version_two = _create_and_activate_rule(client, csrf, ingredient_id, evidence_id, "2.0.0")
        assert version_two["status"] == "active"
        with Session(test_engine) as db:
            old_rule = db.get(RuleVersion, UUID(rule_id))
            assert old_rule is not None and old_rule.status == "retired"

        indexed = client.post(f"/api/v1/admin/evidence/{evidence_id}/index", headers=_headers(csrf))
        assert indexed.status_code == 200, indexed.text
        assert indexed.json()["indexed_text_kind"] == "reviewed_summary"
        qdrant_hits = store.search_approved_evidence(
            vector=[1.0, 0.0],
            ingredient_id=UUID(ingredient_id),
            allowed_evidence_ids={UUID(evidence_id)},
            limit=5,
        )
        assert len(qdrant_hits) == 1

        scan_id = _create_confirmed_scan(
            client,
            csrf,
            ["Synthetic Ingredient Alpha", "Synthetic Ingredient Alhpa"],
        )
        analysis = client.post(f"/api/v1/scans/{scan_id}/analysis", headers=_headers(csrf))
        assert analysis.status_code == 201, analysis.text
        result = analysis.json()
        assert result["status"] == "needs_review"
        assert result["retrieval_status"] == "retrieved"
        assert result["rule_versions"] == [
            {
                "id": version_two["id"],
                "rule_key": "fixture.synthetic-presence",
                "version": "2.0.0",
            }
        ]
        assert [item["resolution"]["status"] for item in result["ingredients"]] == [
            "resolved",
            "unresolved",
        ]
        assert result["ingredients"][1]["resolution"]["ingredient"] is None
        assert result["unresolved_count"] == 1
        assert len(result["findings"]) == 1
        finding = result["findings"][0]
        assert finding["rule_version"] == "2.0.0"
        assert finding["ingredient_name"] == "Synthetic Ingredient Alpha"
        assert len(finding["citations"]) == 1
        citation = finding["citations"][0]
        assert citation["evidence_record_id"] == evidence_id
        assert citation["source"]["id"] == source_id
        assert citation["source"]["canonical_url"].startswith("https://")
        assert citation["summary"].startswith("Synthetic test-only")
        assert citation["excerpt"] is None
        assert citation["retrieval_rank"] == 1
        assert "no guess was made" in result["notice"]

        explanation_url = f"/api/v1/scans/{scan_id}/analysis/findings/{finding['id']}/explanation"
        factory_calls: list[str] = []

        def should_not_construct_provider(provider_name, _settings):
            factory_calls.append(provider_name)
            raise AssertionError("Cloud provider construction must be blocked without consent")

        with monkeypatch.context() as patch:
            patch.setattr(
                "backend.app.api.v1.routes.explanations.create_explanation_provider",
                should_not_construct_provider,
            )
            no_consent = client.post(
                explanation_url,
                json={"provider": "openai"},
                headers=_headers(csrf),
            )
        assert no_consent.status_code == 403
        assert no_consent.json()["detail"]["code"] == "ai_consent_required"
        assert factory_calls == []
        local_fallback = client.post(
            explanation_url,
            json={"provider": "ollama"},
            headers=_headers(csrf),
        )
        assert local_fallback.status_code == 200
        assert local_fallback.json()["status"] == "fallback"
        assert local_fallback.json()["provider"] == "ollama"
        assert local_fallback.json()["explanation"] == finding["message"]

        consent_version = client.get("/api/v1/users/me/ai-consents").json()[
            "current_disclosure_version"
        ]
        granted = client.post(
            "/api/v1/users/me/ai-consents/openai",
            json={"disclosure_version": consent_version, "accepted": True},
            headers=_headers(csrf),
        )
        assert granted.status_code == 200 and granted.json()["enabled"] is True
        captured_context = {}

        class SyntheticExplanationProvider:
            def explain(self, context):
                captured_context["value"] = context
                return "This supplemental text only explains the reviewed test finding."

        def synthetic_factory(provider_name, _settings):
            factory_calls.append(provider_name)
            assert provider_name == "openai"
            return SyntheticExplanationProvider()

        with monkeypatch.context() as patch:
            patch.setattr(
                "backend.app.api.v1.routes.explanations.create_explanation_provider",
                synthetic_factory,
            )
            explanation = client.post(
                explanation_url,
                json={"provider": "openai"},
                headers=_headers(csrf),
            )
        assert explanation.status_code == 200, explanation.text
        generated = explanation.json()
        assert generated["status"] == "generated"
        assert generated["provider"] == "openai"
        assert generated["finding_id"] == finding["id"]
        assert "citations" not in generated
        assert "unchanged" in generated["notice"]
        context = captured_context["value"]
        assert context.confirmed_ingredient_text == "Synthetic Ingredient Alpha"
        assert context.canonical_ingredient_name == "Synthetic Ingredient Alpha"
        assert context.evidence[0].summary.startswith("Synthetic test-only")
        assert context.evidence[0].excerpt is None
        assert "source_id" not in vars(context)
        assert "email" not in vars(context)
        assert "profile" not in vars(context)
        assert "image" not in vars(context)
        assert factory_calls == ["openai"]

        class FailingExplanationProvider:
            def explain(self, _context):
                raise ExplanationError("Synthetic provider failure without sensitive details")

        def failing_factory(provider_name, _settings):
            factory_calls.append(provider_name)
            assert provider_name == "openai"
            return FailingExplanationProvider()

        with monkeypatch.context() as patch:
            patch.setattr(
                "backend.app.api.v1.routes.explanations.create_explanation_provider",
                failing_factory,
            )
            fallback = client.post(
                explanation_url,
                json={"provider": "openai"},
                headers=_headers(csrf),
            )
        assert fallback.status_code == 200
        assert fallback.json()["status"] == "fallback"
        assert fallback.json()["provider"] == "openai"
        assert fallback.json()["explanation"] == finding["message"]
        assert "No alternate provider was used" in fallback.json()["notice"]
        assert factory_calls == ["openai", "openai"]

        revoked_consent = client.delete(
            "/api/v1/users/me/ai-consents/openai", headers=_headers(csrf)
        )
        assert revoked_consent.status_code == 200
        factory_calls.clear()
        with monkeypatch.context() as patch:
            patch.setattr(
                "backend.app.api.v1.routes.explanations.create_explanation_provider",
                should_not_construct_provider,
            )
            revoked = client.post(
                explanation_url,
                json={"provider": "openai"},
                headers=_headers(csrf),
            )
        assert revoked.status_code == 403
        assert revoked.json()["detail"]["code"] == "ai_consent_required"
        assert factory_calls == []

        # Retrieval outages do not discard deterministic findings or bypass SQL citation checks.
        unavailable_scan_id = _create_confirmed_scan(client, csrf, ["Synthetic Ingredient Alpha"])

        def unavailable_runtime(_request):
            raise RagRuntimeUnavailable("The configured retrieval service is unavailable")

        with monkeypatch.context() as patch:
            patch.setattr("backend.app.api.v1.routes.scans.get_rag_services", unavailable_runtime)
            unavailable = client.post(
                f"/api/v1/scans/{unavailable_scan_id}/analysis", headers=_headers(csrf)
            )
        assert unavailable.status_code == 201, unavailable.text
        unavailable_result = unavailable.json()
        assert unavailable_result["retrieval_status"] == "unavailable"
        assert len(unavailable_result["findings"]) == 1
        unavailable_citation = unavailable_result["findings"][0]["citations"][0]
        assert unavailable_citation["evidence_record_id"] == evidence_id
        assert unavailable_citation["retrieval_rank"] is None
        removed_unavailable_scan = client.delete(
            f"/api/v1/scans/{unavailable_scan_id}", headers=_headers(csrf)
        )
        assert removed_unavailable_scan.status_code == 204

        other = TestClient(test_app)
        try:
            other_csrf, _ = _register_and_login(other, "analysis-other@example.com")
            assert other.get(f"/api/v1/scans/{scan_id}/analysis").status_code == 404
            assert (
                other.post(
                    f"/api/v1/scans/{scan_id}/analysis",
                    headers=_headers(other_csrf),
                ).status_code
                == 404
            )
            assert (
                other.post(
                    f"/api/v1/scans/{scan_id}/analysis/findings/{finding['id']}/explanation",
                    json={"provider": "ollama"},
                    headers=_headers(other_csrf),
                ).status_code
                == 404
            )
        finally:
            other.close()

        restricted = client.post(
            f"/api/v1/admin/sources/{source_id}/rights-review",
            json={
                "decision": "restricted",
                "note": "Synthetic fixture rights are withdrawn for this test only.",
                "can_reproduce_excerpt": False,
            },
            headers=_headers(csrf),
        )
        assert restricted.status_code == 200
        stale = client.get(f"/api/v1/scans/{scan_id}/analysis")
        assert stale.status_code == 200
        assert stale.json()["status"] == "stale"
        assert stale.json()["findings"] == []
        assert "No current findings are shown" in stale.json()["notice"]
        factory_calls.clear()
        with monkeypatch.context() as patch:
            patch.setattr(
                "backend.app.api.v1.routes.explanations.create_explanation_provider",
                should_not_construct_provider,
            )
            stale_explanation = client.post(
                f"/api/v1/scans/{scan_id}/analysis/findings/{finding['id']}/explanation",
                json={"provider": "ollama"},
                headers=_headers(csrf),
            )
        assert stale_explanation.status_code == 409
        assert stale_explanation.json()["detail"]["code"] == "analysis_stale"
        assert factory_calls == []
        assert (
            store.search_approved_evidence(
                vector=[1.0, 0.0],
                ingredient_id=UUID(ingredient_id),
                allowed_evidence_ids={UUID(evidence_id)},
                limit=5,
            )
            == []
        )
        blocked_index = client.post(
            f"/api/v1/admin/evidence/{evidence_id}/index", headers=_headers(csrf)
        )
        assert blocked_index.status_code == 409

        reapproved = client.post(
            f"/api/v1/admin/sources/{source_id}/rights-review",
            json={
                "decision": "approved",
                "note": "Synthetic test fixture source reviewed again; not a production source.",
                "can_reproduce_excerpt": False,
            },
            headers=_headers(csrf),
        )
        assert reapproved.status_code == 200
        after_reapproval = client.post(f"/api/v1/scans/{scan_id}/analysis", headers=_headers(csrf))
        assert after_reapproval.status_code == 201
        assert after_reapproval.json()["status"] == "no_active_rules"
        assert after_reapproval.json()["findings"] == []
        assert "not an assessment of safety" in after_reapproval.json()["notice"]

        with Session(test_engine) as db:
            assert db.scalar(select(func.count()).select_from(AnalysisFinding)) == 1
            active_rules = db.scalars(
                select(RuleVersion).where(RuleVersion.status == "active")
            ).all()
            assert active_rules == []

        deleted_scan = client.delete(f"/api/v1/scans/{scan_id}", headers=_headers(csrf))
        assert deleted_scan.status_code == 204
        with Session(test_engine) as db:
            assert db.scalar(select(func.count()).select_from(ScanAnalysis)) == 0
            assert db.scalar(select(func.count()).select_from(AnalysisFinding)) == 0
            assert db.scalar(select(func.count()).select_from(AnalysisFindingEvidence)) == 0
    finally:
        store.close()
