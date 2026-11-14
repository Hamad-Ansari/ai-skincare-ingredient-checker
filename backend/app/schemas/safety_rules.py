"""Admin schemas for deterministic rule versions and reviewed evidence mappings."""

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

RuleKey = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True,
        to_lower=True,
        min_length=2,
        max_length=100,
        pattern=r"^[a-z][a-z0-9._-]+$",
    ),
]
RuleVersionText = Annotated[
    str,
    StringConstraints(
        strip_whitespace=True, min_length=5, max_length=32, pattern=r"^\d+\.\d+\.\d+$"
    ),
]
RuleTitle = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
RuleMessage = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)
]
ReviewNote = Annotated[
    str, StringConstraints(strip_whitespace=True, min_length=10, max_length=2000)
]


class IngredientPresenceCondition(BaseModel):
    """A deliberately small, non-executable condition over resolved canonical IDs."""

    model_config = ConfigDict(extra="forbid")

    ingredient_ids: list[UUID] = Field(min_length=1, max_length=100)

    @field_validator("ingredient_ids")
    @classmethod
    def sort_unique_ingredient_ids(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("Condition ingredient IDs must be unique")
        return sorted(value, key=str)


class RuleVersionCreate(BaseModel):
    """Create a draft rule version and pending links to existing reviewed evidence."""

    model_config = ConfigDict(extra="forbid")

    rule_key: RuleKey
    version: RuleVersionText
    condition: IngredientPresenceCondition
    title: RuleTitle
    message: RuleMessage
    severity: Literal["informational", "notice", "caution"]
    evidence_record_ids: list[UUID] = Field(min_length=1, max_length=200)

    @field_validator("evidence_record_ids")
    @classmethod
    def unique_evidence_records(cls, value: list[UUID]) -> list[UUID]:
        if len(value) != len(set(value)):
            raise ValueError("Evidence record IDs must be unique")
        return value

    @model_validator(mode="after")
    def require_a_mapping_candidate_for_each_target(self) -> "RuleVersionCreate":
        if not self.evidence_record_ids:
            raise ValueError("At least one evidence record must be mapped")
        return self


class ReviewDecision(BaseModel):
    """Explicit approve/reject decision with a recorded editorial rationale."""

    model_config = ConfigDict(extra="forbid")

    decision: Literal["approved", "rejected"]
    note: ReviewNote


class RuleEvidenceMappingRead(BaseModel):
    """Admin view of one map plus the current rights-filtered evidence provenance."""

    id: UUID
    evidence_record_id: UUID
    ingredient_id: UUID
    evidence_kind: str
    summary: str
    scope: str | None
    locator: str
    excerpt: str | None
    source_id: UUID
    source_title: str
    canonical_url: AnyHttpUrl
    source_rights_status: Literal["pending", "approved", "restricted", "rejected"]
    review_status: Literal["pending", "approved", "rejected"]
    review_note: str | None
    reviewed_by: UUID | None
    reviewed_at: datetime | None
    created_at: datetime

    @field_validator("canonical_url")
    @classmethod
    def source_url_has_no_credentials_or_tracking(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        parts = urlsplit(str(value))
        if parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("Citation URLs must not contain credentials, queries, or fragments")
        return value


class RuleVersionRead(BaseModel):
    """Rule version lifecycle and its reviewed evidence mappings."""

    id: UUID
    rule_key: str
    version: str
    rule_type: Literal["ingredient_presence"]
    condition: IngredientPresenceCondition
    title: str
    message: str
    severity: Literal["informational", "notice", "caution"]
    status: Literal["draft", "approved", "active", "retired", "rejected"]
    created_by: UUID | None
    created_at: datetime
    reviewed_by: UUID | None
    review_note: str | None
    reviewed_at: datetime | None
    activated_at: datetime | None
    retired_at: datetime | None
    evidence_mappings: list[RuleEvidenceMappingRead]


class EvidenceIndexRead(BaseModel):
    """Metadata-only result for an explicit admin indexing action."""

    evidence_record_id: UUID
    ingredient_id: UUID
    collection: str
    indexed: Literal[True] = True
    indexed_text_kind: Literal["reviewed_summary"] = "reviewed_summary"
