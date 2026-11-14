"""Account, authentication, profile, declaration, and AI-consent ORM models."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    String,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from backend.app.database.base import Base
from backend.app.database.types import UTCDateTime


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(UTC)


class User(Base):
    """A login identity. Password hashes and internal role are never serialized to clients."""

    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("email", name="uq_users_email"),
        CheckConstraint("role IN ('user', 'admin')", name="ck_users_role"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(320), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(512), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default="user", server_default=text("'user'")
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default=text("true")
    )
    email_verified_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    password_changed_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, server_default=func.now()
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

    sessions: Mapped[list[AuthSession]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    one_time_tokens: Mapped[list[OneTimeToken]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    profile: Mapped[UserProfile | None] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
        passive_deletes=True,
        uselist=False,
    )
    declared_ingredients: Mapped[list[UserDeclaredIngredient]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )
    ai_consents: Mapped[list[AiProviderConsent]] = relationship(
        back_populates="user", cascade="all, delete-orphan", passive_deletes=True
    )


class AuthSession(Base):
    """Server-side session metadata; only a SHA-256 digest of the random cookie token is stored."""

    __tablename__ = "auth_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_auth_sessions_token_hash"),
        Index("ix_auth_sessions_user_expiry", "user_id", "expires_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)
    last_seen_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, server_default=func.now()
    )

    user: Mapped[User] = relationship(back_populates="sessions")


class OneTimeToken(Base):
    """Hashed, expiring, single-use email verification and password-reset token."""

    __tablename__ = "one_time_tokens"
    __table_args__ = (
        UniqueConstraint("token_hash", name="uq_one_time_tokens_token_hash"),
        CheckConstraint(
            "purpose IN ('email_verification', 'password_reset')", name="ck_one_time_tokens_purpose"
        ),
        Index("ix_one_time_tokens_user_purpose", "user_id", "purpose"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    purpose: Mapped[str] = mapped_column(String(32), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, server_default=func.now()
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime(), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    user: Mapped[User] = relationship(back_populates="one_time_tokens")


class UserProfile(Base):
    """Optional user-reported skincare preferences; never a diagnosis or verified medical record."""

    __tablename__ = "user_profiles"
    __table_args__ = (
        UniqueConstraint("user_id", name="uq_user_profiles_user_id"),
        CheckConstraint(
            "skin_type IS NULL OR skin_type IN "
            "('dry', 'oily', 'combination', 'normal', 'sensitive', 'unsure')",
            name="ck_user_profiles_skin_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    skin_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    concerns: Mapped[list[str]] = mapped_column(
        JSON, nullable=False, default=list, server_default=text("'[]'")
    )
    locale: Mapped[str | None] = mapped_column(String(20), nullable=True)
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

    user: Mapped[User] = relationship(back_populates="profile")


class UserDeclaredIngredient(Base):
    """A user-entered term clearly represented as a declaration, not a verified allergy."""

    __tablename__ = "user_declared_ingredients"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "normalized_term", "declaration_type", name="uq_user_declared_term_kind"
        ),
        CheckConstraint(
            "declaration_type IN ('sensitivity', 'allergy', 'preference', 'avoid')",
            name="ck_user_declared_ingredient_type",
        ),
        Index("ix_user_declared_ingredients_user", "user_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    term: Mapped[str] = mapped_column(String(200), nullable=False)
    normalized_term: Mapped[str] = mapped_column(String(200), nullable=False)
    declaration_type: Mapped[str] = mapped_column(String(24), nullable=False)
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

    user: Mapped[User] = relationship(back_populates="declared_ingredients")


class AiProviderConsent(Base):
    """Versioned opt-in history for the OpenAI and Groq cloud providers."""

    __tablename__ = "ai_provider_consents"
    __table_args__ = (
        CheckConstraint("provider IN ('openai', 'groq')", name="ck_ai_provider_consents_provider"),
        Index("ix_ai_provider_consents_user_provider", "user_id", "provider"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    provider: Mapped[str] = mapped_column(String(16), nullable=False)
    disclosure_version: Mapped[str] = mapped_column(String(80), nullable=False)
    granted_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), nullable=False, default=utc_now, server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime(), nullable=True)

    user: Mapped[User] = relationship(back_populates="ai_consents")
