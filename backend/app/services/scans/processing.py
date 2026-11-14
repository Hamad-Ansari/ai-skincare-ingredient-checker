"""Persisted in-process OCR job runner for local development and M5 tests."""

from __future__ import annotations

from datetime import UTC, datetime
from logging import getLogger
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from backend.app.core.config import Settings
from backend.app.models.scans import Scan
from backend.app.services.ocr.tesseract import (
    OcrProcessingError,
    OcrTimeoutError,
    OcrUnavailableError,
    TesseractOcrEngine,
)
from backend.app.services.scans.storage import PrivateScanStorage

logger = getLogger(__name__)


def _now() -> datetime:
    return datetime.now(UTC)


def process_scan_ocr(scan_id: UUID, user_id: UUID, engine: Engine, settings: Settings) -> None:
    """Run one queued scan, recording an explicit state even when OCR is unavailable.

    This BackgroundTasks worker is intentionally in-process and non-durable. A later
    deployment worker can invoke the same adapter/orchestration contract from a queue.
    """
    try:
        with Session(engine) as db:
            scan = db.scalar(select(Scan).where(Scan.id == scan_id, Scan.user_id == user_id))
            if scan is None or scan.status != "queued":
                return
            scan.status = "extracting"
            scan.ocr_status = "running"
            scan.updated_at = _now()
            image_key = scan.image_key
            db.commit()

        result = None
        error_code: str | None = None
        ocr_status = "succeeded"
        try:
            if image_key is None:
                raise OcrProcessingError("Scan image reference is missing")
            image_bytes = PrivateScanStorage.from_settings(settings).read(user_id, image_key)
            result = TesseractOcrEngine(
                settings.ocr_tesseract_command,
                settings.ocr_tesseract_language,
                settings.ocr_timeout_seconds,
            ).extract(image_bytes)
        except OcrUnavailableError:
            ocr_status = "unavailable"
            error_code = "ocr_engine_unavailable"
        except OcrTimeoutError:
            ocr_status = "failed"
            error_code = "ocr_timeout"
        except OcrProcessingError:
            ocr_status = "failed"
            error_code = "ocr_failed"
        except OSError:
            ocr_status = "failed"
            error_code = "scan_photo_unavailable"
        except Exception:
            ocr_status = "failed"
            error_code = "ocr_failed"
            logger.error("Unexpected OCR processing failure; scan_id=%s", scan_id)

        with Session(engine) as db:
            scan = db.scalar(select(Scan).where(Scan.id == scan_id, Scan.user_id == user_id))
            if scan is None or scan.status != "extracting":
                return
            scan.status = "needs_confirmation"
            scan.ocr_status = ocr_status
            scan.ocr_error_code = error_code
            scan.ocr_completed_at = _now()
            scan.updated_at = _now()
            if result is not None:
                scan.ocr_text = result.text
                scan.ocr_confidence = result.confidence
                scan.ocr_engine = result.engine
                scan.ocr_engine_version = result.engine_version
                scan.ocr_tokens = [
                    {
                        "text": token.text,
                        "confidence": token.confidence,
                        "box": (
                            {
                                "left": token.box.left,
                                "top": token.box.top,
                                "width": token.box.width,
                                "height": token.box.height,
                            }
                            if token.box is not None
                            else None
                        ),
                    }
                    for token in result.tokens
                ]
            db.commit()
    except Exception:
        # Do not log exception text: DB/storage errors can include private filesystem paths.
        logger.error("Could not persist scan OCR job state; scan_id=%s", scan_id)
