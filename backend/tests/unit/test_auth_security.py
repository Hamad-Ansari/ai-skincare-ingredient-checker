"""Password, signed-CSRF, opaque-token, rate-limit, and UTC type unit tests."""

from datetime import UTC, datetime, timedelta, timezone

import pytest
from sqlalchemy.dialects.sqlite import dialect as sqlite_dialect

from backend.app.database.types import UTCDateTime
from backend.app.services.auth.csrf import CSRF_TTL_SECONDS, create_csrf_token, verify_csrf_token
from backend.app.services.auth.passwords import (
    PASSWORD_HASHER,
    hash_needs_upgrade,
    hash_password,
    password_matches,
    verify_unknown_account,
)
from backend.app.services.auth.rate_limit import InMemoryRateLimiter, RateLimitExceeded
from backend.app.services.auth.tokens import hash_token


def test_passwords_are_argon2id_salted_and_verifiable() -> None:
    first = hash_password("correct horse battery staple")
    second = hash_password("correct horse battery staple")

    assert first.startswith("$argon2id$")
    assert "$m=19456,t=2,p=1$" in first
    assert first != second
    assert PASSWORD_HASHER.verify(first, "correct horse battery staple")
    assert password_matches(first, "correct horse battery staple")
    assert not password_matches(first, "incorrect password")
    assert not hash_needs_upgrade(first)
    verify_unknown_account("candidate password")


def test_random_one_time_tokens_are_safely_hashable() -> None:
    token = "high-entropy-random-token"

    assert hash_token(token) == hash_token(token)
    assert hash_token(token) != token
    assert hash_token(token) != hash_token(token + "-different")


def test_signed_csrf_tokens_detect_tampering_and_expiry() -> None:
    secret = b"csrf-test-secret-with-enough-randomness"
    token = create_csrf_token(secret, now=1_000)

    assert verify_csrf_token(token, secret, now=1_001)
    assert not verify_csrf_token(token, b"different-secret", now=1_001)
    assert not verify_csrf_token(token + "x", secret, now=1_001)
    assert not verify_csrf_token(token, secret, now=1_000 + CSRF_TTL_SECONDS + 1)
    assert not verify_csrf_token("not-a-token", secret, now=1_001)


def test_rate_limiter_expires_attempts_and_returns_retry_time() -> None:
    now = [100.0]
    limiter = InMemoryRateLimiter(clock=lambda: now[0])
    limiter.check("login:ip:127.0.0.1", 2, 10)
    limiter.check("login:ip:127.0.0.1", 2, 10)

    with pytest.raises(RateLimitExceeded) as exc:
        limiter.check("login:ip:127.0.0.1", 2, 10)
    assert exc.value.retry_after > 0

    now[0] = 111.0
    limiter.check("login:ip:127.0.0.1", 2, 10)


def test_utc_datetime_normalizes_bind_and_result_values() -> None:
    timestamp_type = UTCDateTime()
    local = datetime(2026, 1, 1, 12, tzinfo=timezone(timedelta(hours=5)))
    bound = timestamp_type.process_bind_param(local, sqlite_dialect())
    result = timestamp_type.process_result_value(bound, sqlite_dialect())

    assert bound == datetime(2026, 1, 1, 7)
    assert result == datetime(2026, 1, 1, 7, tzinfo=UTC)
    with pytest.raises(ValueError, match="timezone-aware"):
        timestamp_type.process_bind_param(datetime(2026, 1, 1), sqlite_dialect())
