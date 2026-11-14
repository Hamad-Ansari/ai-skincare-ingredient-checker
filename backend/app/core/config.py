"""Validated application settings loaded from environment and the project .env file."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal, Self
from urllib.parse import urlsplit

from pydantic import EmailStr, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    """Runtime settings with safe development defaults and stricter production checks."""

    app_name: str = "Clarity Checker API"
    app_env: Literal["development", "test", "staging", "production"] = "development"
    app_secret_key: SecretStr | None = None
    database_url: str = "sqlite:///./data/clarity_checker.db"
    allowed_origins: str = ""
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"

    session_cookie_name: str = "clarity_session"
    csrf_cookie_name: str = "clarity_csrf"
    session_ttl_hours: int = 12
    verification_token_ttl_hours: int = 24
    password_reset_token_ttl_minutes: int = 30
    auth_expose_dev_tokens: bool = False
    ai_consent_disclosure_version: str = "clarity-cloud-consent-v2"

    private_scan_storage_dir: Path = PROJECT_ROOT / "data" / "private" / "scans"
    scan_max_upload_bytes: int = 10 * 1024 * 1024
    scan_max_image_pixels: int = 20_000_000
    ocr_tesseract_command: str = "tesseract"
    ocr_tesseract_language: str = "eng"
    ocr_timeout_seconds: int = 30

    ollama_base_url: str = "http://127.0.0.1:11434"
    ollama_embed_model: str = "embeddinggemma"
    qdrant_url: str | None = None
    qdrant_api_key: SecretStr | None = None
    vector_db_path: Path | None = None
    qdrant_collection: str = "clarity_evidence_v1"
    rag_embedding_timeout_seconds: int = 30
    rag_top_k: int = 5

    ollama_chat_model: str | None = None
    openai_api_key: SecretStr | None = None
    openai_chat_model: str | None = None
    groq_api_key: SecretStr | None = None
    groq_chat_model: str | None = None
    llm_timeout_seconds: int = 30

    mail_host: str | None = None
    mail_port: int = 587
    mail_username: str | None = None
    mail_password: SecretStr | None = None
    mail_from: EmailStr | None = None
    mail_starttls: bool = True

    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        hide_input_in_errors=True,
    )

    @field_validator("app_secret_key", mode="before")
    @classmethod
    def blank_secret_is_missing(cls, value: object) -> object:
        """Treat an empty optional secret as unset, especially in copied .env examples."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("mail_host", "mail_username", mode="before")
    @classmethod
    def normalize_mail_text(cls, value: object) -> object:
        """Normalize optional SMTP host/login values and accept blank placeholders."""
        if isinstance(value, str):
            normalized = value.strip()
            return normalized or None
        return value

    @field_validator("mail_password", "mail_from", mode="before")
    @classmethod
    def blank_mail_values_are_missing(cls, value: object) -> object:
        """Allow blank placeholders in `.env.example` for optional mail settings."""
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("database_url")
    @classmethod
    def validate_database_url(cls, value: str) -> str:
        """Reject empty/whitespace database URLs before the engine is constructed."""
        normalized = value.strip()
        if not normalized:
            raise ValueError("DATABASE_URL must not be empty")
        return normalized

    @field_validator("allowed_origins")
    @classmethod
    def validate_allowed_origins(cls, value: str) -> str:
        """Accept a comma-separated list of explicit HTTP(S) origins, never a wildcard."""
        origins = [origin.strip().rstrip("/") for origin in value.split(",") if origin.strip()]
        if "*" in origins:
            raise ValueError("ALLOWED_ORIGINS must list explicit origins; '*' is not allowed")

        for origin in origins:
            parsed = urlsplit(origin)
            if parsed.scheme not in {"http", "https"} or not parsed.hostname:
                raise ValueError(f"Invalid allowed origin: {origin}")
            if parsed.path or parsed.query or parsed.fragment or parsed.username or parsed.password:
                raise ValueError(f"Allowed origins must not contain paths or credentials: {origin}")
            try:
                _ = parsed.port
            except ValueError as exc:
                raise ValueError(f"Invalid port in allowed origin: {origin}") from exc

        return ",".join(dict.fromkeys(origins))

    @field_validator("session_cookie_name", "csrf_cookie_name")
    @classmethod
    def validate_cookie_name(cls, value: str) -> str:
        """Restrict cookie names to simple RFC-token characters."""
        if not value or any(
            not (character.isalnum() or character in "!#$%&'*+-.^_`|~") for character in value
        ):
            raise ValueError("Cookie names must contain only token characters")
        return value

    @field_validator("session_ttl_hours")
    @classmethod
    def validate_session_ttl(cls, value: int) -> int:
        if not 1 <= value <= 168:
            raise ValueError("SESSION_TTL_HOURS must be between 1 and 168")
        return value

    @field_validator("verification_token_ttl_hours")
    @classmethod
    def validate_verification_ttl(cls, value: int) -> int:
        if not 1 <= value <= 168:
            raise ValueError("VERIFICATION_TOKEN_TTL_HOURS must be between 1 and 168")
        return value

    @field_validator("password_reset_token_ttl_minutes")
    @classmethod
    def validate_password_reset_ttl(cls, value: int) -> int:
        if not 5 <= value <= 120:
            raise ValueError("PASSWORD_RESET_TOKEN_TTL_MINUTES must be between 5 and 120")
        return value

    @field_validator("mail_port", mode="before")
    @classmethod
    def validate_mail_port(cls, value: object) -> object:
        if value is None or (isinstance(value, str) and not value.strip()):
            return 587
        if isinstance(value, int) and not 1 <= value <= 65535:
            raise ValueError("MAIL_PORT must be between 1 and 65535")
        if isinstance(value, str) and value.strip().isdigit():
            port = int(value.strip())
            if not 1 <= port <= 65535:
                raise ValueError("MAIL_PORT must be between 1 and 65535")
            return port
        return value

    @field_validator("private_scan_storage_dir", mode="before")
    @classmethod
    def validate_private_scan_storage_dir(cls, value: object) -> object:
        """Reject blank storage paths instead of accidentally writing into the working tree."""
        if isinstance(value, str) and not value.strip():
            raise ValueError("PRIVATE_SCAN_STORAGE_DIR must not be empty")
        return value

    @field_validator("private_scan_storage_dir")
    @classmethod
    def resolve_private_scan_storage_dir(cls, value: Path) -> Path:
        """Anchor relative paths at the project root and reject unsafe filesystem roots."""
        candidate = value.expanduser()
        resolved = (candidate if candidate.is_absolute() else PROJECT_ROOT / candidate).resolve()
        if resolved == Path(resolved.anchor) or resolved == PROJECT_ROOT:
            raise ValueError("PRIVATE_SCAN_STORAGE_DIR must be a private subdirectory")
        return resolved

    @field_validator("scan_max_upload_bytes")
    @classmethod
    def validate_scan_upload_limit(cls, value: int) -> int:
        if not 1024 <= value <= 50 * 1024 * 1024:
            raise ValueError("SCAN_MAX_UPLOAD_BYTES must be between 1024 and 52428800")
        return value

    @field_validator("scan_max_image_pixels")
    @classmethod
    def validate_scan_pixel_limit(cls, value: int) -> int:
        if not 1 <= value <= 100_000_000:
            raise ValueError("SCAN_MAX_IMAGE_PIXELS must be between 1 and 100000000")
        return value

    @field_validator("ocr_tesseract_command", mode="before")
    @classmethod
    def validate_tesseract_command(cls, value: object) -> object:
        if not isinstance(value, str) or not value.strip() or len(value.strip()) > 500:
            raise ValueError("OCR_TESSERACT_COMMAND must name a non-empty executable")
        return value.strip()

    @field_validator("ocr_tesseract_language")
    @classmethod
    def validate_tesseract_language(cls, value: str) -> str:
        normalized = value.strip()
        if (
            not normalized
            or len(normalized) > 80
            or any(not (character.isalnum() or character in "_+.-") for character in normalized)
        ):
            raise ValueError("OCR_TESSERACT_LANGUAGE contains unsupported characters")
        return normalized

    @field_validator("ocr_timeout_seconds")
    @classmethod
    def validate_ocr_timeout(cls, value: int) -> int:
        if not 1 <= value <= 120:
            raise ValueError("OCR_TIMEOUT_SECONDS must be between 1 and 120")
        return value

    @field_validator("qdrant_url", mode="before")
    @classmethod
    def blank_qdrant_url_is_missing(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("qdrant_api_key", "openai_api_key", "groq_api_key", mode="before")
    @classmethod
    def blank_optional_api_keys_are_missing(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("ollama_chat_model", "openai_chat_model", "groq_chat_model", mode="before")
    @classmethod
    def blank_chat_models_are_missing(cls, value: object) -> object:
        if isinstance(value, str):
            return value.strip() or None
        return value

    @field_validator("vector_db_path", mode="before")
    @classmethod
    def blank_vector_path_is_missing(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value

    @field_validator("qdrant_url", "ollama_base_url")
    @classmethod
    def validate_service_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip().rstrip("/")
        parsed = urlsplit(normalized)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("Vector and embedding service URLs must be explicit HTTP(S) URLs")
        if parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError(
                "Service URLs must not include credentials, query strings, or fragments"
            )
        try:
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("Service URL has an invalid port") from exc
        return normalized

    @field_validator("vector_db_path")
    @classmethod
    def resolve_vector_db_path(cls, value: Path | None) -> Path | None:
        if value is None:
            return None
        candidate = value.expanduser()
        resolved = (candidate if candidate.is_absolute() else PROJECT_ROOT / candidate).resolve()
        if resolved in {Path(resolved.anchor), PROJECT_ROOT}:
            raise ValueError("VECTOR_DB_PATH must be a private subdirectory")
        return resolved

    @field_validator("ollama_embed_model")
    @classmethod
    def validate_ollama_embedding_model(cls, value: str) -> str:
        normalized = value.strip() or "embeddinggemma"
        if len(normalized) > 120 or any(
            not (character.isalnum() or character in ":._-+") for character in normalized
        ):
            raise ValueError("OLLAMA_EMBED_MODEL contains unsupported characters")
        return normalized

    @field_validator("ollama_chat_model", "openai_chat_model", "groq_chat_model")
    @classmethod
    def validate_chat_model_names(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if len(value) > 120 or any(
            not (character.isalnum() or character in ":._-/+") for character in value
        ):
            raise ValueError("Chat model name contains unsupported characters")
        return value

    @field_validator("llm_timeout_seconds")
    @classmethod
    def validate_llm_timeout(cls, value: int) -> int:
        if not 1 <= value <= 120:
            raise ValueError("LLM_TIMEOUT_SECONDS must be between 1 and 120")
        return value

    @field_validator("qdrant_collection")
    @classmethod
    def validate_qdrant_collection(cls, value: str) -> str:
        normalized = value.strip()
        if (
            not normalized
            or len(normalized) > 128
            or any(not (character.isalnum() or character in "_-.") for character in normalized)
        ):
            raise ValueError("QDRANT_COLLECTION contains unsupported characters")
        return normalized

    @field_validator("rag_embedding_timeout_seconds")
    @classmethod
    def validate_rag_embedding_timeout(cls, value: int) -> int:
        if not 1 <= value <= 120:
            raise ValueError("RAG_EMBEDDING_TIMEOUT_SECONDS must be between 1 and 120")
        return value

    @field_validator("rag_top_k")
    @classmethod
    def validate_rag_top_k(cls, value: int) -> int:
        if not 1 <= value <= 20:
            raise ValueError("RAG_TOP_K must be between 1 and 20")
        return value

    @field_validator("ai_consent_disclosure_version")
    @classmethod
    def validate_consent_disclosure_version(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or len(normalized) > 80:
            raise ValueError("AI_CONSENT_DISCLOSURE_VERSION must contain 1 to 80 characters")
        return normalized

    @property
    def allowed_origin_list(self) -> list[str]:
        """Return normalized origins for CORS middleware."""
        return [origin for origin in self.allowed_origins.split(",") if origin]

    @property
    def mail_is_configured(self) -> bool:
        """Whether the minimum outbound email settings are present."""
        return bool(self.mail_host and self.mail_from)

    @model_validator(mode="after")
    def validate_security_settings(self) -> Self:
        """Refuse insecure production defaults instead of silently starting."""
        if self.session_cookie_name == self.csrf_cookie_name:
            raise ValueError("SESSION_COOKIE_NAME and CSRF_COOKIE_NAME must be different")
        if bool(self.mail_username) != bool(self.mail_password):
            raise ValueError("MAIL_USERNAME and MAIL_PASSWORD must be configured together")
        if self.qdrant_url and self.vector_db_path:
            raise ValueError("Configure either QDRANT_URL or VECTOR_DB_PATH, not both")
        if self.qdrant_api_key and not self.qdrant_url:
            raise ValueError("QDRANT_API_KEY requires QDRANT_URL")
        if self.auth_expose_dev_tokens and self.app_env not in {"development", "test"}:
            raise ValueError("AUTH_EXPOSE_DEV_TOKENS is permitted only in development/test")

        if self.app_env in {"staging", "production"}:
            secret = self.app_secret_key.get_secret_value() if self.app_secret_key else ""
            if len(secret) < 32:
                raise ValueError(
                    "APP_SECRET_KEY must contain at least 32 characters in staging/production"
                )
            if not self.database_url.lower().startswith(("postgresql://", "postgresql+psycopg://")):
                raise ValueError("Staging/production requires a PostgreSQL DATABASE_URL")
            if not self.mail_is_configured:
                raise ValueError(
                    "Staging/production requires MAIL_HOST and MAIL_FROM for account email flows"
                )
            if not self.mail_starttls:
                raise ValueError("Staging/production SMTP must use STARTTLS")
        return self


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings object."""
    return Settings()
