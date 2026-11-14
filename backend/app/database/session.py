"""Database engine helpers shared by the application and migration environment."""

from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import StaticPool


def create_database_engine(database_url: str) -> Engine:
    """Create a synchronous SQLAlchemy engine with SQLite-safe thread settings."""
    url = make_url(database_url)
    if url.drivername == "postgresql":
        url = url.set(drivername="postgresql+psycopg")

    if url.get_backend_name() == "sqlite":
        connect_args = {"check_same_thread": False}
        if url.database in (None, "", ":memory:"):
            engine = create_engine(url, connect_args=connect_args, poolclass=StaticPool)
        else:
            engine = create_engine(url, connect_args=connect_args, pool_pre_ping=True)

        @event.listens_for(engine, "connect")
        def enable_sqlite_foreign_keys(dbapi_connection, _connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        return engine

    return create_engine(url, pool_pre_ping=True)


def check_database(engine: Engine) -> None:
    """Run a minimal query to verify the database connection."""
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
