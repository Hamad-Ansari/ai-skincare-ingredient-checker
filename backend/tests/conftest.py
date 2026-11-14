"""Shared backend test fixtures."""

import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.engine import Engine, make_url

from backend.app import models as _models  # noqa: F401
from backend.app.core.config import Settings
from backend.app.database.base import Base
from backend.app.database.session import create_database_engine
from backend.app.main import create_app


@pytest.fixture
def test_engine() -> Iterator[Engine]:
    """Use SQLite by default or a guarded disposable PostgreSQL test database in CI."""
    database_url = os.environ.get("TEST_DATABASE_URL")
    use_postgres = database_url is not None
    if use_postgres:
        parsed_url = make_url(database_url)
        database_name = (parsed_url.database or "").lower()
        if parsed_url.get_backend_name() != "postgresql" or not (
            database_name.endswith(("_test", "_tests")) or database_name.startswith("test_")
        ):
            raise RuntimeError(
                "TEST_DATABASE_URL must be PostgreSQL and use a database name ending in _test(s) "
                "or beginning with test_."
            )
    engine = create_database_engine(database_url or "sqlite://")
    try:
        if use_postgres:
            Base.metadata.drop_all(engine)
        Base.metadata.create_all(engine)
        yield engine
    finally:
        if use_postgres:
            Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def test_settings(tmp_path) -> Settings:
    """Return isolated test settings with private temp storage and no OCR executable."""
    return Settings(
        app_env="test",
        database_url="sqlite://",
        allowed_origins="",
        auth_expose_dev_tokens=True,
        private_scan_storage_dir=tmp_path / "private-scans",
        ocr_tesseract_command="clarity-test-tesseract-missing",
    )


@pytest.fixture
def test_app(test_engine: Engine, test_settings: Settings):
    """Build a dependency-injected app sharing the isolated test database."""
    return create_app(settings=test_settings, db_engine=test_engine)


@pytest.fixture
def client(test_app) -> Iterator[TestClient]:
    """Create a TestClient for a schema-initialized app."""
    with TestClient(test_app) as test_client:
        yield test_client
