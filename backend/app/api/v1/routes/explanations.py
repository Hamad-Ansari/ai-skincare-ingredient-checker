"""Explicitly requested, owner-scoped LLM prose for a current deterministic finding."""

from __future__ import annotations

from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.api.dependencies import CurrentUser
from backend.app.database.dependencies import get_db_session
from backend.app.models.safety_rules import AnalysisFinding, ScanAnalysis
from backend.app.models.scans import Scan, ScanIngredient
from backend.app.schemas.explanations import FindingExplanationRead, FindingExplanationRequest
from backend.app.services.auth.consent import has_active_cloud_consent
from backend.app.services.auth.rate_limit import RateLimitExceeded
from backend.app.services.llm.explanations import (
    EvidenceText,
    ExplanationContext,
    ExplanationError,
    create_explanation_provider,
)
from backend.app.services.scans.analysis import SAFETY_DISCLAIMER, serialize_scan_analysis

logger = getLogger(__name__)
router = APIRouter(prefix="/scans", tags=["analysis"])
DbSession = Annotated[Session, Depends(get_db_session)]


def _http_error(code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _fallback(
    finding_id: UUID,
    provider: str,
    finding_message: str,
) -> FindingExplanationRead:
    """Expose the deterministic rule text, never a substitute model or invented claim."""
    fallback_text = " ".join(finding_message.split())[:1200]
    if not fallback_text:
        fallback_text = "Review the deterministic finding and its separately displayed citations."
    return FindingExplanationRead(
        finding_id=finding_id,
        provider=provider,
        status="fallback",
        explanation=fallback_text,
        notice=(
            "The requested explanation could not be generated safely; the reviewed rule message "
            "is shown. No alternate provider was used."
        ),
        disclaimer=SAFETY_DISCLAIMER,
    )


@router.post(
    "/{scan_id}/analysis/findings/{finding_id}/explanation",
    response_model=FindingExplanationRead,
)
def explain_scan_finding(
    scan_id: UUID,
    finding_id: UUID,
    payload: FindingExplanationRequest,
    request: Request,
    user: CurrentUser,
    db: DbSession,
) -> FindingExplanationRead:
    """Generate optional supplementary prose from one current finding and approved evidence."""
    scan = db.scalar(select(Scan).where(Scan.id == scan_id, Scan.user_id == user.id))
    if scan is None:
        raise _http_error("not_found", "Scan not found.", status.HTTP_404_NOT_FOUND)
    if scan.status != "confirmed" or scan.confirmed_at is None:
        raise _http_error(
            "scan_not_confirmed",
            "Review and explicitly confirm this scan before requesting an explanation.",
            status.HTTP_409_CONFLICT,
        )

    scan_items = db.scalars(
        select(ScanIngredient)
        .where(ScanIngredient.scan_id == scan.id)
        .order_by(ScanIngredient.position, ScanIngredient.id)
    ).all()
    if not scan_items or any(not item.user_confirmed for item in scan_items):
        raise _http_error(
            "scan_not_confirmed",
            "Every analysis entry must be explicitly confirmed.",
            status.HTTP_409_CONFLICT,
        )

    analysis = db.scalar(
        select(ScanAnalysis)
        .where(ScanAnalysis.scan_id == scan.id)
        .order_by(ScanAnalysis.created_at.desc(), ScanAnalysis.id.desc())
    )
    if analysis is None:
        raise _http_error(
            "analysis_not_found",
            "Run the deterministic analysis before requesting an explanation.",
            status.HTTP_404_NOT_FOUND,
        )
    current_analysis = serialize_scan_analysis(db, analysis)
    if current_analysis.status == "stale":
        raise _http_error(
            "analysis_stale",
            "The analysis is out of date. Run it again before requesting an explanation.",
            status.HTTP_409_CONFLICT,
        )
    finding_read = next((item for item in current_analysis.findings if item.id == finding_id), None)
    if finding_read is None:
        raise _http_error(
            "finding_not_found",
            "Finding not found in the current analysis.",
            status.HTTP_404_NOT_FOUND,
        )
    finding = db.scalar(
        select(AnalysisFinding).where(
            AnalysisFinding.id == finding_id,
            AnalysisFinding.analysis_id == analysis.id,
        )
    )
    if finding is None:
        raise _http_error(
            "finding_not_found",
            "Finding not found in the current analysis.",
            status.HTTP_404_NOT_FOUND,
        )
    scan_item = next((item for item in scan_items if item.id == finding.scan_ingredient_id), None)
    if scan_item is None:
        raise _http_error(
            "scan_not_confirmed",
            "Every analysis entry must be explicitly confirmed.",
            status.HTTP_409_CONFLICT,
        )

    provider_name = payload.provider
    settings = request.app.state.settings
    if provider_name in {"openai", "groq"} and not has_active_cloud_consent(
        db,
        user.id,
        provider_name,
        settings.ai_consent_disclosure_version,
    ):
        raise _http_error(
            "ai_consent_required",
            "Grant current, provider-specific consent before requesting a cloud explanation.",
            status.HTTP_403_FORBIDDEN,
        )

    evidence = tuple(
        EvidenceText(summary=citation.summary, excerpt=citation.excerpt)
        for citation in finding_read.citations[:3]
    )
    context = ExplanationContext(
        confirmed_ingredient_text=scan_item.text,
        canonical_ingredient_name=finding_read.ingredient_name,
        rule_title=finding_read.title,
        rule_message=finding_read.message,
        severity=finding_read.severity,
        evidence=evidence,
    )
    provider = create_explanation_provider(provider_name, settings)
    if provider is None:
        return _fallback(finding_id, provider_name, finding_read.message)

    limiter = request.app.state.ai_explanation_rate_limiter
    try:
        limiter.check(f"ai-explanation:user:{user.id}", limit=10, window_seconds=3600)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "ai_explanation_rate_limited",
                "message": "Too many explanation requests. Try again later.",
            },
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc

    try:
        explanation = provider.explain(context)
    except ExplanationError as exc:
        logger.warning(
            "Supplementary explanation fell back; provider=%s error_type=%s",
            provider_name,
            type(exc).__name__,
        )
        return _fallback(finding_id, provider_name, finding_read.message)
    except Exception as exc:
        logger.error(
            "Supplementary explanation failed safely; provider=%s error_type=%s",
            provider_name,
            type(exc).__name__,
        )
        return _fallback(finding_id, provider_name, finding_read.message)

    return FindingExplanationRead(
        finding_id=finding_id,
        provider=provider_name,
        status="generated",
        explanation=explanation,
        notice=(
            "Supplemental AI-generated text may be incomplete or inaccurate; the deterministic "
            "finding and server citations are unchanged."
        ),
        disclaimer=SAFETY_DISCLAIMER,
    )
