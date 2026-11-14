"""Authenticated current-user, profile, declared-term, and cloud-consent routes."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.dependencies import CurrentUser
from backend.app.database.dependencies import get_db_session
from backend.app.models.accounts import AiProviderConsent, User, UserDeclaredIngredient, UserProfile
from backend.app.schemas.auth import AccountDeletionRequest
from backend.app.schemas.users import (
    AiConsentGrant,
    AiConsentListResponse,
    AiConsentRead,
    CloudProvider,
    DeclaredIngredientCreate,
    DeclaredIngredientRead,
    UserProfilePatch,
    UserProfileRead,
    UserRead,
    UserUpdate,
)
from backend.app.services.auth.consent import CLOUD_CONSENT_DISCLOSURE
from backend.app.services.auth.passwords import password_matches
from backend.app.services.scans.storage import PrivateScanStorage

router = APIRouter(prefix="/users/me", tags=["users"])
DbSession = Annotated[Session, Depends(get_db_session)]


def _profile_response(profile: UserProfile) -> UserProfileRead:
    return UserProfileRead.model_validate(profile)


def _consent_response(
    provider: CloudProvider,
    latest: AiProviderConsent | None,
    current_version: str,
) -> AiConsentRead:
    is_enabled = bool(
        latest and latest.revoked_at is None and latest.disclosure_version == current_version
    )
    return AiConsentRead(
        provider=provider,
        enabled=is_enabled,
        current_disclosure_version=current_version,
        granted_at=latest.granted_at if latest else None,
        revoked_at=latest.revoked_at if latest else None,
    )


def _latest_consents(
    db: Session,
    user_id: UUID,
) -> dict[str, AiProviderConsent]:
    rows = db.scalars(
        select(AiProviderConsent)
        .where(AiProviderConsent.user_id == user_id)
        .order_by(
            AiProviderConsent.revoked_at.is_(None).desc(),
            AiProviderConsent.granted_at.desc(),
            AiProviderConsent.id.desc(),
        )
    ).all()
    latest: dict[str, AiProviderConsent] = {}
    for consent in rows:
        latest.setdefault(consent.provider, consent)
    return latest


@router.get("", response_model=UserRead)
def get_current_user(user: CurrentUser) -> User:
    """Return the authenticated account's public fields only."""
    return user


@router.patch("", response_model=UserRead)
def update_current_user(payload: UserUpdate, user: CurrentUser, db: DbSession) -> User:
    """Update non-credential account metadata; email and role cannot be changed here."""
    if "display_name" in payload.model_fields_set:
        user.display_name = payload.display_name
        db.commit()
        db.refresh(user)
    return user


@router.get("/profile", response_model=UserProfileRead)
def get_profile(user: CurrentUser, db: DbSession) -> UserProfileRead:
    """Return the user's optional, explicitly user-reported profile."""
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "profile_not_found", "message": "Profile not found."},
        )
    return _profile_response(profile)


@router.patch("/profile", response_model=UserProfileRead)
def update_profile(
    payload: UserProfilePatch,
    user: CurrentUser,
    db: DbSession,
) -> UserProfileRead:
    """Edit only the authenticated user's profile; values remain user-reported."""
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))
    if profile is None:
        profile = UserProfile(user_id=user.id, concerns=[])
        db.add(profile)
        db.flush()

    values = payload.model_dump(exclude_unset=True)
    if "concerns" in values:
        profile.concerns = values["concerns"] or []
    if "skin_type" in values:
        profile.skin_type = values["skin_type"]
    if "locale" in values:
        profile.locale = values["locale"]

    db.commit()
    db.refresh(profile)
    return _profile_response(profile)


@router.get("/declared-ingredients", response_model=list[DeclaredIngredientRead])
def list_declared_ingredients(
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[UserDeclaredIngredient]:
    """List only declarations owned by the signed-in user."""
    return list(
        db.scalars(
            select(UserDeclaredIngredient)
            .where(UserDeclaredIngredient.user_id == user.id)
            .order_by(UserDeclaredIngredient.created_at, UserDeclaredIngredient.id)
            .limit(limit)
            .offset(offset)
        ).all()
    )


@router.post(
    "/declared-ingredients",
    response_model=DeclaredIngredientRead,
    status_code=status.HTTP_201_CREATED,
)
def create_declared_ingredient(
    payload: DeclaredIngredientCreate,
    user: CurrentUser,
    db: DbSession,
) -> UserDeclaredIngredient:
    """Save a user-entered ingredient term without treating it as verified evidence."""
    normalized = " ".join(payload.term.split()).casefold()
    existing = db.scalar(
        select(UserDeclaredIngredient).where(
            UserDeclaredIngredient.user_id == user.id,
            UserDeclaredIngredient.normalized_term == normalized,
            UserDeclaredIngredient.declaration_type == payload.declaration_type,
        )
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "declaration_exists", "message": "That declaration already exists."},
        )

    declaration = UserDeclaredIngredient(
        user_id=user.id,
        term=payload.term,
        normalized_term=normalized,
        declaration_type=payload.declaration_type,
    )
    db.add(declaration)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "declaration_exists", "message": "That declaration already exists."},
        ) from exc
    db.refresh(declaration)
    return declaration


