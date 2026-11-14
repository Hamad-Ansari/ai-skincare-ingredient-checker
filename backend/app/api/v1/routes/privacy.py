"""Data-export route for authenticated account data."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.dependencies import CurrentUser
from backend.app.database.dependencies import get_db_session
from backend.app.models.accounts import AiProviderConsent, UserDeclaredIngredient, UserProfile
from backend.app.models.safety_rules import ScanAnalysis
from backend.app.models.scans import Scan
from backend.app.schemas.users import (
    AiConsentRead,
    DeclaredIngredientRead,
    PrivacyExport,
    UserProfileRead,
    UserRead,
)
from backend.app.services.scans.analysis import serialize_scan_analysis
from backend.app.services.scans.serialization import scan_to_read

router = APIRouter(prefix="/privacy", tags=["privacy"])
DbSession = Annotated[Session, Depends(get_db_session)]


@router.get("/export", response_model=PrivacyExport)
def export_account_data(
    request: Request,
    response: Response,
    user: CurrentUser,
    db: DbSession,
) -> PrivacyExport:
    """Export only the authenticated user's account/profile/declarations/consent metadata."""
    profile = db.scalar(select(UserProfile).where(UserProfile.user_id == user.id))

    declarations = list(
        db.scalars(
            select(UserDeclaredIngredient)
            .where(UserDeclaredIngredient.user_id == user.id)
            .order_by(UserDeclaredIngredient.created_at, UserDeclaredIngredient.id)
        ).all()
    )
    consent_rows = db.scalars(
        select(AiProviderConsent)
        .where(AiProviderConsent.user_id == user.id)
        .order_by(
            AiProviderConsent.revoked_at.is_(None).desc(),
            AiProviderConsent.granted_at.desc(),
            AiProviderConsent.id.desc(),
        )
    ).all()
    latest: dict[str, AiProviderConsent] = {}
    for consent in consent_rows:
        latest.setdefault(consent.provider, consent)

    scans = db.scalars(
        select(Scan).where(Scan.user_id == user.id).order_by(Scan.created_at, Scan.id)
    ).all()
    scan_data = [scan_to_read(scan, db, user.id, request.app.state.settings) for scan in scans]
    analyses = db.scalars(
        select(ScanAnalysis)
        .join(Scan, ScanAnalysis.scan_id == Scan.id)
        .where(Scan.user_id == user.id)
        .order_by(ScanAnalysis.created_at, ScanAnalysis.id)
    ).all()
    analysis_data = [serialize_scan_analysis(db, analysis) for analysis in analyses]

    current_version = request.app.state.settings.ai_consent_disclosure_version
    consent_data = []
    for provider in ("openai", "groq"):
        record = latest.get(provider)
        consent_data.append(
            AiConsentRead(
                provider=provider,
                enabled=bool(
                    record
                    and record.revoked_at is None
                    and record.disclosure_version == current_version
                ),
                current_disclosure_version=current_version,
                granted_at=record.granted_at if record else None,
                revoked_at=record.revoked_at if record else None,
            )
        )

    response.headers["Content-Disposition"] = 'attachment; filename="clarity-checker-export.json"'
    return PrivacyExport(
        exported_at=datetime.now(UTC),
        user=UserRead.model_validate(user),
        profile=UserProfileRead.model_validate(profile) if profile is not None else None,
        declared_ingredients=[DeclaredIngredientRead.model_validate(item) for item in declarations],
        ai_provider_consents=consent_data,
        scans=scan_data,
        analyses=analysis_data,
    )
