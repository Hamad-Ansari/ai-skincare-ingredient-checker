"""Schema-safe serialization helpers for owned scan history and privacy export."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.models.scans import Scan, ScanIngredient
from backend.app.schemas.scans import (
    OcrTokenRead,
    ScanIngredientRead,
    ScanRead,
    ScanSummary,
)
from backend.app.services.scans.storage import PrivateScanStorage


def scan_to_read(scan: Scan, db: Session, user_id: UUID, settings: Settings) -> ScanRead:
    """Serialize one user-owned scan without exposing private filesystem keys."""
    ingredients = db.scalars(
        select(ScanIngredient)
        .where(ScanIngredient.scan_id == scan.id)
        .order_by(ScanIngredient.position, ScanIngredient.id)
    ).all()
    photo_available = PrivateScanStorage.from_settings(settings).exists(user_id, scan.image_key)
    return ScanRead(
        id=scan.id,
        status=scan.status,
        ocr_status=scan.ocr_status,
        ocr_text=scan.ocr_text,
        ocr_tokens=[OcrTokenRead.model_validate(token) for token in scan.ocr_tokens],
        ocr_confidence=scan.ocr_confidence,
        ocr_engine=scan.ocr_engine,
        ocr_engine_version=scan.ocr_engine_version,
        ocr_error_code=scan.ocr_error_code,
        created_at=scan.created_at,
        updated_at=scan.updated_at,
        ocr_completed_at=scan.ocr_completed_at,
        confirmed_at=scan.confirmed_at,
        ingredients=[ScanIngredientRead.model_validate(item) for item in ingredients],
        photo_available=photo_available,
        photo_download_url=(f"/api/v1/scans/{scan.id}/photo" if photo_available else None),
    )


def scan_to_summary(scan: Scan, user_id: UUID, settings: Settings) -> ScanSummary:
    """Serialize a compact history row for the owner only."""
    return ScanSummary(
        id=scan.id,
        status=scan.status,
        ocr_status=scan.ocr_status,
        ocr_confidence=scan.ocr_confidence,
        ocr_error_code=scan.ocr_error_code,
        created_at=scan.created_at,
        updated_at=scan.updated_at,
        confirmed_at=scan.confirmed_at,
        photo_available=PrivateScanStorage.from_settings(settings).exists(user_id, scan.image_key),
    )
