"""Registration, email verification, login, logout, and password-reset routes."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from logging import getLogger
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.database.dependencies import get_db_session
from backend.app.models.accounts import AuthSession, OneTimeToken, User, UserProfile
from backend.app.schemas.auth import (
    AuthMessageResponse,
    AuthUserRead,
    CsrfTokenResponse,
    LoginRequest,
    LoginResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RegisterRequest,
    RegistrationResponse,
    VerificationRequest,
    VerifyEmailRequest,
)
from backend.app.services.auth.csrf import CSRF_TTL_SECONDS, create_csrf_token
from backend.app.services.auth.mailer import AuthEmailDeliveryError, send_auth_email
from backend.app.services.auth.passwords import (
    hash_needs_upgrade,
    hash_password,
    password_matches,
    verify_unknown_account,
)
from backend.app.services.auth.rate_limit import RateLimitExceeded, rate_limit_auth_attempt
from backend.app.services.auth.tokens import (
    find_valid_one_time_token,
    hash_token,
    issue_one_time_token,
)

logger = getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["authentication"])
DbSession = Annotated[Session, Depends(get_db_session)]


def _rate_limit(request: Request, action: str, identifier: str | None = None) -> None:
    client_host = request.client.host if request.client else "unknown"
    try:
        rate_limit_auth_attempt(
            request.app.state.auth_rate_limiter,
            action,
            client_host,
            identifier,
        )
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited", "message": "Please wait before trying again."},
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc


def _set_csrf_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=token,
        max_age=CSRF_TTL_SECONDS,
        path="/",
        secure=settings.app_env in {"staging", "production"},
        httponly=False,
        samesite="lax",
    )


def _set_session_cookie(response: Response, settings: Settings, token: str) -> None:
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        max_age=settings.session_ttl_hours * 60 * 60,
        path="/",
        secure=settings.app_env in {"staging", "production"},
        httponly=True,
        samesite="lax",
    )


def _clear_auth_cookies(response: Response, settings: Settings) -> None:
    secure = settings.app_env in {"staging", "production"}
    response.delete_cookie(
        key=settings.session_cookie_name,
        path="/",
        secure=secure,
        httponly=True,
        samesite="lax",
    )
    response.delete_cookie(
        key=settings.csrf_cookie_name,
        path="/",
        secure=secure,
        httponly=False,
        samesite="lax",
    )


def _deliver_email(settings: Settings, recipient: str, subject: str, body: str) -> None:
    """Attempt delivery but keep SMTP internals and account-existence details private."""
    try:
        send_auth_email(settings, recipient, subject, body)
    except AuthEmailDeliveryError:
        # Avoid recipient/token/SMTP details in logs; users can request another token.
        logger.warning("Account email delivery failed; the response remains intentionally generic.")


def _create_verification_token(db: Session, user: User, settings: Settings) -> str:
    token = issue_one_time_token(
        db,
        user.id,
        "email_verification",
        timedelta(hours=settings.verification_token_ttl_hours),
    )
    db.commit()
    _deliver_email(
        settings,
        user.email,
        "Verify your Clarity Checker account",
        "Use this one-time verification token in Clarity Checker:\n\n"
        f"{token}\n\n"
        f"It expires in {settings.verification_token_ttl_hours} hours. If you did not request it, "
        "you can ignore this message.",
    )
    return token


def _login_error() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "invalid_credentials", "message": "Email or password is incorrect."},
        headers={"WWW-Authenticate": "Session"},
    )


@router.get("/csrf", response_model=CsrfTokenResponse)
def get_csrf_token(request: Request, response: Response) -> CsrfTokenResponse:
    """Issue a signed CSRF token for the cookie/header pair used by unsafe requests."""
    settings: Settings = request.app.state.settings
    token = create_csrf_token(request.app.state.csrf_signing_key)
    _set_csrf_cookie(response, settings, token)
    return CsrfTokenResponse(csrf_token=token, expires_in_seconds=CSRF_TTL_SECONDS)


@router.post(
    "/register",
    response_model=RegistrationResponse,
    response_model_exclude_none=True,
    status_code=status.HTTP_202_ACCEPTED,
)
def register(
    payload: RegisterRequest,
    request: Request,
    db: DbSession,
) -> RegistrationResponse:
    """Create an unverified account without revealing whether an email is already registered."""
    settings: Settings = request.app.state.settings
    _rate_limit(request, "register", payload.email)

    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        user = User(email=payload.email, password_hash=hash_password(payload.password))
        user.profile = UserProfile(concerns=[])
        db.add(user)
        try:
            db.flush()
        except IntegrityError:
            db.rollback()
            user = db.scalar(select(User).where(User.email == payload.email))
            if user is None:
                raise
    else:
        verify_unknown_account(payload.password)

    dev_token = None
    if user and user.is_active and user.email_verified_at is None:
        try:
            token = _create_verification_token(db, user, settings)
            if settings.auth_expose_dev_tokens:
                dev_token = token
        except IntegrityError:
            db.rollback()
            raise

    return RegistrationResponse(status="accepted", dev_verification_token=dev_token)


@router.post("/verification/request", response_model=AuthMessageResponse, status_code=202)
def request_verification(
    payload: VerificationRequest,
    request: Request,
    db: DbSession,
) -> AuthMessageResponse:
    """Resend verification instructions with a generic response for every email address."""
    settings: Settings = request.app.state.settings
    _rate_limit(request, "verification", payload.email)
    user = db.scalar(select(User).where(User.email == payload.email, User.is_active.is_(True)))
    dev_token = None
    if user and user.email_verified_at is None:
        token = _create_verification_token(db, user, settings)
        if settings.auth_expose_dev_tokens:
            dev_token = token
    return AuthMessageResponse(
        message="If the account requires verification, instructions will be sent.",
        dev_token=dev_token,
    )


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
def verify_email(payload: VerifyEmailRequest, request: Request, db: DbSession) -> Response:
    """Consume a single-use verification token and mark the account verified."""
    _rate_limit(request, "verification")
    token = find_valid_one_time_token(db, payload.token, "email_verification")
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_or_expired_token",
                "message": "The token is invalid or expired.",
            },
        )
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_or_expired_token",
                "message": "The token is invalid or expired.",
            },
        )

    now = datetime.now(UTC)
    token.used_at = now
    if user.email_verified_at is None:
        user.email_verified_at = now
    db.execute(
        update(OneTimeToken)
        .where(
            OneTimeToken.user_id == user.id,
            OneTimeToken.purpose == "email_verification",
            OneTimeToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: DbSession,
) -> LoginResponse:
    """Verify credentials and issue a fresh opaque, server-side session."""
    settings: Settings = request.app.state.settings
    _rate_limit(request, "login", payload.email)
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None:
        verify_unknown_account(payload.password)
        raise _login_error()

    valid_password = password_matches(user.password_hash, payload.password)
    if not valid_password or not user.is_active or user.email_verified_at is None:
        raise _login_error()

    if hash_needs_upgrade(user.password_hash):
        user.password_hash = hash_password(payload.password)

    previous_token = request.cookies.get(settings.session_cookie_name)
    if previous_token:
        db.execute(
            update(AuthSession)
            .where(
                AuthSession.token_hash == hash_token(previous_token),
                AuthSession.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )

    raw_session_token = secrets.token_urlsafe(32)
    now = datetime.now(UTC)
    auth_session = AuthSession(
        user_id=user.id,
        token_hash=hash_token(raw_session_token),
        created_at=now,
        expires_at=now + timedelta(hours=settings.session_ttl_hours),
        last_seen_at=now,
    )
    db.add(auth_session)
    db.commit()

    csrf_token = create_csrf_token(request.app.state.csrf_signing_key)
    _set_session_cookie(response, settings, raw_session_token)
    _set_csrf_cookie(response, settings, csrf_token)
    return LoginResponse(
        user=AuthUserRead.model_validate(user),
        csrf_token=csrf_token,
        csrf_expires_in_seconds=CSRF_TTL_SECONDS,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: DbSession) -> Response:
    """Revoke the presented session (if any) and clear both browser cookies."""
    settings: Settings = request.app.state.settings
    raw_session_token = request.cookies.get(settings.session_cookie_name)
    if raw_session_token:
        db.execute(
            update(AuthSession)
            .where(
                AuthSession.token_hash == hash_token(raw_session_token),
                AuthSession.revoked_at.is_(None),
            )
            .values(revoked_at=datetime.now(UTC))
        )
        db.commit()
    _clear_auth_cookies(response, settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/password-reset/request", response_model=AuthMessageResponse, status_code=202)
def request_password_reset(
    payload: PasswordResetRequest,
    request: Request,
    db: DbSession,
) -> AuthMessageResponse:
    """Request a password reset with the same public response for known and unknown emails."""
    settings: Settings = request.app.state.settings
    _rate_limit(request, "password_reset", payload.email)
    user = db.scalar(select(User).where(User.email == payload.email, User.is_active.is_(True)))
    dev_token = None
    if user:
        token = issue_one_time_token(
            db,
            user.id,
            "password_reset",
            timedelta(minutes=settings.password_reset_token_ttl_minutes),
        )
        db.commit()
        _deliver_email(
            settings,
            user.email,
            "Reset your Clarity Checker password",
            "Use this one-time password-reset token in Clarity Checker:\n\n"
            f"{token}\n\n"
            f"It expires in {settings.password_reset_token_ttl_minutes} minutes. If you did not "
            "request it, you can ignore this message.",
        )
        if settings.auth_expose_dev_tokens:
            dev_token = token
    return AuthMessageResponse(
        message="If an active account matches that address, reset instructions will be sent.",
        dev_token=dev_token,
    )


@router.post("/password-reset/confirm", status_code=status.HTTP_204_NO_CONTENT)
def confirm_password_reset(
    payload: PasswordResetConfirmRequest,
    request: Request,
    response: Response,
    db: DbSession,
) -> Response:
    """Consume one reset token, change the password, and revoke every existing session."""
    _rate_limit(request, "password_reset")
    token = find_valid_one_time_token(db, payload.token, "password_reset")
    if token is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_or_expired_token",
                "message": "The token is invalid or expired.",
            },
        )
    user = db.get(User, token.user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={
                "code": "invalid_or_expired_token",
                "message": "The token is invalid or expired.",
            },
        )

    now = datetime.now(UTC)
    user.password_hash = hash_password(payload.new_password)
    user.password_changed_at = now
    token.used_at = now
    db.execute(
        update(OneTimeToken)
        .where(
            OneTimeToken.user_id == user.id,
            OneTimeToken.purpose == "password_reset",
            OneTimeToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=now)
    )
    db.commit()
    _clear_auth_cookies(response, request.app.state.settings)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
