"""Authenticated upload, review, retrieval, and deletion APIs for private scans."""

from __future__ import annotations

from datetime import UTC, datetime
from logging import getLogger
from typing import Annotated
from uuid import UUID, uuid4

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Query,
    Request,
    Response,
    status,
)
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile as StarletteUploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException

from backend.app.api.dependencies import CurrentUser
from backend.app.database.dependencies import get_db_session
from backend.app.models.safety_rules import ScanAnalysis
from backend.app.models.scans import Scan, ScanIngredient
from backend.app.schemas.analysis import ScanAnalysisRead
from backend.app.schemas.scans import (
    ScanConfirmationRequest,
    ScanIngredientsPatch,
    ScanListResponse,
    ScanRead,
)
from backend.app.services.auth.rate_limit import RateLimitExceeded
from backend.app.services.rag.runtime import RagRuntimeUnavailable, get_rag_services
from backend.app.services.scans.analysis import (
    ScanAnalysisInputError,
    run_scan_analysis,
    serialize_scan_analysis,
)
from backend.app.services.scans.images import ImageValidationError, sanitize_image
from backend.app.services.scans.processing import process_scan_ocr
from backend.app.services.scans.serialization import scan_to_read, scan_to_summary
from backend.app.services.scans.storage import PrivateScanStorage

logger = getLogger(__name__)
router = APIRouter(prefix="/scans", tags=["scans"])
DbSession = Annotated[Session, Depends(get_db_session)]

_SCAN_UPLOAD_OPENAPI = {
    "requestBody": {
        "required": True,
        "content": {
            "multipart/form-data": {
                "schema": {
                    "type": "object",
                    "required": ["image"],
                    "properties": {"image": {"type": "string", "format": "binary"}},
                }
            }
        },
    }
}


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"code": "not_found", "message": "Scan not found."},
    )


def _scan_or_404(db: Session, scan_id: UUID, user_id: UUID) -> Scan:
    scan = db.scalar(select(Scan).where(Scan.id == scan_id, Scan.user_id == user_id))
    if scan is None:
        raise _not_found()
    return scan


def _check_scan_upload_rate(request: Request, user_id: UUID) -> None:
    limiter = request.app.state.scan_rate_limiter
    client_host = request.client.host if request.client is not None else "unknown"
    try:
        limiter.check(f"scan-upload:user:{user_id}", limit=8, window_seconds=3600)
        limiter.check(f"scan-upload:ip:{client_host}", limit=40, window_seconds=3600)
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "rate_limited", "message": "Too many image uploads. Try again later."},
            headers={"Retry-After": str(exc.retry_after)},
        ) from exc


@router.post(
    "",
    response_model=ScanRead,
    status_code=status.HTTP_202_ACCEPTED,
    openapi_extra=_SCAN_UPLOAD_OPENAPI,
)
async def upload_scan(
    request: Request,
    background_tasks: BackgroundTasks,
    user: CurrentUser,
    db: DbSession,
) -> ScanRead:
    """Validate actual image bytes, save a private sanitized copy, and queue local OCR."""
    settings = request.app.state.settings
    _check_scan_upload_rate(request, user.id)

    try:
        form = await request.form(
            max_files=1,
            max_fields=0,
            max_part_size=settings.scan_max_upload_bytes,
        )
    except StarletteHTTPException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "invalid_upload", "message": "Provide exactly one image file."},
        ) from exc

    try:
        items = list(form.multi_items())
        if (
            len(items) != 1
            or items[0][0] != "image"
            or not isinstance(items[0][1], StarletteUploadFile)
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "code": "invalid_upload",
                    "message": "Provide one file in the image field.",
                },
            )
        uploaded_file = items[0][1]
        image_bytes = await uploaded_file.read(settings.scan_max_upload_bytes + 1)
    finally:
        await form.close()

    try:
        sanitized = sanitize_image(
            image_bytes,
            max_bytes=settings.scan_max_upload_bytes,
            max_pixels=settings.scan_max_image_pixels,
        )
    except ImageValidationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    storage = PrivateScanStorage.from_settings(settings)
    try:
        image_key = storage.store(user.id, sanitized.data)
    except OSError as exc:
        logger.error("Could not save a private scan image; user_id=%s", user.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": "scan_storage_unavailable", "message": "The scan could not be stored."},
        ) from exc

    scan = Scan(
        id=uuid4(),
        user_id=user.id,
        status="queued",
        ocr_status="queued",
        image_key=image_key,
        image_bytes=len(sanitized.data),
        image_width=sanitized.width,
        image_height=sanitized.height,
        image_content_type=sanitized.content_type,
        ocr_tokens=[],
    )
    db.add(scan)
    try:
        db.commit()
        db.refresh(scan)
    except Exception:
        db.rollback()
        try:
            storage.delete(user.id, image_key)
        except OSError:
            logger.error("Could not remove an unreferenced scan image; user_id=%s", user.id)
        raise

    engine: Engine = request.app.state.db_engine
    background_tasks.add_task(process_scan_ocr, scan.id, user.id, engine, settings)
    return scan_to_read(scan, db, user.id, settings)


