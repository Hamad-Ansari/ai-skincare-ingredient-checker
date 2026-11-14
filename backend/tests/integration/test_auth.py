"""Authentication and privacy API integration tests on isolated SQLite."""

from datetime import UTC, datetime, timedelta
from uuid import UUID

from fastapi.testclient import TestClient
from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from backend.app.models.accounts import (
    AiProviderConsent,
    AuthSession,
    OneTimeToken,
    User,
    UserDeclaredIngredient,
    UserProfile,
)
from backend.app.services.auth.consent import has_active_cloud_consent
from backend.app.services.auth.tokens import hash_token

ORIGIN = "http://testserver"
PASSWORD = "correct horse battery staple"


def _csrf(client: TestClient) -> str:
    response = client.get("/api/v1/auth/csrf")
    assert response.status_code == 200
    return response.json()["csrf_token"]


def _headers(token: str, origin: str = ORIGIN) -> dict[str, str]:
    return {"X-CSRF-Token": token, "Origin": origin}


def _register_unverified(
    client: TestClient,
    email: str = "alice@example.com",
    password: str = PASSWORD,
) -> tuple[str, str]:
    csrf = _csrf(client)
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password},
        headers=_headers(csrf),
    )
    assert response.status_code == 202
    return response.json()["dev_verification_token"], csrf


def _register_and_login(
    client: TestClient,
    email: str = "alice@example.com",
    password: str = PASSWORD,
) -> tuple[str, dict[str, object]]:
    verification_token, csrf = _register_unverified(client, email, password)
    verified = client.post(
        "/api/v1/auth/verify-email",
        json={"token": verification_token},
        headers=_headers(csrf),
    )
    assert verified.status_code == 204
    login = client.post(
        "/api/v1/auth/login",
        json={"email": email, "password": password},
        headers=_headers(csrf),
    )
    assert login.status_code == 200
    return login.json()["csrf_token"], login.json()["user"]


def test_registration_verification_and_login_store_only_hashes(
    client: TestClient,
    test_engine,
) -> None:
    raw_verification_token, csrf = _register_unverified(client)
    with Session(test_engine) as db:
        user = db.scalar(select(User).where(User.email == "alice@example.com"))
        token_row = db.scalar(select(OneTimeToken).where(OneTimeToken.user_id == user.id))
        assert user is not None
        assert user.email_verified_at is None
        assert user.password_hash.startswith("$argon2id$")
        assert PASSWORD not in user.password_hash
        assert token_row.token_hash == hash_token(raw_verification_token)
        assert raw_verification_token not in token_row.token_hash

    verify = client.post(
        "/api/v1/auth/verify-email",
        json={"token": raw_verification_token},
        headers=_headers(csrf),
    )
    assert verify.status_code == 204
    assert (
        client.post(
            "/api/v1/auth/verify-email",
            json={"token": raw_verification_token},
            headers=_headers(csrf),
        ).status_code
        == 400
    )

    login = client.post(
        "/api/v1/auth/login",
        json={"email": "ALICE@example.com", "password": PASSWORD},
        headers=_headers(csrf),
    )
    assert login.status_code == 200
    assert "password_hash" not in login.json()["user"]
    assert "password" not in login.json()["user"]

    cookie = client.cookies.get("clarity_session")
    assert cookie
    cookies = login.headers.get_list("set-cookie")
    assert any("clarity_session=" in item and "HttpOnly" in item for item in cookies)
    assert any("clarity_csrf=" in item and "HttpOnly" not in item for item in cookies)
    with Session(test_engine) as db:
        session_row = db.scalar(select(AuthSession).where(AuthSession.user_id == user.id))
        assert session_row.token_hash == hash_token(cookie)
        assert cookie not in session_row.token_hash


def test_csrf_token_is_required_and_mismatched_origin_is_rejected(client: TestClient) -> None:
    body = {"email": "nobody@example.com", "password": PASSWORD}
    assert client.post("/api/v1/auth/register", json=body).status_code == 403

    csrf = _csrf(client)
    # Non-production tooling may omit Origin, but browser-origin mismatches are rejected.
    assert (
        client.post("/api/v1/auth/register", json=body, headers={"X-CSRF-Token": csrf}).status_code
        == 202
    )
    assert (
        client.post(
            "/api/v1/auth/register",
            json=body,
            headers=_headers(csrf, "https://attacker.example"),
        ).status_code
        == 403
    )
    private_value = "secret"
    invalid = client.post(
        "/api/v1/auth/register",
        json={"email": "invalid@example.com", "password": private_value},
        headers=_headers(csrf),
    )
    assert invalid.status_code == 422
    assert private_value not in invalid.text


