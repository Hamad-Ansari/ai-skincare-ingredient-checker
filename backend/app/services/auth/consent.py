"""Cloud-provider consent disclosure and enforcement helpers."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.accounts import AiProviderConsent

CLOUD_CONSENT_DISCLOSURE = (
    "If you opt in and request a text explanation, the selected cloud provider may receive only "
    "the confirmed OCR ingredient text for that finding, its deterministic rule title/message and "
    "severity, and currently approved evidence summaries plus any excerpt explicitly permitted "
    "for reproduction. The provider processes the request under its own API data and retention "
    "terms. Clarity Checker does not send your raw label image, email address, entire scan, or "
    "full skin profile or source URLs to OpenAI or Groq, and it does not store "
    "generated explanations. "
    "Provider-specific consent can be revoked at any time; credentials remain server-side."
)


def has_active_cloud_consent(
    db: Session,
    user_id: UUID,
    provider: str,
    disclosure_version: str,
) -> bool:
    """Check that the latest applicable provider consent is active and current-versioned."""
    consent_id = db.scalar(
        select(AiProviderConsent.id)
        .where(
            AiProviderConsent.user_id == user_id,
            AiProviderConsent.provider == provider,
            AiProviderConsent.disclosure_version == disclosure_version,
            AiProviderConsent.revoked_at.is_(None),
        )
        .limit(1)
    )
    return consent_id is not None
