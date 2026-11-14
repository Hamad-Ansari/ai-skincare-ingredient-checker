"""Private per-user scan records and OCR/correction state."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy import (
    text as sql_text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.base import Base
from backend.app.database.types import UTCDateTime


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class Scan(Base):
    """A user-owned upload and its persisted OCR/correction job state."""

    __tablename__ = "scans"
    __table_args__ = (
        CheckConstraint(
            "status IN ('queued', 'extracting', 'needs_confirmation', 'confirmed', 'failed')",
            name="ck_scans_status",
        ),
        CheckConstraint(
            "ocr_status IN ('queued', 'running', 'succeeded', 'unavailable', 'failed')",
            name="ck_scans_ocr_status",
        ),
        CheckConstraint(
            "image_key IS NULL OR length(image_key) = 32", name="ck_scans_image_key_length"
        ),
        CheckConstraint(
            "image_bytes IS NULL OR image_bytes > 0", name="ck_scans_image_bytes_positive"
        ),
        CheckConstraint(
            "image_width IS NULL OR image_width > 0", name="ck_scans_image_width_positive"
        ),
        CheckConstraint(
            "image_height IS NULL OR image_height > 0", name="ck_scans_image_height_positive"
        ),
        CheckConstraint(
            "image_content_type IS NULL OR image_content_type = 'image/jpeg'",
            name="ck_scans_image_content_type",
        ),
        CheckConstraint(
            "ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 100)",
            name="ck_scans_ocr_confidence_range",
        ),
        UniqueConstraint("user_id", "image_key", name="uq_scans_user_image_key"),
        Index("ix_scans_user_created", "user_id", "created_at", "id"),
        Index("ix_scans_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="queued", server_default=sql_text("'queued'")
    )
    ocr_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="queued", server_default=sql_text("'queued'")
    )
    image_key: Mapped[str | None] = mapped_column(String(32), nullable=True)
    image_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_width: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_height: Mapped[int | None] = mapped_column(Integer, nullable=True)
    image_content_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    ocr_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    ocr_tokens: Mapped[list[dict[str, object]]] = mapped_column(
        JSON, nullable=False, default=list, server_default=sql_text("'[]'")
    )
    ocr_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    ocr_engine: Mapped[str | None] = mapped_column(String(80), nullable=True)
    ocr_engine_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    ocr_error_code: Mapped[str | None] = mapped_column(String(48), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )
    ocr_completed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    confirmed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    ingredients: Mapped[list[ScanIngredient]] = relationship(
        back_populates="scan",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="ScanIngredient.position",
    )


class ScanIngredient(Base):
    """A user-editable draft entry; confirmed only through an explicit scan action."""

    __tablename__ = "scan_ingredients"
    __table_args__ = (
        UniqueConstraint("scan_id", "position", name="uq_scan_ingredients_position"),
        CheckConstraint("position >= 0", name="ck_scan_ingredients_position_nonnegative"),
        CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 100)",
            name="ck_scan_ingredients_confidence_range",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    text: Mapped[str] = mapped_column(String(300), nullable=False)
    confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    user_confirmed: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=sql_text("false")
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        default=utc_now,
        onupdate=utc_now,
        server_default=func.now(),
    )

    scan: Mapped[Scan] = relationship(back_populates="ingredients")