@router.delete("/declared-ingredients/{declaration_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_declared_ingredient(
    declaration_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> Response:
    """Delete a declaration only when it is owned by the authenticated account."""
    declaration = db.scalar(
        select(UserDeclaredIngredient).where(
            UserDeclaredIngredient.id == declaration_id,
            UserDeclaredIngredient.user_id == user.id,
        )
    )
    if declaration is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": "Declaration not found."},
        )
    db.delete(declaration)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/ai-consents", response_model=AiConsentListResponse)
def get_ai_consents(
    request: Request,
    user: CurrentUser,
    db: DbSession,
) -> AiConsentListResponse:
    """Return current OpenAI/Groq opt-in status and the server's disclosure version."""
    version = request.app.state.settings.ai_consent_disclosure_version
    latest = _latest_consents(db, user.id)
    return AiConsentListResponse(
        current_disclosure_version=version,
        disclosure_text=CLOUD_CONSENT_DISCLOSURE,
        providers=[
            _consent_response(provider, latest.get(provider), version)
            for provider in ("openai", "groq")
        ],
    )


@router.post("/ai-consents/{provider}", response_model=AiConsentRead)
def grant_ai_consent(
    provider: CloudProvider,
    payload: AiConsentGrant,
    request: Request,
    user: CurrentUser,
    db: DbSession,
) -> AiConsentRead:
    """Grant provider-specific text-only consent for the current disclosure version."""
    version = request.app.state.settings.ai_consent_disclosure_version
    if payload.disclosure_version != version:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "consent_disclosure_changed",
                "message": "Review the current disclosure before opting in.",
            },
        )

    active = db.scalar(
        select(AiProviderConsent)
        .where(
            AiProviderConsent.user_id == user.id,
            AiProviderConsent.provider == provider,
            AiProviderConsent.revoked_at.is_(None),
            AiProviderConsent.disclosure_version == version,
        )
        .order_by(AiProviderConsent.granted_at.desc())
    )
    if active:
        return _consent_response(provider, active, version)

    now = datetime.now(UTC)
    db.execute(
        update(AiProviderConsent)
        .where(
            AiProviderConsent.user_id == user.id,
            AiProviderConsent.provider == provider,
            AiProviderConsent.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    consent = AiProviderConsent(
        user_id=user.id,
        provider=provider,
        disclosure_version=version,
        granted_at=now,
    )
    db.add(consent)
    db.commit()
    db.refresh(consent)
    return _consent_response(provider, consent, version)


@router.delete("/ai-consents/{provider}", response_model=AiConsentRead)
def revoke_ai_consent(
    provider: CloudProvider,
    request: Request,
    user: CurrentUser,
    db: DbSession,
) -> AiConsentRead:
    """Revoke only the selected cloud provider's account-level consent."""
    now = datetime.now(UTC)
    db.execute(
        update(AiProviderConsent)
        .where(
            AiProviderConsent.user_id == user.id,
            AiProviderConsent.provider == provider,
            AiProviderConsent.revoked_at.is_(None),
        )
        .values(revoked_at=now)
    )
    db.commit()
    version = request.app.state.settings.ai_consent_disclosure_version
    latest = _latest_consents(db, user.id).get(provider)
    return _consent_response(provider, latest, version)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    payload: AccountDeletionRequest,
    user: CurrentUser,
    db: DbSession,
    request: Request,
    response: Response,
) -> Response:
    """Delete the user and cascading account records after password confirmation."""
    if not password_matches(user.password_hash, payload.password):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"code": "confirmation_failed", "message": "Password confirmation failed."},
        )

    settings = request.app.state.settings
    try:
        PrivateScanStorage.from_settings(settings).delete_user_images(user.id)
    except (OSError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "account_deletion_unavailable",
                "message": "Private scan data could not be removed right now.",
            },
        ) from exc

    db.delete(user)
    db.commit()
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
    response.status_code = status.HTTP_204_NO_CONTENT
    return response
