"""FastAPI application factory and ASGI entry point."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from logging import getLogger
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError

from backend.app.api.upload_limits import ScanBodySizeLimitMiddleware
from backend.app.api.v1.routes.admin import router as admin_router
from backend.app.api.v1.routes.auth import router as auth_router
from backend.app.api.v1.routes.explanations import router as explanations_router
from backend.app.api.v1.routes.health import router as health_router
from backend.app.api.v1.routes.ingredients import router as ingredients_router
from backend.app.api.v1.routes.privacy import router as privacy_router
from backend.app.api.v1.routes.rules_admin import router as rules_admin_router
from backend.app.api.v1.routes.scans import router as scans_router
from backend.app.api.v1.routes.users import router as users_router
from backend.app.core.config import Settings, get_settings
from backend.app.core.logging_config import configure_logging
from backend.app.database.session import create_database_engine
from backend.app.services.auth.csrf import require_csrf
from backend.app.services.auth.rate_limit import InMemoryRateLimiter
from backend.app.services.rag.runtime import close_rag_state, initialize_rag_state

logger = getLogger(__name__)
FRONTEND_DIRECTORY = Path(__file__).resolve().parents[2] / "frontend"


def create_app(settings: Settings | None = None, db_engine: Engine | None = None) -> FastAPI:
    """Create an application instance; dependency injection keeps tests isolated."""
    resolved_settings = settings or get_settings()
    configure_logging(resolved_settings.log_level)

    owns_engine = db_engine is None
    resolved_engine = db_engine or create_database_engine(resolved_settings.database_url)

    @asynccontextmanager
    async def lifespan(application: FastAPI) -> AsyncIterator[None]:
        try:
            yield
        finally:
            close_rag_state(application)
            if owns_engine:
                resolved_engine.dispose()

    docs_enabled = resolved_settings.app_env in {"development", "test"}
    app = FastAPI(
        title=resolved_settings.app_name,
        version="0.1.0",
        debug=False,
        docs_url="/docs" if docs_enabled else None,
        redoc_url="/redoc" if docs_enabled else None,
        openapi_url="/openapi.json" if docs_enabled else None,
        lifespan=lifespan,
    )
    app.state.settings = resolved_settings
    app.state.db_engine = resolved_engine
    app.state.owns_db_engine = owns_engine
    initialize_rag_state(app)
    configured_secret = (
        resolved_settings.app_secret_key.get_secret_value()
        if resolved_settings.app_secret_key
        else secrets.token_urlsafe(32)
    )
    app.state.csrf_signing_key = hmac.new(
        configured_secret.encode("utf-8"), b"Clarity Checker CSRF signing key v1", hashlib.sha256
    ).digest()
    app.state.auth_rate_limiter = InMemoryRateLimiter()
    app.state.scan_rate_limiter = InMemoryRateLimiter()
    app.state.ai_explanation_rate_limiter = InMemoryRateLimiter()

    @app.exception_handler(RequestValidationError)
    async def sanitized_validation_error(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        """Return field locations/codes only; never echo passwords, tokens, or request values."""
        fields = [
            {
                "location": [str(part) for part in error.get("loc", ())],
                "code": str(error.get("type", "invalid")),
            }
            for error in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content={
                "detail": {
                    "code": "validation_error",
                    "message": "The request is invalid.",
                    "fields": fields,
                    "request_id": getattr(request.state, "request_id", None),
                }
            },
        )

    @app.exception_handler(SQLAlchemyError)
    async def sanitized_database_error(request: Request, _exc: SQLAlchemyError) -> JSONResponse:
        """Hide SQL text, parameters, and connection details from clients and logs."""
        request_id = getattr(request.state, "request_id", None)
        logger.error(
            "Database operation failed; request_id=%s error_type=%s",
            request_id,
            type(_exc).__name__,
        )
        return JSONResponse(
            status_code=503,
            content={
                "detail": {
                    "code": "database_unavailable",
                    "message": "The request could not be completed right now.",
                    "request_id": request_id,
                }
            },
        )

    @app.middleware("http")
    async def add_security_headers(request: Request, call_next):
        """Add baseline browser security headers and a server-generated request ID."""
        request_id = uuid4().hex
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Cache-Control"] = "no-store"
        response.headers["Pragma"] = "no-cache"
        if resolved_settings.app_env in {"staging", "production"}:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; base-uri 'self'; object-src 'none'; "
                "form-action 'self'; script-src 'self'; "
                "style-src 'self' 'unsafe-inline'; img-src 'self' data:; "
                "connect-src 'self'; font-src 'self'; frame-ancestors 'none'"
            )
        return response

    if resolved_settings.allowed_origin_list:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=resolved_settings.allowed_origin_list,
            allow_credentials=True,
            allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
            allow_headers=["Content-Type", "X-CSRF-Token", "X-Request-ID"],
        )

    app.add_middleware(
        ScanBodySizeLimitMiddleware,
        max_request_bytes=resolved_settings.scan_max_upload_bytes + 64 * 1024,
        path="/api/v1/scans",
    )

    app.include_router(health_router)
    api_dependencies = [Depends(require_csrf)]
    app.include_router(auth_router, prefix="/api/v1", dependencies=api_dependencies)
    app.include_router(users_router, prefix="/api/v1", dependencies=api_dependencies)
    app.include_router(privacy_router, prefix="/api/v1", dependencies=api_dependencies)
    app.include_router(scans_router, prefix="/api/v1", dependencies=api_dependencies)
    app.include_router(explanations_router, prefix="/api/v1", dependencies=api_dependencies)
    app.include_router(ingredients_router, prefix="/api/v1", dependencies=api_dependencies)
    app.include_router(admin_router, prefix="/api/v1", dependencies=api_dependencies)
    app.include_router(rules_admin_router, prefix="/api/v1", dependencies=api_dependencies)
    if (FRONTEND_DIRECTORY / "index.html").is_file():

        def serve_frontend_index() -> FileResponse:
            """Serve the same-origin vanilla frontend shell at the application root."""
            return FileResponse(FRONTEND_DIRECTORY / "index.html")

        app.add_api_route(
            "/",
            serve_frontend_index,
            methods=["GET"],
            include_in_schema=False,
        )
        app.mount(
            "/static",
            StaticFiles(directory=str(FRONTEND_DIRECTORY)),
            name="frontend-static",
        )
    return app


app = create_app()
