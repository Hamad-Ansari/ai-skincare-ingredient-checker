"""Shared authentication and ownership dependencies for API routes."""

from datetime import UTC, datetime
from typing import Annotated

from fastapi import Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.dependencies import get_db_session
from backend.app.models.accounts import AuthSession, User
from backend.app.services.auth.tokens import hash_token

DbSession = Annotated[Session, Depends(get_db_session)]


def _authentication_required() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={"code": "authentication_required", "message": "Authentication is required."},
        headers={"WWW-Authenticate": "Session"},
    )


def get_current_auth_session(request: Request, db: DbSession) -> AuthSession:
    """Resolve the opaque browser cookie to a live database session."""
    settings = request.app.state.settings
    raw_token = request.cookies.get(settings.session_cookie_name)
    if not raw_token:
        raise _authentication_required()

    now = datetime.now(UTC)
    auth_session = db.scalar(
        select(AuthSession).where(
            AuthSession.token_hash == hash_token(raw_token),
            AuthSession.revoked_at.is_(None),
            AuthSession.expires_at > now,
        )
    )
    if auth_session is None:
        raise _authentication_required()

    user = db.get(User, auth_session.user_id)
    if user is None or not user.is_active or user.email_verified_at is None:
        raise _authentication_required()

    request.state.current_user = user
    request.state.auth_session = auth_session
    if (now - auth_session.last_seen_at).total_seconds() >= 300:
        auth_session.last_seen_at = now
        db.commit()
    return auth_session


def get_current_user(
    request: Request,
    _auth_session: Annotated[AuthSession, Depends(get_current_auth_session)],
) -> User:
    """Return only the user bound to the validated server-side session."""
    user = getattr(request.state, "current_user", None)
    if user is None:
        raise _authentication_required()
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_admin_user(user: CurrentUser) -> User:
    """Require an active, verified session belonging to an explicitly promoted admin."""
    if user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "admin_required", "message": "Administrator access is required."},
        )
    return user


AdminUser = Annotated[User, Depends(get_admin_user)]
