"""Alembic migration smoke tests against a temporary SQLite database."""

from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import text

from backend.app.core.config import get_settings
from backend.app.database.session import create_database_engine

PROJECT_ROOT = Path(__file__).resolve().parents[3]
ALEMBIC_CONFIG = PROJECT_ROOT / "backend" / "alembic.ini"


def test_baseline_migration_upgrades_temporary_database(tmp_path, monkeypatch) -> None:
    database_path = tmp_path / "migration_test.db"
    database_url = f"sqlite:///{database_path.as_posix()}"
    monkeypatch.setenv("APP_ENV", "test")
    monkeypatch.setenv("DATABASE_URL", database_url)
    get_settings.cache_clear()

    try:
        config = Config(str(ALEMBIC_CONFIG))
        command.upgrade(config, "head")

        engine = create_database_engine(database_url)
        try:
            with engine.connect() as connection:
                revision = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                tables = set(
                    connection.exec_driver_sql(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).scalars()
                )
        finally:
            engine.dispose()

        assert revision == "0005_rules_rag_analysis"
        account_tables = {
            "users",
            "auth_sessions",
            "one_time_tokens",
            "user_profiles",
            "user_declared_ingredients",
            "ai_provider_consents",
        }
        catalog_tables = {
            "evidence_sources",
            "ingredients",
            "ingredient_aliases",
            "ingredient_evidence_records",
            "ingredient_import_batches",
            "ingredient_import_rows",
            "admin_audit_events",
        }
        scan_tables = {"scans", "scan_ingredients"}
        analysis_tables = {
            "rule_versions",
            "rule_evidence_mappings",
            "scan_analyses",
            "analysis_ingredients",
            "analysis_findings",
            "analysis_finding_evidence",
        }
        assert account_tables.issubset(tables)
        assert catalog_tables.issubset(tables)
        assert scan_tables.issubset(tables)
        assert analysis_tables.issubset(tables)

        command.downgrade(config, "0004_image_scans")
        engine = create_database_engine(database_url)
        try:
            with engine.connect() as connection:
                analysis_downgrade_revision = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                after_analysis_downgrade = set(
                    connection.exec_driver_sql(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).scalars()
                )
        finally:
            engine.dispose()
        assert analysis_downgrade_revision == "0004_image_scans"
        assert scan_tables.issubset(after_analysis_downgrade)
        assert analysis_tables.isdisjoint(after_analysis_downgrade)

        command.downgrade(config, "0003_ingredient_evidence")
        engine = create_database_engine(database_url)
        try:
            with engine.connect() as connection:
                scan_downgrade_revision = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                after_scan_downgrade = set(
                    connection.exec_driver_sql(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).scalars()
                )
        finally:
            engine.dispose()
        assert scan_downgrade_revision == "0003_ingredient_evidence"
        assert account_tables.issubset(after_scan_downgrade)
        assert catalog_tables.issubset(after_scan_downgrade)
        assert scan_tables.isdisjoint(after_scan_downgrade)
        assert analysis_tables.isdisjoint(after_scan_downgrade)

        command.downgrade(config, "0002_auth_profiles")
        engine = create_database_engine(database_url)
        try:
            with engine.connect() as connection:
                catalog_downgrade_revision = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                after_catalog_downgrade = set(
                    connection.exec_driver_sql(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).scalars()
                )
        finally:
            engine.dispose()
        assert catalog_downgrade_revision == "0002_auth_profiles"
        assert account_tables.issubset(after_catalog_downgrade)
        assert catalog_tables.isdisjoint(after_catalog_downgrade)

        command.downgrade(config, "0001_schema_baseline")
        engine = create_database_engine(database_url)
        try:
            with engine.connect() as connection:
                downgraded_revision = connection.execute(
                    text("SELECT version_num FROM alembic_version")
                ).scalar_one()
                remaining_tables = set(
                    connection.exec_driver_sql(
                        "SELECT name FROM sqlite_master WHERE type='table'"
                    ).scalars()
                )
        finally:
            engine.dispose()
        assert downgraded_revision == "0001_schema_baseline"
        assert account_tables.isdisjoint(remaining_tables)
        assert catalog_tables.isdisjoint(remaining_tables)
        assert scan_tables.isdisjoint(remaining_tables)
    finally:
        get_settings.cache_clear()
