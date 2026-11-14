"""Trusted operator helper for granting the first administrator role."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.accounts import User
from backend.app.models.ingredient_catalog import AdminAuditEvent


def promote_verified_account(db: Session, email: str) -> User:
    """Grant admin to an existing, active, verified account; no HTTP self-promotion path."""
    normalized_email = email.strip().casefold()
    user = db.scalar(select(User).where(User.email == normalized_email))
    if user is None or not user.is_active or user.email_verified_at is None:
        raise ValueError("Only an existing, active, verified account can be promoted.")
    if user.role != "admin":
        user.role = "admin"
        db.add(
            AdminAuditEvent(
                actor_user_id=None,
                action="admin_role_granted",
                object_type="user",
                object_id=str(user.id),
                request_id=None,
                details={"method": "trusted_operator_cli", "new_role": "admin"},
            )
        )
        db.commit()
        db.refresh(user)
    return user