@router.get("", response_model=ScanListResponse)
def list_scans(
    request: Request,
    user: CurrentUser,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> ScanListResponse:
    """List only the authenticated user's scans, newest first."""
    filters = Scan.user_id == user.id
    total = db.scalar(select(func.count()).select_from(Scan).where(filters)) or 0
    scans = db.scalars(
        select(Scan)
        .where(filters)
        .order_by(Scan.created_at.desc(), Scan.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return ScanListResponse(
        items=[scan_to_summary(scan, user.id, request.app.state.settings) for scan in scans],
        total=total,
        limit=limit,
        offset=offset,
    )


@router.get("/{scan_id}", response_model=ScanRead)
def get_scan(
    scan_id: UUID,
    request: Request,
    user: CurrentUser,
    db: DbSession,
) -> ScanRead:
    """Return OCR state and the unconfirmed draft for an owned scan."""
    scan = _scan_or_404(db, scan_id, user.id)
    return scan_to_read(scan, db, user.id, request.app.state.settings)


@router.patch("/{scan_id}/ingredients", response_model=ScanRead)
def replace_scan_ingredients(
    scan_id: UUID,
    payload: ScanIngredientsPatch,
    request: Request,
    user: CurrentUser,
    db: DbSession,
) -> ScanRead:
    """Replace the complete draft while the scan is awaiting explicit confirmation."""
    scan = _scan_or_404(db, scan_id, user.id)
    if scan.status != "needs_confirmation" or scan.confirmed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "scan_not_editable", "message": "This scan is not awaiting review."},
        )

    scan.ingredients.clear()
    for position, ingredient_text in enumerate(payload.items):
        scan.ingredients.append(
            ScanIngredient(
                position=position,
                text=ingredient_text,
                confidence=None,
                user_confirmed=False,
            )
        )
    scan.updated_at = datetime.now(UTC)
    db.commit()
    db.refresh(scan)
    return scan_to_read(scan, db, user.id, request.app.state.settings)


@router.post("/{scan_id}/confirm", response_model=ScanRead)
def confirm_scan_ingredients(
    scan_id: UUID,
    payload: ScanConfirmationRequest,
    request: Request,
    user: CurrentUser,
    db: DbSession,
) -> ScanRead:
    """Mark the reviewed ingredient draft as user-confirmed; OCR alone cannot do so."""
    scan = _scan_or_404(db, scan_id, user.id)
    if scan.status != "needs_confirmation" or scan.confirmed_at is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "scan_not_ready", "message": "This scan is not awaiting confirmation."},
        )
    ingredients = db.scalars(
        select(ScanIngredient)
        .where(ScanIngredient.scan_id == scan.id)
        .order_by(ScanIngredient.position, ScanIngredient.id)
    ).all()
    if not ingredients:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "ingredient_draft_empty",
                "message": "Add at least one ingredient before confirming this scan.",
            },
        )

    now = datetime.now(UTC)
    for ingredient in ingredients:
        ingredient.user_confirmed = True
        ingredient.updated_at = now
    scan.status = "confirmed"
    scan.confirmed_at = now
    scan.updated_at = now
    db.commit()
    db.refresh(scan)
    return scan_to_read(scan, db, user.id, request.app.state.settings)


