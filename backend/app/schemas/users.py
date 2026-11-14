"""User, profile, declared-term, consent, and privacy-export schemas."""

from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_validator

from backend.app.schemas.analysis import ScanAnalysisRead
from backend.app.schemas.scans import ScanRead

SkinType = Literal["dry", "oily", "combination", "normal", "sensitive", "unsure"]
DeclarationType = Literal["sensitivity", "allergy", "preference", "avoid"]
CloudProvider = Literal["openai", "groq"]


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    email: EmailStr
    display_name: str | None
    email_verified_at: datetime
    created_at: datetime


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    display_name: str | None = Field(default=None, max_length=120)

    @field_validator("display_name")
    @classmethod
    def normalize_display_name(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = " ".join(value.split())
        if not normalized:
            return None
        if len(normalized) > 120:
            raise ValueError("Display name must be 120 characters or fewer")
        return normalized


class UserProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    skin_type: SkinType | None
    concerns: list[str]
    locale: str | None
    user_reported: Literal[True] = True
    updated_at: datetime


Concern = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]


class UserProfilePatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    skin_type: SkinType | None = None
    concerns: list[Concern] | None = Field(default=None, max_length=10)
    locale: str | None = Field(default=None, max_length=20)

    @field_validator("locale")
    @classmethod
    def normalize_locale(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            return None
        if any(character.isspace() for character in normalized):
            raise ValueError("Locale must not contain whitespace")
        return normalized

    @field_validator("concerns")
    @classmethod
    def normalize_concerns(cls, value: list[str] | None) -> list[str] | None:
        if value is None:
            return None
        normalized = [" ".join(item.split()) for item in value]
        if any(not item for item in normalized):
            raise ValueError("Concerns must not be blank")
        if len({item.casefold() for item in normalized}) != len(normalized):
            raise ValueError("Concerns must not contain duplicates")
        return normalized


class DeclaredIngredientCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: str = Field(min_length=1, max_length=200)
    declaration_type: DeclarationType

    @field_validator("term")
    @classmethod
    def normalize_term(cls, value: str) -> str:
        normalized = " ".join(value.split())
        if not normalized:
            raise ValueError("Declared term must not be blank")
        return normalized


class DeclaredIngredientRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    term: str
    declaration_type: DeclarationType
    created_at: datetime
    user_reported: Literal[True] = True


class AiConsentGrant(BaseModel):
    model_config = ConfigDict(extra="forbid")

    disclosure_version: str = Field(min_length=1, max_length=80)
    accepted: Literal[True]


class AiConsentRead(BaseModel):
    provider: CloudProvider
    enabled: bool
    current_disclosure_version: str
    granted_at: datetime | None = None
    revoked_at: datetime | None = None


class AiConsentListResponse(BaseModel):
    current_disclosure_version: str
    disclosure_text: str
    providers: list[AiConsentRead]


class PrivacyExport(BaseModel):
    export_version: Literal[1] = 1
    exported_at: datetime
    user: UserRead
    profile: UserProfileRead | None
    declared_ingredients: list[DeclaredIngredientRead]
    ai_provider_consents: list[AiConsentRead]
    scans: list[ScanRead]
    analyses: list[ScanAnalysisRead] = Field(default_factory=list)
