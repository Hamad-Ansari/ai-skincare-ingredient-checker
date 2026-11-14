"""Source, ingredient, import-review, and public resolution schemas."""

from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import (
    AnyHttpUrl,
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from backend.app.services.ingredients.normalization import (
    normalize_ingredient_name,
    normalize_locale_tag,
)

ShortText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
LocatorText = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1024)
]
SourceType = Literal[
    "regulatory", "government", "scientific", "standards", "reference", "dataset", "other"
]
NameKind = Literal["inci", "source_name", "other"]
AliasType = Literal["inci", "common_name", "synonym", "abbreviation"]
EvidenceKind = Literal["identity", "composition", "regulatory", "research", "other"]


class EvidenceSourceCreate(BaseModel):
    """Register source metadata; reuse rights remain pending until a separate review."""

    model_config = ConfigDict(extra="forbid")

    publisher: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=180)
    ]
    title: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
    canonical_url: AnyHttpUrl
    source_type: SourceType
    license_name: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)
    ]
    license_url: AnyHttpUrl | None = None
    attribution_text: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=5, max_length=2000)
    ]
    source_version: Annotated[
        str | None, StringConstraints(strip_whitespace=True, max_length=100)
    ] = None
    checksum_sha256: Annotated[str | None, StringConstraints(pattern=r"^[0-9a-fA-F]{64}$")] = None
    retrieved_at: datetime | None = None

    @field_validator("canonical_url", "license_url")
    @classmethod
    def reject_url_credentials_and_tracking(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if value is None:
            return None
        parts = urlsplit(str(value))
        if parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError(
                "Source URLs must not contain credentials, query strings, or fragments"
            )
        return value

    @field_validator("checksum_sha256")
    @classmethod
    def normalize_checksum(cls, value: str | None) -> str | None:
        return value.lower() if value else None


class EvidenceSourceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    publisher: str
    title: str
    canonical_url: str
    source_type: str
    license_name: str
    license_url: str | None
    attribution_text: str
    source_version: str | None
    checksum_sha256: str | None
    retrieved_at: datetime | None
    rights_status: str
    can_reproduce_excerpt: bool
    rights_review_note: str | None
    rights_reviewed_at: datetime | None
    created_at: datetime


class EvidenceSourceRightsReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "restricted", "rejected"]
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)]
    can_reproduce_excerpt: bool = False

    @model_validator(mode="after")
    def excerpt_requires_approval(self) -> "EvidenceSourceRightsReview":
        if self.decision != "approved" and self.can_reproduce_excerpt:
            raise ValueError("Excerpt reproduction can be allowed only for an approved source")
        return self


class IngredientAliasInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    alias: ShortText
    alias_type: AliasType
    locale: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=2, max_length=35)
    ] = "und"
    source_locator: LocatorText | None = None

    @field_validator("locale")
    @classmethod
    def normalize_locale(cls, value: str) -> str:
        return normalize_locale_tag(value)

    @field_validator("alias")
    @classmethod
    def validate_normalized_length(cls, value: str) -> str:
        if len(normalize_ingredient_name(value)) > 240:
            raise ValueError("Normalized alias must be 240 characters or fewer")
        return value


class IngredientEvidenceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    evidence_kind: EvidenceKind
    summary: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1200)]
    scope: Annotated[str | None, StringConstraints(strip_whitespace=True, max_length=500)] = None
    locator: LocatorText
    excerpt: Annotated[
        str | None, StringConstraints(strip_whitespace=True, min_length=1, max_length=500)
    ] = None


class IngredientImportRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: ShortText
    name_kind: NameKind = "source_name"
    source_locator: LocatorText
    aliases: list[IngredientAliasInput] = Field(default_factory=list, max_length=30)
    evidence: list[IngredientEvidenceInput] = Field(default_factory=list, max_length=5)

    @field_validator("name")
    @classmethod
    def validate_normalized_name_length(cls, value: str) -> str:
        normalized = normalize_ingredient_name(value)
        if not normalized:
            raise ValueError("Ingredient name must not be blank")
        if len(normalized) > 240:
            raise ValueError("Normalized ingredient name must be 240 characters or fewer")
        return value

    @model_validator(mode="after")
    def aliases_must_be_distinct(self) -> "IngredientImportRecord":
        canonical = normalize_ingredient_name(self.name)
        seen: set[tuple[str, str]] = set()
        for alias in self.aliases:
            normalized = normalize_ingredient_name(alias.alias)
            key = (normalized, alias.locale)
            if normalized == canonical:
                raise ValueError("An alias must differ from the preferred ingredient name")
            if key in seen:
                raise ValueError("Duplicate normalized alias and locale in one ingredient record")
            if len(normalized) > 240:
                raise ValueError("Normalized alias must be 240 characters or fewer")
            seen.add(key)
        return self


class IngredientImportCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: UUID
    dataset_version: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=100)
    ]
    records: list[IngredientImportRecord] = Field(min_length=1, max_length=100)

    @model_validator(mode="after")
    def canonical_names_must_be_unique(self) -> "IngredientImportCreate":
        names = [normalize_ingredient_name(record.name) for record in self.records]
        if len(names) != len(set(names)):
            raise ValueError("An import batch cannot contain duplicate normalized ingredient names")
        return self


class IngredientImportRowReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=2000)]


class IngredientImportBatchReject(BaseModel):
    model_config = ConfigDict(extra="forbid")

    note: Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=2000)]


class IngredientImportRowRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    row_number: int
    normalized_name: str
    payload: dict[str, object]
    decision: str
    review_note: str | None
    reviewed_by: UUID | None
    reviewed_at: datetime | None


class IngredientImportBatchSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    source_id: UUID
    dataset_version: str
    content_sha256: str
    status: str
    row_count: int
    submitted_by: UUID | None
    activated_by: UUID | None
    created_at: datetime
    activated_at: datetime | None


class IngredientImportBatchRead(IngredientImportBatchSummary):
    rows: list[IngredientImportRowRead]


class IngredientResolutionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    term: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=240)]
    locale: Annotated[
        str | None, StringConstraints(strip_whitespace=True, min_length=2, max_length=35)
    ] = None

    @field_validator("term")
    @classmethod
    def validate_normalized_term(cls, value: str) -> str:
        normalized = normalize_ingredient_name(value)
        if len(normalized) > 240:
            raise ValueError("Normalized term must be 240 characters or fewer")
        return value

    @field_validator("locale")
    @classmethod
    def normalize_optional_locale(cls, value: str | None) -> str | None:
        return normalize_locale_tag(value) if value else None


class IngredientCandidate(BaseModel):
    id: UUID
    name: str


class IngredientResolution(BaseModel):
    query: str
    normalized_query: str
    matching: Literal["exact_normalized_v1"]
    status: Literal["resolved", "ambiguous", "unresolved"]
    ingredient: IngredientCandidate | None = None
    candidates: list[IngredientCandidate]


class SourceCitation(BaseModel):
    id: UUID
    publisher: str
    title: str
    canonical_url: str
    source_type: str
    license_name: str
    license_url: str | None
    attribution_text: str
    source_version: str | None
    checksum_sha256: str | None
    retrieved_at: datetime | None


class IngredientAliasRead(BaseModel):
    alias: str
    locale: str
    alias_type: str
    source_locator: str


class IngredientEvidenceRead(BaseModel):
    id: UUID
    evidence_kind: str
    summary: str
    scope: str | None
    locator: str
    excerpt: str | None
    source: SourceCitation


class IngredientDetailRead(BaseModel):
    id: UUID
    name: str
    name_kind: str
    dataset_version: str
    source_locator: str
    source: SourceCitation
    aliases: list[IngredientAliasRead]
    evidence: list[IngredientEvidenceRead]


class AdminAuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_user_id: UUID | None
    action: str
    object_type: str
    object_id: str
    request_id: str | None
    details: dict[str, object]
    created_at: datetime
