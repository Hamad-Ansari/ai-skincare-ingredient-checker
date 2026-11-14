"""Reviewed ingredient catalog, source registry, evidence, and import workflow models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from backend.app.database.base import Base
from backend.app.database.types import UTCDateTime


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class EvidenceSource(Base):
    """Provenance and human-reviewed reuse rights for an external reference."""

    __tablename__ = "evidence_sources"
    __table_args__ = (
        UniqueConstraint("canonical_url", name="uq_evidence_sources_canonical_url"),
        CheckConstraint(
            "source_type IN ('regulatory', 'government', 'scientific', 'standards', "
            "'reference', 'dataset', 'other')",
            name="ck_evidence_sources_source_type",
        ),
        CheckConstraint(
            "rights_status IN ('pending', 'approved', 'restricted', 'rejected')",
            name="ck_evidence_sources_rights_status",
        ),
        CheckConstraint(
            "can_reproduce_excerpt = false OR rights_status = 'approved'",
            name="ck_evidence_sources_excerpt_rights",
        ),
        CheckConstraint(
            "checksum_sha256 IS NULL OR length(checksum_sha256) = 64",
            name="ck_evidence_sources_checksum_length",
        ),
        Index("ix_evidence_sources_rights_status", "rights_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    publisher: Mapped[str] = mapped_column(String(180), nullable=False)
    title: Mapped[str] = mapped_column(String(240), nullable=False)
    canonical_url: Mapped[str] = mapped_column(String(2048), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    license_name: Mapped[str] = mapped_column(String(200), nullable=False)
    license_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    attribution_text: Mapped[str] = mapped_column(Text, nullable=False)
    source_version: Mapped[str | None] = mapped_column(String(100), nullable=True)
    checksum_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    retrieved_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    rights_status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="pending", server_default=text("'pending'")
    )
    can_reproduce_excerpt: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default=text("false")
    )
    rights_review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    rights_reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    rights_reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
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


class Ingredient(Base):
    """A reviewed catalog identity, without unreferenced safety or medical claims."""

    __tablename__ = "ingredients"
    __table_args__ = (
        UniqueConstraint("normalized_name", name="uq_ingredients_normalized_name"),
        CheckConstraint(
            "length(normalized_name) > 0", name="ck_ingredients_normalized_name_nonempty"
        ),
        CheckConstraint(
            "name_kind IN ('inci', 'source_name', 'other')", name="ck_ingredients_name_kind"
        ),
        CheckConstraint("status IN ('active', 'retired')", name="ck_ingredients_status"),
        Index("ix_ingredients_status_normalized", "status", "normalized_name"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(240), nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(240), nullable=False)
    name_kind: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default=text("'active'")
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("evidence_sources.id", ondelete="RESTRICT"), nullable=False
    )
    source_locator: Mapped[str] = mapped_column(String(1024), nullable=False)
    dataset_version: Mapped[str] = mapped_column(String(100), nullable=False)
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


class IngredientAlias(Base):
    """A source-backed exact alias; different ingredients may share one alias."""

    __tablename__ = "ingredient_aliases"
    __table_args__ = (
        UniqueConstraint(
            "ingredient_id",
            "normalized_alias",
            "locale",
            name="uq_ingredient_alias_identity_locale",
        ),
        CheckConstraint("length(normalized_alias) > 0", name="ck_ingredient_alias_nonempty"),
        CheckConstraint(
            "alias_type IN ('inci', 'common_name', 'synonym', 'abbreviation')",
            name="ck_ingredient_alias_type",
        ),
        CheckConstraint("status IN ('active', 'retired')", name="ck_ingredient_alias_status"),
        Index("ix_ingredient_aliases_normalized_status", "normalized_alias", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False
    )
    alias: Mapped[str] = mapped_column(String(240), nullable=False)
    normalized_alias: Mapped[str] = mapped_column(String(240), nullable=False)
    locale: Mapped[str] = mapped_column(
        String(35), nullable=False, default="und", server_default=text("'und'")
    )
    alias_type: Mapped[str] = mapped_column(String(24), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default=text("'active'")
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("evidence_sources.id", ondelete="RESTRICT"), nullable=False
    )
    source_locator: Mapped[str] = mapped_column(String(1024), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, server_default=func.now()
    )


class EvidenceRecord(Base):
    """Reviewed, source-linked information; this table is not itself a safety rules engine."""

    __tablename__ = "ingredient_evidence_records"
    __table_args__ = (
        CheckConstraint(
            "evidence_kind IN ('identity', 'composition', 'regulatory', 'research', 'other')",
            name="ck_ingredient_evidence_kind",
        ),
        CheckConstraint(
            "review_status IN ('approved', 'rejected', 'retired')",
            name="ck_ingredient_evidence_review_status",
        ),
        Index("ix_ingredient_evidence_ingredient_status", "ingredient_id", "review_status"),
        Index("ix_ingredient_evidence_source", "source_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ingredients.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("evidence_sources.id", ondelete="RESTRICT"), nullable=False
    )
    evidence_kind: Mapped[str] = mapped_column(String(24), nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[str | None] = mapped_column(String(500), nullable=True)
    locator: Mapped[str] = mapped_column(String(1024), nullable=False)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    review_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="approved", server_default=text("'approved'")
    )
    review_note: Mapped[str] = mapped_column(Text, nullable=False)
    reviewed_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, server_default=func.now()
    )


class IngredientImportBatch(Base):
    """Immutable submitted content awaiting explicit admin review and activation."""

    __tablename__ = "ingredient_import_batches"
    __table_args__ = (
        UniqueConstraint("source_id", "content_sha256", name="uq_ingredient_import_source_digest"),
        CheckConstraint(
            "status IN ('in_review', 'activated', 'rejected')",
            name="ck_ingredient_import_batch_status",
        ),
        CheckConstraint("length(content_sha256) = 64", name="ck_ingredient_import_digest_length"),
        CheckConstraint("row_count > 0", name="ck_ingredient_import_row_count"),
        Index("ix_ingredient_import_batches_status_created", "status", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    source_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("evidence_sources.id", ondelete="RESTRICT"), nullable=False
    )
    dataset_version: Mapped[str] = mapped_column(String(100), nullable=False)
    content_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="in_review", server_default=text("'in_review'")
    )
    row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    activated_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, server_default=func.now()
    )
    activated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class IngredientImportRow(Base):
    """One validated manifest row and its explicit review decision."""

    __tablename__ = "ingredient_import_rows"
    __table_args__ = (
        UniqueConstraint("batch_id", "row_number", name="uq_ingredient_import_row_number"),
        CheckConstraint(
            "decision IN ('pending', 'approved', 'rejected')",
            name="ck_ingredient_import_row_decision",
        ),
        Index("ix_ingredient_import_rows_batch_decision", "batch_id", "decision"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    batch_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ingredient_import_batches.id", ondelete="CASCADE"),
        nullable=False,
    )
    row_number: Mapped[int] = mapped_column(Integer, nullable=False)
    normalized_name: Mapped[str] = mapped_column(String(240), nullable=False)
    payload: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    decision: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default=text("'pending'")
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class AdminAuditEvent(Base):
    """Minimal audit trail for source and catalog workflow changes; never stores raw tokens."""

    __tablename__ = "admin_audit_events"
    __table_args__ = (
        Index("ix_admin_audit_events_created", "created_at"),
        Index("ix_admin_audit_events_object", "object_type", "object_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    object_type: Mapped[str] = mapped_column(String(32), nullable=False)
    object_id: Mapped[str] = mapped_column(String(36), nullable=False)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    details: Mapped[dict[str, object]] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, server_default=func.now()
    )
