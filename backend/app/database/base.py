"""SQLAlchemy declarative base for application models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class imported by models and Alembic metadata discovery."""
