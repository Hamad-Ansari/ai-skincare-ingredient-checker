"""Create authentication, profile, declaration, and cloud-consent tables.

Revision ID: 0002_auth_profiles
Revises: 0001_schema_baseline
Create Date: 2026-11-09
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from backend.app.database.types import UTCDateTime

revision: str = "0002_auth_profiles"
down_revision: str | None = "0001_schema_baseline"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Create account tables with database-level ownership and validity constraints."""
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=512), nullable=False),
        sa.Column("display_name", sa.String(length=120), nullable=True),
        sa.Column("role", sa.String(length=20), server_default=sa.text("'user'"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("email_verified_at", UTCDateTime(), nullable=True),
        sa.Column(
            "password_changed_at", UTCDateTime(), server_default=sa.func.now(), nullable=False
        ),
        sa.Column("created_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )

    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", UTCDateTime(), nullable=False),
        sa.Column("revoked_at", UTCDateTime(), nullable=True),
        sa.Column("last_seen_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
    )
    op.create_index(
        "ix_auth_sessions_user_expiry", "auth_sessions", ["user_id", "expires_at"], unique=False
    )

    op.create_table(
        "one_time_tokens",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("expires_at", UTCDateTime(), nullable=False),
        sa.Column("used_at", UTCDateTime(), nullable=True),
        sa.CheckConstraint(
            "purpose IN ('email_verification', 'password_reset')",
            name="ck_one_time_tokens_purpose",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash", name="uq_one_time_tokens_token_hash"),
    )
    op.create_index(
        "ix_one_time_tokens_user_purpose", "one_time_tokens", ["user_id", "purpose"], unique=False
    )

    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("skin_type", sa.String(length=32), nullable=True),
        sa.Column("concerns", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("locale", sa.String(length=20), nullable=True),
        sa.Column("created_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "skin_type IS NULL OR skin_type IN "
            "('dry', 'oily', 'combination', 'normal', 'sensitive', 'unsure')",
            name="ck_user_profiles_skin_type",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", name="uq_user_profiles_user_id"),
    )

    op.create_table(
        "user_declared_ingredients",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("term", sa.String(length=200), nullable=False),
        sa.Column("normalized_term", sa.String(length=200), nullable=False),
        sa.Column("declaration_type", sa.String(length=24), nullable=False),
        sa.Column("created_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "declaration_type IN ('sensitivity', 'allergy', 'preference', 'avoid')",
            name="ck_user_declared_ingredient_type",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id", "normalized_term", "declaration_type", name="uq_user_declared_term_kind"
        ),
    )
    op.create_index(
        "ix_user_declared_ingredients_user",
        "user_declared_ingredients",
        ["user_id"],
        unique=False,
    )

    op.create_table(
        "ai_provider_consents",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("user_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=16), nullable=False),
        sa.Column("disclosure_version", sa.String(length=80), nullable=False),
        sa.Column("granted_at", UTCDateTime(), server_default=sa.func.now(), nullable=False),
        sa.Column("revoked_at", UTCDateTime(), nullable=True),
        sa.CheckConstraint(
            "provider IN ('openai', 'groq')", name="ck_ai_provider_consents_provider"
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ai_provider_consents_user_provider",
        "ai_provider_consents",
        ["user_id", "provider"],
        unique=False,
    )


def downgrade() -> None:
    """Drop account-owned tables in reverse dependency order."""
    op.drop_index("ix_ai_provider_consents_user_provider", table_name="ai_provider_consents")
    op.drop_table("ai_provider_consents")
    op.drop_index("ix_user_declared_ingredients_user", table_name="user_declared_ingredients")
    op.drop_table("user_declared_ingredients")
    op.drop_table("user_profiles")
    op.drop_index("ix_one_time_tokens_user_purpose", table_name="one_time_tokens")
    op.drop_table("one_time_tokens")
    op.drop_index("ix_auth_sessions_user_expiry", table_name="auth_sessions")
    op.drop_table("auth_sessions")
    op.drop_table("users")