def test_unverified_and_unknown_login_errors_are_generic(client: TestClient) -> None:
    _register_unverified(client)
    csrf = _csrf(client)
    headers = _headers(csrf)
    unverified = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": PASSWORD},
        headers=headers,
    )
    unknown = client.post(
        "/api/v1/auth/login",
        json={"email": "unknown@example.com", "password": PASSWORD},
        headers=headers,
    )
    wrong_password = client.post(
        "/api/v1/auth/login",
        json={"email": "alice@example.com", "password": "incorrect password"},
        headers=headers,
    )
    assert unverified.status_code == unknown.status_code == wrong_password.status_code == 401
    assert unverified.json() == unknown.json() == wrong_password.json()


def test_logout_revokes_server_side_session_and_clears_cookies(client: TestClient) -> None:
    csrf, _ = _register_and_login(client)
    response = client.post("/api/v1/auth/logout", headers=_headers(csrf))
    assert response.status_code == 204
    assert client.get("/api/v1/users/me").status_code == 401
    cookies = response.headers.get_list("set-cookie")
    assert any("clarity_session=" in item and "Max-Age=0" in item for item in cookies)
    assert any("clarity_csrf=" in item and "Max-Age=0" in item for item in cookies)


def test_expired_sessions_are_rejected(client: TestClient, test_engine) -> None:
    csrf, _ = _register_and_login(client)
    raw_cookie = client.cookies.get("clarity_session")
    assert raw_cookie
    with Session(test_engine) as db:
        db.execute(
            update(AuthSession)
            .where(AuthSession.token_hash == hash_token(raw_cookie))
            .values(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        )
        db.commit()

    assert client.get("/api/v1/users/me").status_code == 401


def test_password_reset_is_single_use_and_revokes_all_sessions(
    client: TestClient,
    test_app,
    test_engine,
) -> None:
    csrf, _ = _register_and_login(client)
    second = TestClient(test_app)
    try:
        second_csrf = _csrf(second)
        second_login = second.post(
            "/api/v1/auth/login",
            json={"email": "alice@example.com", "password": PASSWORD},
            headers=_headers(second_csrf),
        )
        assert second_login.status_code == 200

        reset_request = client.post(
            "/api/v1/auth/password-reset/request",
            json={"email": "alice@example.com"},
            headers=_headers(csrf),
        )
        raw_token = reset_request.json()["dev_token"]
        assert reset_request.status_code == 202
        with Session(test_engine) as db:
            reset_row = db.scalar(
                select(OneTimeToken).where(OneTimeToken.purpose == "password_reset")
            )
            assert reset_row.token_hash == hash_token(raw_token)
            assert raw_token not in reset_row.token_hash
        reset = client.post(
            "/api/v1/auth/password-reset/confirm",
            json={"token": raw_token, "new_password": "a new secure passphrase"},
            headers=_headers(csrf),
        )
        assert reset.status_code == 204
        assert client.get("/api/v1/users/me").status_code == 401
        assert second.get("/api/v1/users/me").status_code == 401

        fresh_csrf = _csrf(client)
        assert (
            client.post(
                "/api/v1/auth/password-reset/confirm",
                json={"token": raw_token, "new_password": "another secure password"},
                headers=_headers(fresh_csrf),
            ).status_code
            == 400
        )
        login_csrf = fresh_csrf
        login = client.post(
            "/api/v1/auth/login",
            json={"email": "alice@example.com", "password": "a new secure passphrase"},
            headers=_headers(login_csrf),
        )
        assert login.status_code == 200
        assert (
            client.post(
                "/api/v1/auth/login",
                json={"email": "alice@example.com", "password": PASSWORD},
                headers=_headers(login.json()["csrf_token"]),
            ).status_code
            == 401
        )
    finally:
        second.close()


def test_profile_declarations_and_export_are_user_scoped(client: TestClient, test_app) -> None:
    alice_csrf, alice = _register_and_login(client)
    alice_headers = _headers(alice_csrf)
    assert (
        client.patch(
            "/api/v1/users/me",
            json={"display_name": "  Alice  Example "},
            headers=alice_headers,
        ).json()["display_name"]
        == "Alice Example"
    )
    profile = client.patch(
        "/api/v1/users/me/profile",
        json={"skin_type": "sensitive", "concerns": ["Redness", "Dryness"]},
        headers=alice_headers,
    )
    assert profile.status_code == 200
    assert profile.json()["user_reported"] is True
    declaration = client.post(
        "/api/v1/users/me/declared-ingredients",
        json={"term": "Fragrance", "declaration_type": "avoid"},
        headers=alice_headers,
    )
    assert declaration.status_code == 201

    bob = TestClient(test_app)
    try:
        _register_and_login(bob, "bob@example.com")
        assert bob.get("/api/v1/users/me/profile").json()["skin_type"] is None
        assert bob.get("/api/v1/users/me/declared-ingredients").json() == []
        assert (
            bob.delete(
                f"/api/v1/users/me/declared-ingredients/{declaration.json()['id']}",
                headers=_headers(bob.get("/api/v1/auth/csrf").json()["csrf_token"]),
            ).status_code
            == 404
        )
    finally:
        bob.close()

    export = client.get("/api/v1/privacy/export")
    assert export.status_code == 200
    assert export.headers["content-disposition"].startswith("attachment;")
    exported = export.json()
    assert exported["user"]["email"] == "alice@example.com"
    assert exported["declared_ingredients"][0]["term"] == "Fragrance"
    assert "password_hash" not in export.text
    assert "session" not in export.text.lower()
    assert alice["id"] == exported["user"]["id"]


def test_provider_consent_is_versioned_and_independently_revocable(
    client: TestClient,
    test_engine,
) -> None:
    csrf, user = _register_and_login(client)
    headers = _headers(csrf)
    initial = client.get("/api/v1/users/me/ai-consents").json()
    version = initial["current_disclosure_version"]
    disclosure = initial["disclosure_text"].lower()
    assert "confirmed ocr ingredient text" in disclosure
    assert "raw label image" in disclosure and "full skin profile" in disclosure
    assert [item["enabled"] for item in initial["providers"]] == [False, False]

    stale = client.post(
        "/api/v1/users/me/ai-consents/openai",
        json={"disclosure_version": "old-version", "accepted": True},
        headers=headers,
    )
    assert stale.status_code == 409
    granted = client.post(
        "/api/v1/users/me/ai-consents/openai",
        json={"disclosure_version": version, "accepted": True},
        headers=headers,
    )
    assert granted.status_code == 200 and granted.json()["enabled"] is True
    with Session(test_engine) as db:
        assert has_active_cloud_consent(db, UUID(user["id"]), "openai", version)
    assert client.get("/api/v1/users/me/ai-consents").json()["providers"][1]["enabled"] is False

    revoked = client.delete("/api/v1/users/me/ai-consents/openai", headers=headers)
    assert revoked.status_code == 200 and revoked.json()["enabled"] is False
    with Session(test_engine) as db:
        assert not has_active_cloud_consent(db, UUID(user["id"]), "openai", version)
    assert client.get("/api/v1/users/me/ai-consents").json()["providers"][0]["enabled"] is False
    regranted = client.post(
        "/api/v1/users/me/ai-consents/openai",
        json={"disclosure_version": version, "accepted": True},
        headers=headers,
    )
    assert regranted.status_code == 200 and regranted.json()["enabled"] is True
    assert (
        client.post(
            "/api/v1/users/me/ai-consents/ollama",
            json={"disclosure_version": version, "accepted": True},
            headers=headers,
        ).status_code
        == 422
    )


def test_account_deletion_cascades_owned_records_and_clears_cookies(
    client: TestClient,
    test_engine,
) -> None:
    csrf, _ = _register_and_login(client)
    consent_version = client.get("/api/v1/users/me/ai-consents").json()[
        "current_disclosure_version"
    ]
    client.post(
        "/api/v1/users/me/declared-ingredients",
        json={"term": "Retinol", "declaration_type": "preference"},
        headers=_headers(csrf),
    )
    client.post(
        "/api/v1/users/me/ai-consents/groq",
        json={"disclosure_version": consent_version, "accepted": True},
        headers=_headers(csrf),
    )
    user_id = client.get("/api/v1/users/me").json()["id"]
    deleted = client.request(
        "DELETE",
        "/api/v1/users/me",
        json={"password": "wrong password"},
        headers=_headers(csrf),
    )
    assert deleted.status_code == 403
    deleted = client.request(
        "DELETE",
        "/api/v1/users/me",
        json={"password": PASSWORD},
        headers=_headers(csrf),
    )
    assert deleted.status_code == 204
    assert client.get("/api/v1/users/me").status_code == 401
    cookies = deleted.headers.get_list("set-cookie")
    assert any("clarity_session=" in item and "Max-Age=0" in item for item in cookies)

    with Session(test_engine) as db:
        user_uuid = UUID(user_id)
        assert db.get(User, user_uuid) is None
        assert db.scalar(select(func.count()).select_from(AuthSession)) == 0
        assert db.scalar(select(func.count()).select_from(OneTimeToken)) == 0
        assert db.scalar(select(func.count()).select_from(UserProfile)) == 0
        assert db.scalar(select(func.count()).select_from(UserDeclaredIngredient)) == 0
        assert db.scalar(select(func.count()).select_from(AiProviderConsent)) == 0


def test_auth_rate_limit_returns_retry_after(client: TestClient) -> None:
    csrf = _csrf(client)
    headers = _headers(csrf)
    payload = {"email": "limited@example.com", "password": PASSWORD}
    for _ in range(3):
        assert (
            client.post("/api/v1/auth/register", json=payload, headers=headers).status_code == 202
        )
    blocked = client.post("/api/v1/auth/register", json=payload, headers=headers)
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
