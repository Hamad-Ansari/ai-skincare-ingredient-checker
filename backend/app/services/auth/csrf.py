"""Signed double-submit CSRF tokens with strict token and origin checks."""

from __future__ import annotations

import hashlib
import hmac
import secrets
import time
from urllib.parse import urlsplit

from fastapi import HTTPException, Request, status

from backend.app.core.config import Settings

CSRF_TTL_SECONDS = 2 * 60 * 60
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


def create_csrf_token(secret: bytes, now: int | None = None) -> str:
    """Create a timestamped, HMAC-signed token for the CSRF cookie/header pair."""
    issued_at = int(time.time()) if now is None else now
    nonce = secrets.token_urlsafe(24)
    message = f"{issued_at}.{nonce}".encode("ascii")
    signature = hmac.new(secret, message, hashlib.sha256).hexdigest()
    return f"{issued_at}.{nonce}.{signature}"


def verify_csrf_token(token: str, secret: bytes, now: int | None = None) -> bool:
    """Verify signature, structure, and a bounded token age without raising to callers."""
    if len(token) > 200:
        return False
    try:
        issued_text, nonce, supplied_signature = token.split(".", maxsplit=2)
        issued_at = int(issued_text)
        current_time = int(time.time()) if now is None else now
        if (
            not nonce
            or issued_at > current_time + 60
            or current_time - issued_at > CSRF_TTL_SECONDS
        ):
            return False
        message = f"{issued_at}.{nonce}".encode("ascii")
        expected = hmac.new(secret, message, hashlib.sha256).hexdigest()
        return hmac.compare_digest(expected, supplied_signature)
    except (ValueError, UnicodeEncodeError):
        return False


def _origin_key(origin: str) -> str | None:
    """Normalize a serialized HTTP(S) origin, rejecting paths and credentials."""
    try:
        parsed = urlsplit(origin)
    except ValueError:
        return None
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        return None
    if parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        return None
    if parsed.username or parsed.password:
        return None
    try:
        port = parsed.port
    except ValueError:
        return None
    host = parsed.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    default_port = 443 if parsed.scheme == "https" else 80
    authority = host if port in {None, default_port} else f"{host}:{port}"
    return f"{parsed.scheme}://{authority}"


def _validate_origin(request: Request, settings: Settings) -> None:
    origin = request.headers.get("origin")
    if not origin:
        if settings.app_env == "production":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={"code": "origin_required", "message": "A valid Origin header is required."},
            )
        return

    candidate = _origin_key(origin)
    current = _origin_key(f"{request.url.scheme}://{request.url.netloc}")
    allowed = {_origin_key(value) for value in settings.allowed_origin_list}
    allowed.discard(None)
    if candidate is None or (candidate != current and candidate not in allowed):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "origin_rejected", "message": "The request origin is not allowed."},
        )


def require_csrf(request: Request) -> None:
    """FastAPI dependency: enforce signed double-submit and Origin checks on unsafe calls."""
    if request.method.upper() in SAFE_METHODS:
        return

    settings: Settings = request.app.state.settings
    _validate_origin(request, settings)
    cookie_token = request.cookies.get(settings.csrf_cookie_name, "")
    header_token = request.headers.get("X-CSRF-Token", "")
    if (
        not cookie_token
        or not header_token
        or not hmac.compare_digest(cookie_token, header_token)
        or not verify_csrf_token(cookie_token, request.app.state.csrf_signing_key)
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "csrf_failed", "message": "CSRF validation failed."},
        )
