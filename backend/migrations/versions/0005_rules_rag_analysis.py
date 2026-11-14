"""Add reviewed rule versions, evidence mappings, and scan analysis history.

Revision ID: 0005_rules_rag_analysis
Revises: 0004_image_scans
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from backend.app.database.types import UTCDateTime

revision: str = "0005_rules_rag_analysis"
down_revision: str | None = "0004_image_scans"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create empty rules/evidence lifecycle and private scan-analysis tables."""
    op.create_table(
        "rule_versions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("rule_key", sa.String(length=100), nullable=False),
        sa.Column("version", sa.String(length=32), nullable=False),
        sa.Column("rule_type", sa.String(length=32), nullable=False),
        sa.Column("condition", sa.JSON(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default=sa.text("'draft'"), nullable=False
        ),
        sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_at", UTCDateTime(), nullable=True),
        sa.Column("activated_at", UTCDateTime(), nullable=True),
        sa.Column("retired_at", UTCDateTime(), nullable=True),
        sa.Column("created_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "rule_type IN ('ingredient_presence')", name="ck_rule_versions_rule_type"
        ),
        sa.CheckConstraint(
            "severity IN ('informational', 'notice', 'caution')",
            name="ck_rule_versions_severity",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'approved', 'active', 'retired', 'rejected')",
            name="ck_rule_versions_status",
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rule_key", "version", name="uq_rule_versions_key_version"),
    )
    op.create_index("ix_rule_versions_status_key", "rule_versions", ["status", "rule_key"])
    op.create_index(
        "uq_rule_versions_active_key",
        "rule_versions",
        ["rule_key"],
        unique=True,
        sqlite_where=sa.text("status = 'active'"),
        postgresql_where=sa.text("status = 'active'"),
    )

    op.create_table(
        "rule_evidence_mappings",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("rule_version_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("evidence_record_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "review_status",
            sa.String(length=16),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("created_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("reviewed_at", UTCDateTime(), nullable=True),
        sa.CheckConstraint(
            "review_status IN ('pending', 'approved', 'rejected')",
            name="ck_rule_evidence_mapping_status",
        ),
        sa.ForeignKeyConstraint(["rule_version_id"], ["rule_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["evidence_record_id"], ["ingredient_evidence_records.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "rule_version_id", "evidence_record_id", name="uq_rule_evidence_mapping_identity"
        ),
    )
    op.create_index(
        "ix_rule_evidence_mappings_rule_status",
        "rule_evidence_mappings",
        ["rule_version_id", "review_status"],
    )
    op.create_index(
        "ix_rule_evidence_mappings_evidence", "rule_evidence_mappings", ["evidence_record_id"]
    )

    op.create_table(
        "scan_analyses",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("scan_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("requested_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("engine_version", sa.String(length=64), nullable=False),
        sa.Column("resolver_version", sa.String(length=64), nullable=False),
        sa.Column("rule_snapshot", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("retrieval_status", sa.String(length=24), nullable=False),
        sa.Column("created_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status IN ('completed', 'no_active_rules', 'needs_review')",
            name="ck_scan_analyses_status",
        ),
        sa.CheckConstraint(
            "retrieval_status IN ('not_run', 'not_configured', 'empty', "
            "'retrieved', 'unavailable')",
            name="ck_scan_analyses_retrieval_status",
        ),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["requested_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_scan_analyses_scan_created", "scan_analyses", ["scan_id", "created_at", "id"]
    )

    op.create_table(
        "analysis_ingredients",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("analysis_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("scan_ingredient_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("input_text", sa.String(length=300), nullable=False),
        sa.Column("normalized_text", sa.String(length=300), nullable=False),
        sa.Column("resolution_status", sa.String(length=16), nullable=False),
        sa.Column("ingredient_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("ingredient_name", sa.String(length=240), nullable=True),
        sa.Column("candidate_snapshot", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("matching", sa.String(length=64), nullable=False),
        sa.CheckConstraint("position >= 0", name="ck_analysis_ingredients_position_nonnegative"),
        sa.CheckConstraint(
            "resolution_status IN ('resolved', 'ambiguous', 'unresolved')",
            name="ck_analysis_ingredients_resolution_status",
        ),
        sa.ForeignKeyConstraint(["analysis_id"], ["scan_analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["scan_ingredient_id"], ["scan_ingredients.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("analysis_id", "position", name="uq_analysis_ingredients_position"),
    )
    op.create_index("ix_analysis_ingredients_canonical", "analysis_ingredients", ["ingredient_id"])

    op.create_table(
        "analysis_findings",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("analysis_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("rule_version_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("scan_ingredient_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("ingredient_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("ingredient_name", sa.String(length=240), nullable=False),
        sa.Column("rule_key", sa.String(length=100), nullable=False),
        sa.Column("rule_version", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("severity", sa.String(length=20), nullable=False),
        sa.Column("created_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "severity IN ('informational', 'notice', 'caution')",
            name="ck_analysis_findings_severity",
        ),
        sa.ForeignKeyConstraint(["analysis_id"], ["scan_analyses.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["rule_version_id"], ["rule_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["scan_ingredient_id"], ["scan_ingredients.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "analysis_id",
            "rule_version_id",
            "scan_ingredient_id",
            name="uq_analysis_finding_rule_input",
        ),
    )
    op.create_index("ix_analysis_findings_analysis", "analysis_findings", ["analysis_id"])

    op.create_table(
        "analysis_finding_evidence",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("finding_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("rule_evidence_mapping_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("retrieval_rank", sa.Integer(), nullable=True),
        sa.CheckConstraint(
            "retrieval_rank IS NULL OR retrieval_rank >= 1",
            name="ck_analysis_finding_evidence_rank",
        ),
        sa.ForeignKeyConstraint(["finding_id"], ["analysis_findings.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["rule_evidence_mapping_id"], ["rule_evidence_mappings.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "finding_id", "rule_evidence_mapping_id", name="uq_finding_evidence_mapping"
        ),
    )
    op.create_index(
        "ix_analysis_finding_evidence_finding", "analysis_finding_evidence", ["finding_id"]
    )


def downgrade() -> None:
    """Remove analysis history before the rule/evidence lifecycle it references."""
    op.drop_index("ix_analysis_finding_evidence_finding", table_name="analysis_finding_evidence")
    op.drop_table("analysis_finding_evidence")
    op.drop_index("ix_analysis_findings_analysis", table_name="analysis_findings")
    op.drop_table("analysis_findings")
    op.drop_index("ix_analysis_ingredients_canonical", table_name="analysis_ingredients")
    op.drop_table("analysis_ingredients")
    op.drop_index("ix_scan_analyses_scan_created", table_name="scan_analyses")
    op.drop_table("scan_analyses")
    op.drop_index("ix_rule_evidence_mappings_evidence", table_name="rule_evidence_mappings")
    op.drop_index("ix_rule_evidence_mappings_rule_status", table_name="rule_evidence_mappings")
    op.drop_table("rule_evidence_mappings")
    op.drop_index("uq_rule_versions_active_key", table_name="rule_versions")
    op.drop_index("ix_rule_versions_status_key", table_name="rule_versions")
    op.drop_table("rule_versions")
