"""Versioned, reviewed rules and private, source-linked scan analyses."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
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


class RuleVersion(Base):
    """An immutable deterministic rule version with an explicit editorial lifecycle."""

    __tablename__ = "rule_versions"
    __table_args__ = (
        UniqueConstraint("rule_key", "version", name="uq_rule_versions_key_version"),
        CheckConstraint("rule_type IN ('ingredient_presence')", name="ck_rule_versions_rule_type"),
        CheckConstraint(
            "severity IN ('informational', 'notice', 'caution')",
            name="ck_rule_versions_severity",
        ),
        CheckConstraint(
            "status IN ('draft', 'approved', 'active', 'retired', 'rejected')",
            name="ck_rule_versions_status",
        ),
        Index("ix_rule_versions_status_key", "status", "rule_key"),
        Index(
            "uq_rule_versions_active_key",
            "rule_key",
            unique=True,
            sqlite_where=text("status = 'active'"),
            postgresql_where=text("status = 'active'"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_key: Mapped[str] = mapped_column(String(100), nullable=False)
    version: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_type: Mapped[str] = mapped_column(String(32), nullable=False)
    condition: Mapped[dict[str, object]] = mapped_column(JSON, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="draft", server_default=text("'draft'")
    )
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    activated_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    retired_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
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


class RuleEvidenceMapping(Base):
    """A separately reviewed mapping from one rule version to one evidence record."""

    __tablename__ = "rule_evidence_mappings"
    __table_args__ = (
        UniqueConstraint(
            "rule_version_id", "evidence_record_id", name="uq_rule_evidence_mapping_identity"
        ),
        CheckConstraint(
            "review_status IN ('pending', 'approved', 'rejected')",
            name="ck_rule_evidence_mapping_status",
        ),
        Index("ix_rule_evidence_mappings_rule_status", "rule_version_id", "review_status"),
        Index("ix_rule_evidence_mappings_evidence", "evidence_record_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    rule_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rule_versions.id", ondelete="RESTRICT"), nullable=False
    )
    evidence_record_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("ingredient_evidence_records.id", ondelete="RESTRICT"),
        nullable=False,
    )
    review_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending", server_default=text("'pending'")
    )
    review_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, server_default=func.now()
    )
    reviewed_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)


class ScanAnalysis(Base):
    """One immutable analysis run attached to an owned, explicitly confirmed scan."""

    __tablename__ = "scan_analyses"
    __table_args__ = (
        CheckConstraint(
            "status IN ('completed', 'no_active_rules', 'needs_review')",
            name="ck_scan_analyses_status",
        ),
        CheckConstraint(
            "retrieval_status IN ('not_run', 'not_configured', 'empty', "
            "'retrieved', 'unavailable')",
            name="ck_scan_analyses_retrieval_status",
        ),
        Index("ix_scan_analyses_scan_created", "scan_id", "created_at", "id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scan_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("scans.id", ondelete="CASCADE"), nullable=False
    )
    requested_by: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    engine_version: Mapped[str] = mapped_column(String(64), nullable=False)
    resolver_version: Mapped[str] = mapped_column(String(64), nullable=False)
    rule_snapshot: Mapped[list[dict[str, str]]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )
    retrieval_status: Mapped[str] = mapped_column(String(24), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, server_default=func.now()
    )


class AnalysisIngredient(Base):
    """Exact resolver outcome captured for one confirmed input at analysis time."""

    __tablename__ = "analysis_ingredients"
    __table_args__ = (
        UniqueConstraint("analysis_id", "position", name="uq_analysis_ingredients_position"),
        CheckConstraint("position >= 0", name="ck_analysis_ingredients_position_nonnegative"),
        CheckConstraint(
            "resolution_status IN ('resolved', 'ambiguous', 'unresolved')",
            name="ck_analysis_ingredients_resolution_status",
        ),
        Index("ix_analysis_ingredients_canonical", "ingredient_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("scan_analyses.id", ondelete="CASCADE"), nullable=False
    )
    scan_ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("scan_ingredients.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    input_text: Mapped[str] = mapped_column(String(300), nullable=False)
    normalized_text: Mapped[str] = mapped_column(String(300), nullable=False)
    resolution_status: Mapped[str] = mapped_column(String(16), nullable=False)
    ingredient_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ingredients.id", ondelete="SET NULL"), nullable=True
    )
    ingredient_name: Mapped[str | None] = mapped_column(String(240), nullable=True)
    candidate_snapshot: Mapped[list[dict[str, str]]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )
    matching: Mapped[str] = mapped_column(String(64), nullable=False)


class AnalysisFinding(Base):
    """A deterministic rule match; never a model-generated safety conclusion."""

    __tablename__ = "analysis_findings"
    __table_args__ = (
        UniqueConstraint(
            "analysis_id",
            "rule_version_id",
            "scan_ingredient_id",
            name="uq_analysis_finding_rule_input",
        ),
        CheckConstraint(
            "severity IN ('informational', 'notice', 'caution')",
            name="ck_analysis_findings_severity",
        ),
        Index("ix_analysis_findings_analysis", "analysis_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("scan_analyses.id", ondelete="CASCADE"), nullable=False
    )
    rule_version_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rule_versions.id", ondelete="RESTRICT"), nullable=False
    )
    scan_ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("scan_ingredients.id", ondelete="CASCADE"), nullable=False
    )
    ingredient_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ingredients.id", ondelete="RESTRICT"), nullable=False
    )
    ingredient_name: Mapped[str] = mapped_column(String(240), nullable=False)
    rule_key: Mapped[str] = mapped_column(String(100), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, server_default=func.now()
    )


class AnalysisFindingEvidence(Base):
    """Links a displayed finding to an approved mapping and optional Qdrant rank."""

    __tablename__ = "analysis_finding_evidence"
    __table_args__ = (
        UniqueConstraint(
            "finding_id", "rule_evidence_mapping_id", name="uq_finding_evidence_mapping"
        ),
        CheckConstraint(
            "retrieval_rank IS NULL OR retrieval_rank >= 1",
            name="ck_analysis_finding_evidence_rank",
        ),
        Index("ix_analysis_finding_evidence_finding", "finding_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    finding_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("analysis_findings.id", ondelete="CASCADE"), nullable=False
    )
    rule_evidence_mapping_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("rule_evidence_mappings.id", ondelete="RESTRICT"),
        nullable=False,
    )
    retrieval_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
