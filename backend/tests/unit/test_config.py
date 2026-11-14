"""Configuration validation tests."""

import pytest
from pydantic import ValidationError

from backend.app.core.config import PROJECT_ROOT, Settings

PRODUCTION_MAIL = {"mail_host": "smtp.example.com", "mail_from": "no-reply@example.com"}


def test_allowed_origins_parse_as_explicit_origins() -> None:
    settings = Settings(allowed_origins="https://app.example.com, http://localhost:8000/")

    assert settings.allowed_origin_list == [
        "https://app.example.com",
        "http://localhost:8000",
    ]


def test_wildcard_cors_origin_is_rejected() -> None:
    with pytest.raises(ValidationError, match="explicit origins"):
        Settings(allowed_origins="*")


def test_origin_with_path_is_rejected() -> None:
    with pytest.raises(ValidationError, match="must not contain paths"):
        Settings(allowed_origins="https://app.example.com/dashboard")


def test_session_and_csrf_cookie_names_must_differ() -> None:
    with pytest.raises(ValidationError, match="must be different"):
        Settings(session_cookie_name="same", csrf_cookie_name="same")


def test_env_example_is_parseable_for_local_development() -> None:
    settings = Settings(_env_file=PROJECT_ROOT / ".env.example")

    assert settings.app_env == "development"
    assert settings.auth_expose_dev_tokens is True
    assert settings.mail_port == 587
    assert settings.private_scan_storage_dir.name == "scans"
    assert settings.scan_max_upload_bytes == 10 * 1024 * 1024
    assert settings.scan_max_image_pixels == 20_000_000
    assert settings.ocr_tesseract_language == "eng"
    assert settings.ollama_embed_model == "embeddinggemma"
    assert settings.ollama_chat_model is None
    assert settings.openai_chat_model is None
    assert settings.groq_chat_model is None
    assert settings.openai_api_key is None
    assert settings.groq_api_key is None
    assert settings.llm_timeout_seconds == 30
    assert settings.ai_consent_disclosure_version == "clarity-cloud-consent-v2"
    assert settings.qdrant_url is None
    assert settings.vector_db_path is not None
    assert settings.vector_db_path == settings.vector_db_path.resolve()
    assert settings.rag_top_k == 5
    assert not settings.mail_is_configured


def test_legacy_blank_mail_port_uses_default() -> None:
    assert Settings(mail_port="").mail_port == 587


def test_production_requires_long_secret() -> None:
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(
            app_env="production",
            app_secret_key="short",
            database_url="postgresql+psycopg://user:password@localhost/clarity",
            **PRODUCTION_MAIL,
        )


def test_production_requires_postgresql() -> None:
    with pytest.raises(ValidationError, match="requires a PostgreSQL"):
        Settings(
            app_env="production",
            app_secret_key="a" * 40,
            database_url="sqlite:///./data/local.db",
            **PRODUCTION_MAIL,
        )


def test_production_requires_mail_delivery() -> None:
    with pytest.raises(ValidationError, match="MAIL_HOST and MAIL_FROM"):
        Settings(
            app_env="production",
            app_secret_key="a" * 40,
            database_url="postgresql+psycopg://user:password@localhost/clarity",
        )


def test_settings_validation_errors_hide_database_credentials() -> None:
    private_password = "database-password-not-for-logs"
    with pytest.raises(ValidationError) as error:
        Settings(
            app_env="production",
            app_secret_key="a" * 40,
            database_url=f"mysql://user:{private_password}@localhost/clarity",
            **PRODUCTION_MAIL,
        )
    assert private_password not in str(error.value)


def test_production_rejects_dev_token_exposure() -> None:
    with pytest.raises(ValidationError, match="only in development/test"):
        Settings(
            app_env="production",
            app_secret_key="a" * 40,
            database_url="postgresql+psycopg://user:password@localhost/clarity",
            auth_expose_dev_tokens=True,
            **PRODUCTION_MAIL,
        )


def test_production_accepts_postgresql_secret_and_mail_settings() -> None:
    settings = Settings(
        app_env="production",
        app_secret_key="a" * 40,
        database_url="postgresql+psycopg://user:password@localhost/clarity",
        **PRODUCTION_MAIL,
    )

    assert settings.app_env == "production"
    assert settings.mail_is_configured


def test_qdrant_and_embedding_settings_have_explicit_single_backend() -> None:
    local = Settings(_env_file=None, vector_db_path="data/qdrant")
    assert local.vector_db_path is not None
    assert local.vector_db_path.name == "qdrant"

    remote = Settings(_env_file=None, qdrant_url="https://qdrant.example.com")
    assert remote.qdrant_url == "https://qdrant.example.com"
    assert remote.vector_db_path is None

    with pytest.raises(ValidationError, match="either QDRANT_URL or VECTOR_DB_PATH"):
        Settings(
            _env_file=None,
            qdrant_url="http://qdrant.example.com",
            vector_db_path="data/qdrant",
        )
    with pytest.raises(ValidationError, match="QDRANT_API_KEY requires QDRANT_URL"):
        Settings(_env_file=None, qdrant_api_key="secret-without-url")
    with pytest.raises(ValidationError, match="must not include credentials"):
        Settings(_env_file=None, qdrant_url="https://user:password@qdrant.example.com")


def test_chat_provider_settings_are_optional_and_validated() -> None:
    settings = Settings(
        _env_file=None,
        ollama_chat_model="gemma4",
        openai_api_key="openai-test-secret",
        openai_chat_model="gpt-example-mini",
        groq_api_key="groq-test-secret",
        groq_chat_model="openai/gpt-oss-20b",
        llm_timeout_seconds=15,
    )
    assert settings.ollama_chat_model == "gemma4"
    assert settings.openai_chat_model == "gpt-example-mini"
    assert settings.groq_chat_model == "openai/gpt-oss-20b"
    assert settings.openai_api_key is not None
    assert settings.groq_api_key is not None
    assert settings.llm_timeout_seconds == 15
    assert Settings(_env_file=None, openai_api_key=" ").openai_api_key is None

    with pytest.raises(ValidationError, match="Chat model name"):
        Settings(_env_file=None, groq_chat_model="invalid model name")
    with pytest.raises(ValidationError, match="LLM_TIMEOUT_SECONDS"):
        Settings(_env_file=None, llm_timeout_seconds=0)


def test_scan_and_ocr_settings_reject_unsafe_limits_or_arguments() -> None:
    with pytest.raises(ValidationError, match="SCAN_MAX_UPLOAD_BYTES"):
        Settings(scan_max_upload_bytes=0)
    with pytest.raises(ValidationError, match="SCAN_MAX_IMAGE_PIXELS"):
        Settings(scan_max_image_pixels=100_000_001)
    with pytest.raises(ValidationError, match="OCR_TESSERACT_LANGUAGE"):
        Settings(ocr_tesseract_language="eng;touch-file")
    with pytest.raises(ValidationError, match="OCR_TESSERACT_COMMAND"):
        Settings(ocr_tesseract_command=" ")
    with pytest.raises(ValidationError, match="PRIVATE_SCAN_STORAGE_DIR"):
        Settings(private_scan_storage_dir="/")