@router.post(
    "/{scan_id}/analysis",
    response_model=ScanAnalysisRead,
    status_code=status.HTTP_201_CREATED,
)
def create_scan_analysis(
    scan_id: UUID,
    request: Request,
    user: CurrentUser,
    db: DbSession,
) -> ScanAnalysisRead:
    """Analyze only explicitly confirmed user entries with current exact matches and rules."""
    scan = _scan_or_404(db, scan_id, user.id)
    if scan.status != "confirmed" or scan.confirmed_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "scan_not_confirmed",
                "message": "Review and explicitly confirm this scan before analysis.",
            },
        )
    scan_items = db.scalars(
        select(ScanIngredient)
        .where(ScanIngredient.scan_id == scan.id)
        .order_by(ScanIngredient.position, ScanIngredient.id)
    ).all()
    if not scan_items or any(not item.user_confirmed for item in scan_items):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "scan_not_confirmed",
                "message": "Every analysis entry must be explicitly confirmed.",
            },
        )

    rag_unavailable = False
    try:
        store, embedder = get_rag_services(request)
    except RagRuntimeUnavailable:
        logger.warning("Configured retrieval service could not be initialized")
        store, embedder = None, None
        rag_unavailable = True
    try:
        analysis = run_scan_analysis(
            db,
            scan,
            user.id,
            store,
            embedder,
            request.app.state.settings.rag_top_k,
            rag_unavailable=rag_unavailable,
        )
    except ScanAnalysisInputError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "scan_not_confirmed", "message": str(exc)},
        ) from exc
    db.commit()
    db.refresh(analysis)
    return serialize_scan_analysis(db, analysis)


@router.get("/{scan_id}/analysis", response_model=ScanAnalysisRead)
def get_scan_analysis(
    scan_id: UUID,
    user: CurrentUser,
    db: DbSession,
) -> ScanAnalysisRead:
    """Return the latest owner-scoped analysis with current citation validation."""
    _scan_or_404(db, scan_id, user.id)
    analysis = db.scalar(
        select(ScanAnalysis)
        .where(ScanAnalysis.scan_id == scan_id)
        .order_by(ScanAnalysis.created_at.desc(), ScanAnalysis.id.desc())
    )
    if analysis is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "analysis_not_found",
                "message": "No analysis is available for this scan.",
            },
        )
    return serialize_scan_analysis(db, analysis)


@router.get("/{scan_id}/photo")
def retrieve_scan_photo(
    scan_id: UUID,
    request: Request,
    user: CurrentUser,
    db: DbSession,
) -> Response:
    """Retrieve the sanitized retained photo only for its owning authenticated user."""
    scan = _scan_or_404(db, scan_id, user.id)
    if scan.image_key is None:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "code": "scan_photo_unavailable",
                "message": "The retained photo is unavailable.",
            },
        )
    try:
        photo = PrivateScanStorage.from_settings(request.app.state.settings).read(
            user.id, scan.image_key
        )
    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail={
                "code": "scan_photo_unavailable",
                "message": "The retained photo is unavailable.",
            },
        ) from exc
    except (OSError, ValueError) as exc:
        logger.error("Could not retrieve a private scan image; scan_id=%s", scan.id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={
                "code": "scan_photo_unavailable",
                "message": "The retained photo is unavailable.",
            },
        ) from exc

    return Response(
        content=photo,
        media_type="image/jpeg",
        headers={
            "Content-Disposition": f'attachment; filename="scan-{scan.id}.jpg"',
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
        },
    )


@router.delete("/{scan_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scan(
    scan_id: UUID,
    request: Request,
    user: CurrentUser,
    db: DbSession,
) -> Response:
    """Delete an owned scan and its sanitized photo; missing files are idempotent."""
    scan = _scan_or_404(db, scan_id, user.id)
    if scan.image_key is not None:
        try:
            PrivateScanStorage.from_settings(request.app.state.settings).delete(
                user.id, scan.image_key
            )
        except (OSError, ValueError) as exc:
            logger.error("Could not delete a private scan image; scan_id=%s", scan.id)
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail={
                    "code": "scan_deletion_unavailable",
                    "message": "The scan could not be deleted right now.",
                },
            ) from exc
    db.delete(scan)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
