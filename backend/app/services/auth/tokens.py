"""Random token generation and hashed, single-use database token operations."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import update
from sqlalchemy.orm import Session

from backend.app.models.accounts import OneTimeToken


def hash_token(raw_token: str) -> str:
    """SHA-256 is appropriate for random 256-bit tokens; plaintext is never persisted."""
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def issue_one_time_token(
    db: Session,
    user_id: uuid.UUID,
    purpose: str,
    lifetime: timedelta,
) -> str:
    """Invalidate previous unused tokens of the same purpose and create a fresh token."""
    now = datetime.now(UTC)
    db.execute(
        update(OneTimeToken)
        .where(
            OneTimeToken.user_id == user_id,
            OneTimeToken.purpose == purpose,
            OneTimeToken.used_at.is_(None),
        )
        .values(used_at=now)
    )
    raw_token = secrets.token_urlsafe(32)
    db.add(
        OneTimeToken(
            user_id=user_id,
            purpose=purpose,
            token_hash=hash_token(raw_token),
            created_at=now,
            expires_at=now + lifetime,
        )
    )
    return raw_token


def find_valid_one_time_token(
    db: Session,
    raw_token: str,
    purpose: str,
) -> OneTimeToken | None:
    """Find an unused, unexpired token while locking it where the database supports it."""
    now = datetime.now(UTC)
    from sqlalchemy import select

    return db.scalar(
        select(OneTimeToken)
        .where(
            OneTimeToken.token_hash == hash_token(raw_token),
            OneTimeToken.purpose == purpose,
            OneTimeToken.used_at.is_(None),
            OneTimeToken.expires_at > now,
        )
        .with_for_update()
    )
