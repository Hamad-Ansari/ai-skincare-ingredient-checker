"""Request-scoped SQLAlchemy session dependency."""

from collections.abc import Iterator

from fastapi import Request
from sqlalchemy.orm import Session


def get_db_session(request: Request) -> Iterator[Session]:
    """Yield one database session per request and roll back failed work."""
    session = Session(request.app.state.db_engine)
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
