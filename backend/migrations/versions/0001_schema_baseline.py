"""Establish the initial Alembic revision before application tables are introduced.

Revision ID: 0001_schema_baseline
Revises:
Create Date: 2026-11-09
"""

from collections.abc import Sequence

revision: str = "0001_schema_baseline"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Start schema version tracking; domain tables arrive with the auth milestone."""
    # Intentionally no application tables in the backend-foundation milestone.
    pass


def downgrade() -> None:
    """The baseline has no application objects to remove."""
    pass
