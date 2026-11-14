"""Add private user scans and persisted OCR/correction state.

Revision ID: 0004_image_scans
Revises: 0003_ingredient_evidence
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from backend.app.database.types import UTCDateTime

revision: str = "0004_image_scans"
down_revision: str | None = "0003_ingredient_evidence"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create scan and editable ingredient-draft tables."""
    op.create_table(
        "scans",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column(
            "status", sa.String(length=24), server_default=sa.text("'queued'"), nullable=False
        ),
        sa.Column(
            "ocr_status", sa.String(length=20), server_default=sa.text("'queued'"), nullable=False
        ),
        sa.Column("image_key", sa.String(length=32), nullable=True),
        sa.Column("image_bytes", sa.Integer(), nullable=True),
        sa.Column("image_width", sa.Integer(), nullable=True),
        sa.Column("image_height", sa.Integer(), nullable=True),
        sa.Column("image_content_type", sa.String(length=40), nullable=True),
        sa.Column("ocr_text", sa.Text(), nullable=True),
        sa.Column("ocr_tokens", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("ocr_confidence", sa.Float(), nullable=True),
        sa.Column("ocr_engine", sa.String(length=80), nullable=True),
        sa.Column("ocr_engine_version", sa.String(length=100), nullable=True),
        sa.Column("ocr_error_code", sa.String(length=48), nullable=True),
        sa.Column("created_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("ocr_completed_at", UTCDateTime(), nullable=True),
        sa.Column("confirmed_at", UTCDateTime(), nullable=True),
        sa.CheckConstraint(
            "status IN ('queued', 'extracting', 'needs_confirmation', 'confirmed', 'failed')",
            name="ck_scans_status",
        ),
        sa.CheckConstraint(
            "ocr_status IN ('queued', 'running', 'succeeded', 'unavailable', 'failed')",
            name="ck_scans_ocr_status",
        ),
        sa.CheckConstraint(
            "image_key IS NULL OR length(image_key) = 32", name="ck_scans_image_key_length"
        ),
        sa.CheckConstraint(
            "image_bytes IS NULL OR image_bytes > 0", name="ck_scans_image_bytes_positive"
        ),
        sa.CheckConstraint(
            "image_width IS NULL OR image_width > 0", name="ck_scans_image_width_positive"
        ),
        sa.CheckConstraint(
            "image_height IS NULL OR image_height > 0", name="ck_scans_image_height_positive"
        ),
        sa.CheckConstraint(
            "image_content_type IS NULL OR image_content_type = 'image/jpeg'",
            name="ck_scans_image_content_type",
        ),
        sa.CheckConstraint(
            "ocr_confidence IS NULL OR (ocr_confidence >= 0 AND ocr_confidence <= 100)",
            name="ck_scans_ocr_confidence_range",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "image_key", name="uq_scans_user_image_key"),
    )
    op.create_index("ix_scans_user_created", "scans", ["user_id", "created_at", "id"])
    op.create_index("ix_scans_user_status", "scans", ["user_id", "status"])

    op.create_table(
        "scan_ingredients",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("scan_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("text", sa.String(length=300), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=True),
        sa.Column("user_confirmed", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("created_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("position >= 0", name="ck_scan_ingredients_position_nonnegative"),
        sa.CheckConstraint(
            "confidence IS NULL OR (confidence >= 0 AND confidence <= 100)",
            name="ck_scan_ingredients_confidence_range",
        ),
        sa.ForeignKeyConstraint(["scan_id"], ["scans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("scan_id", "position", name="uq_scan_ingredients_position"),
    )


def downgrade() -> None:
    """Drop private scan state and its child rows."""
    op.drop_table("scan_ingredients")
    op.drop_index("ix_scans_user_status", table_name="scans")
    op.drop_index("ix_scans_user_created", table_name="scans")
    op.drop_table("scans")
