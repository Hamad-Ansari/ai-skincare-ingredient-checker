"""Liveness and readiness endpoints."""

import logging

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from backend.app.database.session import check_database
from backend.app.schemas.health import HealthResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/health", tags=["health"])


@router.get("/live", response_model=HealthResponse)
def liveness() -> HealthResponse:
    """Report that the API process is running without checking dependencies."""
    return HealthResponse(status="ok")


@router.get(
    "/ready",
    response_model=HealthResponse,
    responses={
        503: {"model": HealthResponse, "description": "A required dependency is unavailable"}
    },
)
def readiness(request: Request) -> HealthResponse | JSONResponse:
    """Report readiness after a safe database connection check."""
    try:
        check_database(request.app.state.db_engine)
    except SQLAlchemyError as exc:
        # Do not return or log the database exception text; it can contain connection details.
        logger.warning("Database readiness check failed (%s)", type(exc).__name__)
        return JSONResponse(status_code=503, content={"status": "not_ready"})

    return HealthResponse(status="ok")
