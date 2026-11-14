"""Private image-scan, OCR, ingredient-draft, and confirmation API schemas."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator

ScanStatus = Literal[
    "queued",
    "extracting",
    "needs_confirmation",
    "confirmed",
    "failed",
]
OcrStatus = Literal["queued", "running", "succeeded", "unavailable", "failed"]
DraftIngredientText = Annotated[
    str,
    StringConstraints(strip_whitespace=True, min_length=1, max_length=300),
]


class OcrBoundingBox(BaseModel):
    """Pixel-coordinate rectangle returned by the local OCR engine, when available."""

    left: int = Field(ge=0)
    top: int = Field(ge=0)
    width: int = Field(ge=0)
    height: int = Field(ge=0)


class OcrTokenRead(BaseModel):
    """Unconfirmed OCR word and its engine-reported confidence, if supplied."""

    text: str = Field(min_length=1, max_length=1000)
    confidence: float | None = Field(default=None, ge=0, le=100)
    box: OcrBoundingBox | None = None


class ScanIngredientRead(BaseModel):
    """A corrected draft entry, marked confirmed only after explicit user approval."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    position: int = Field(ge=0)
    text: str
    confidence: float | None = Field(default=None, ge=0, le=100)
    user_confirmed: bool


class ScanRead(BaseModel):
    """A user's scan state; raw OCR is never implied to be user-confirmed."""

    id: UUID
    status: ScanStatus
    ocr_status: OcrStatus
    ocr_text: str | None
    ocr_tokens: list[OcrTokenRead]
    ocr_confidence: float | None = Field(default=None, ge=0, le=100)
    ocr_engine: str | None
    ocr_engine_version: str | None
    ocr_error_code: str | None
    created_at: datetime
    updated_at: datetime
    ocr_completed_at: datetime | None
    confirmed_at: datetime | None
    ingredients: list[ScanIngredientRead]
    photo_available: bool
    photo_download_url: str | None


class ScanSummary(BaseModel):
    """Compact row for current-user scan history."""

    id: UUID
    status: ScanStatus
    ocr_status: OcrStatus
    ocr_confidence: float | None = Field(default=None, ge=0, le=100)
    ocr_error_code: str | None
    created_at: datetime
    updated_at: datetime
    confirmed_at: datetime | None
    photo_available: bool


class ScanListResponse(BaseModel):
    items: list[ScanSummary]
    total: int = Field(ge=0)
    limit: int = Field(ge=1, le=100)
    offset: int = Field(ge=0)


class ScanIngredientsPatch(BaseModel):
    """Replace the complete, still-unconfirmed ingredient draft in display order."""

    model_config = ConfigDict(extra="forbid")

    items: list[DraftIngredientText] = Field(max_length=300)

    @field_validator("items")
    @classmethod
    def normalize_items(cls, value: list[str]) -> list[str]:
        normalized = [" ".join(item.split()) for item in value]
        if any(not item for item in normalized):
            raise ValueError("Ingredient draft items must not be blank")
        return normalized


class ScanConfirmationRequest(BaseModel):
    """Require an explicit affirmative action before marking scan text confirmed."""

    model_config = ConfigDict(extra="forbid")

    accepted: Literal[True]


class ScanExport(BaseModel):
    """Exportable scan history and an authenticated path to retrieve retained photos."""

    scans: list[ScanRead]
