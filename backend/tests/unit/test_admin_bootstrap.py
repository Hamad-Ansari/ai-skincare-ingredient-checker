"""Tests for trusted operator-only administrator bootstrap."""

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.models.accounts import User
from backend.app.models.ingredient_catalog import AdminAuditEvent
from backend.app.services.auth.admin_bootstrap import promote_verified_account


def test_operator_can_promote_only_an_active_verified_account(test_engine) -> None:
    verified = User(
        email="operator@example.com",
        password_hash="test-only-hash",
        email_verified_at=datetime.now(UTC),
    )
    unverified = User(email="unverified@example.com", password_hash="test-only-hash")
    with Session(test_engine) as db:
        db.add_all([verified, unverified])
        db.commit()
        admin = promote_verified_account(db, " OPERATOR@EXAMPLE.COM ")
        assert admin.id == verified.id
        assert admin.role == "admin"
        audit_events = db.scalars(select(AdminAuditEvent)).all()
        assert len(audit_events) == 1
        assert audit_events[0].action == "admin_role_granted"
        assert "email" not in audit_events[0].details

        with pytest.raises(ValueError, match="verified account"):
            promote_verified_account(db, "unverified@example.com")
        with pytest.raises(ValueError, match="verified account"):
            promote_verified_account(db, "missing@example.com")

        still_unverified = db.get(User, unverified.id)
        assert still_unverified is not None and still_unverified.role == "user"
