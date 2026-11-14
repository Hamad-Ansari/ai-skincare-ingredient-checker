"""Add reviewed ingredient catalog, evidence provenance, and import workflow.

Revision ID: 0003_ingredient_evidence
Revises: 0002_auth_profiles
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from backend.app.database.types import UTCDateTime

revision: str = "0003_ingredient_evidence"
down_revision: str | None = "0002_auth_profiles"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create source/licensing, ingredient, evidence, import, and audit tables."""
    op.create_table(
        "evidence_sources",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("publisher", sa.String(length=180), nullable=False),
        sa.Column("title", sa.String(length=240), nullable=False),
        sa.Column("canonical_url", sa.String(length=2048), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("license_name", sa.String(length=200), nullable=False),
        sa.Column("license_url", sa.String(length=2048), nullable=True),
        sa.Column("attribution_text", sa.Text(), nullable=False),
        sa.Column("source_version", sa.String(length=100), nullable=True),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=True),
        sa.Column("retrieved_at", UTCDateTime(), nullable=True),
        sa.Column(
            "rights_status",
            sa.String(length=20),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column(
            "can_reproduce_excerpt", sa.Boolean(), server_default=sa.text("false"), nullable=False
        ),
        sa.Column("rights_review_note", sa.Text(), nullable=True),
        sa.Column("rights_reviewed_at", UTCDateTime(), nullable=True),
        sa.Column("rights_reviewed_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("created_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "source_type IN ('regulatory', 'government', 'scientific', 'standards', "
            "'reference', 'dataset', 'other')",
            name="ck_evidence_sources_source_type",
        ),
        sa.CheckConstraint(
            "rights_status IN ('pending', 'approved', 'restricted', 'rejected')",
            name="ck_evidence_sources_rights_status",
        ),
        sa.CheckConstraint(
            "can_reproduce_excerpt = false OR rights_status = 'approved'",
            name="ck_evidence_sources_excerpt_rights",
        ),
        sa.CheckConstraint(
            "checksum_sha256 IS NULL OR length(checksum_sha256) = 64",
            name="ck_evidence_sources_checksum_length",
        ),
        sa.ForeignKeyConstraint(["rights_reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("canonical_url", name="uq_evidence_sources_canonical_url"),
    )
    op.create_index("ix_evidence_sources_rights_status", "evidence_sources", ["rights_status"])

    op.create_table(
        "ingredients",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=240), nullable=False),
        sa.Column("normalized_name", sa.String(length=240), nullable=False),
        sa.Column("name_kind", sa.String(length=20), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default=sa.text("'active'"), nullable=False
        ),
        sa.Column("source_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("source_locator", sa.String(length=1024), nullable=False),
        sa.Column("dataset_version", sa.String(length=100), nullable=False),
        sa.Column("created_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "length(normalized_name) > 0", name="ck_ingredients_normalized_name_nonempty"
        ),
        sa.CheckConstraint(
            "name_kind IN ('inci', 'source_name', 'other')", name="ck_ingredients_name_kind"
        ),
        sa.CheckConstraint("status IN ('active', 'retired')", name="ck_ingredients_status"),
        sa.ForeignKeyConstraint(["source_id"], ["evidence_sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("normalized_name", name="uq_ingredients_normalized_name"),
    )
    op.create_index(
        "ix_ingredients_status_normalized", "ingredients", ["status", "normalized_name"]
    )

    op.create_table(
        "ingredient_aliases",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("ingredient_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("alias", sa.String(length=240), nullable=False),
        sa.Column("normalized_alias", sa.String(length=240), nullable=False),
        sa.Column("locale", sa.String(length=35), server_default=sa.text("'und'"), nullable=False),
        sa.Column("alias_type", sa.String(length=24), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default=sa.text("'active'"), nullable=False
        ),
        sa.Column("source_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("source_locator", sa.String(length=1024), nullable=False),
        sa.Column("created_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(normalized_alias) > 0", name="ck_ingredient_alias_nonempty"),
        sa.CheckConstraint(
            "alias_type IN ('inci', 'common_name', 'synonym', 'abbreviation')",
            name="ck_ingredient_alias_type",
        ),
        sa.CheckConstraint("status IN ('active', 'retired')", name="ck_ingredient_alias_status"),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["evidence_sources.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ingredient_id",
            "normalized_alias",
            "locale",
            name="uq_ingredient_alias_identity_locale",
        ),
    )
    op.create_index(
        "ix_ingredient_aliases_normalized_status",
        "ingredient_aliases",
        ["normalized_alias", "status"],
    )

    op.create_table(
        "ingredient_evidence_records",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("ingredient_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("source_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("evidence_kind", sa.String(length=24), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("scope", sa.String(length=500), nullable=True),
        sa.Column("locator", sa.String(length=1024), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column(
            "review_status",
            sa.String(length=16),
            server_default=sa.text("'approved'"),
            nullable=False,
        ),
        sa.Column("review_note", sa.Text(), nullable=False),
        sa.Column("reviewed_at", UTCDateTime(), nullable=False),
        sa.Column("reviewed_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("created_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "evidence_kind IN ('identity', 'composition', 'regulatory', 'research', 'other')",
            name="ck_ingredient_evidence_kind",
        ),
        sa.CheckConstraint(
            "review_status IN ('approved', 'rejected', 'retired')",
            name="ck_ingredient_evidence_review_status",
        ),
        sa.ForeignKeyConstraint(["ingredient_id"], ["ingredients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_id"], ["evidence_sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ingredient_evidence_ingredient_status",
        "ingredient_evidence_records",
        ["ingredient_id", "review_status"],
    )
    op.create_index("ix_ingredient_evidence_source", "ingredient_evidence_records", ["source_id"])

    op.create_table(
        "ingredient_import_batches",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("source_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("dataset_version", sa.String(length=100), nullable=False),
        sa.Column("content_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "status", sa.String(length=16), server_default=sa.text("'in_review'"), nullable=False
        ),
        sa.Column("row_count", sa.Integer(), nullable=False),
        sa.Column("submitted_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("activated_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("created_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("activated_at", UTCDateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('in_review', 'activated', 'rejected')",
            name="ck_ingredient_import_batch_status",
        ),
        sa.CheckConstraint(
            "length(content_sha256) = 64", name="ck_ingredient_import_digest_length"
        ),
        sa.CheckConstraint("row_count > 0", name="ck_ingredient_import_row_count"),
        sa.ForeignKeyConstraint(["source_id"], ["evidence_sources.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["submitted_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["activated_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "source_id", "content_sha256", name="uq_ingredient_import_source_digest"
        ),
    )
    op.create_index(
        "ix_ingredient_import_batches_status_created",
        "ingredient_import_batches",
        ["status", "created_at"],
    )

    op.create_table(
        "ingredient_import_rows",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("batch_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("normalized_name", sa.String(length=240), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column(
            "decision", sa.String(length=16), server_default=sa.text("'pending'"), nullable=False
        ),
        sa.Column("review_note", sa.Text(), nullable=True),
        sa.Column("reviewed_by", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("reviewed_at", UTCDateTime(), nullable=True),
        sa.CheckConstraint(
            "decision IN ('pending', 'approved', 'rejected')",
            name="ck_ingredient_import_row_decision",
        ),
        sa.ForeignKeyConstraint(["batch_id"], ["ingredient_import_batches.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("batch_id", "row_number", name="uq_ingredient_import_row_number"),
    )
    op.create_index(
        "ix_ingredient_import_rows_batch_decision",
        "ingredient_import_rows",
        ["batch_id", "decision"],
    )

    op.create_table(
        "admin_audit_events",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=64), nullable=False),
        sa.Column("object_type", sa.String(length=32), nullable=False),
        sa.Column("object_id", sa.String(length=36), nullable=False),
        sa.Column("request_id", sa.String(length=64), nullable=True),
        sa.Column("details", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
        sa.Column("created_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_admin_audit_events_created", "admin_audit_events", ["created_at"])
    op.create_index(
        "ix_admin_audit_events_object", "admin_audit_events", ["object_type", "object_id"]
    )


def downgrade() -> None:
    """Drop catalog workflow tables in reverse dependency order."""
    op.drop_index("ix_admin_audit_events_object", table_name="admin_audit_events")
    op.drop_index("ix_admin_audit_events_created", table_name="admin_audit_events")
    op.drop_table("admin_audit_events")
    op.drop_index("ix_ingredient_import_rows_batch_decision", table_name="ingredient_import_rows")
    op.drop_table("ingredient_import_rows")
    op.drop_index(
        "ix_ingredient_import_batches_status_created", table_name="ingredient_import_batches"
    )
    op.drop_table("ingredient_import_batches")
    op.drop_index("ix_ingredient_evidence_source", table_name="ingredient_evidence_records")
    op.drop_index(
        "ix_ingredient_evidence_ingredient_status", table_name="ingredient_evidence_records"
    )
    op.drop_table("ingredient_evidence_records")
    op.drop_index("ix_ingredient_aliases_normalized_status", table_name="ingredient_aliases")
    op.drop_table("ingredient_aliases")
    op.drop_index("ix_ingredients_status_normalized", table_name="ingredients")
    op.drop_table("ingredients")
    op.drop_index("ix_evidence_sources_rights_status", table_name="evidence_sources")
    op.drop_table("evidence_sources")
