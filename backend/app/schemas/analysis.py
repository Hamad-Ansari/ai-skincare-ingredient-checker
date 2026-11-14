"""Private scan-analysis schemas with source citations validated by the API."""

from datetime import datetime
from typing import Annotated, Literal
from urllib.parse import urlsplit
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, Field, StringConstraints, field_validator

from backend.app.schemas.ingredients import IngredientResolution

AnalysisStatus = Literal["completed", "no_active_rules", "needs_review", "stale"]
RetrievalStatus = Literal["not_run", "not_configured", "empty", "retrieved", "unavailable"]


class AnalysisRuleVersionRead(BaseModel):
    id: UUID
    rule_key: str
    version: str


class AnalysisIngredientRead(BaseModel):
    """The exact resolver result for one explicitly confirmed scan item."""

    scan_ingredient_id: UUID
    position: int = Field(ge=0)
    input_text: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    normalized_text: Annotated[str, StringConstraints(min_length=1, max_length=300)]
    resolution: IngredientResolution


class AnalysisSourceRead(BaseModel):
    """Server-owned source metadata; never accepted from an analysis request/model."""

    id: UUID
    publisher: str
    title: str
    canonical_url: AnyHttpUrl
    source_type: str
    license_name: str
    license_url: AnyHttpUrl | None
    attribution_text: str
    source_version: str | None
    checksum_sha256: str | None
    retrieved_at: datetime | None

    @field_validator("canonical_url", "license_url")
    @classmethod
    def source_url_has_no_credentials_or_tracking(
        cls, value: AnyHttpUrl | None
    ) -> AnyHttpUrl | None:
        if value is None:
            return None
        parts = urlsplit(str(value))
        if parts.username or parts.password or parts.query or parts.fragment:
            raise ValueError("Citation URLs must not contain credentials, queries, or fragments")
        return value


class AnalysisCitationRead(BaseModel):
    """Current approved evidence record plus a citation resolved from the database."""

    evidence_record_id: UUID
    evidence_kind: str
    summary: Annotated[str, StringConstraints(min_length=1, max_length=4000)]
    scope: str | None
    locator: Annotated[str, StringConstraints(min_length=1, max_length=1024)]
    excerpt: Annotated[str | None, StringConstraints(min_length=1, max_length=500)] = None
    source: AnalysisSourceRead
    retrieval_rank: int | None = Field(default=None, ge=1)


class AnalysisFindingRead(BaseModel):
    """A versioned rule match with one or more server-validated source citations."""

    id: UUID
    rule_key: str
    rule_version: str
    title: str
    message: str
    severity: Literal["informational", "notice", "caution"]
    ingredient_id: UUID
    ingredient_name: str
    citations: list[AnalysisCitationRead] = Field(min_length=1)


class ScanAnalysisRead(BaseModel):
    """Analysis results for the owning user; empty findings are never a safety verdict."""

    id: UUID
    scan_id: UUID
    status: AnalysisStatus
    rule_engine_version: str
    resolver_version: str
    created_at: datetime
    rule_versions: list[AnalysisRuleVersionRead]
    retrieval_status: RetrievalStatus
    ingredients: list[AnalysisIngredientRead]
    findings: list[AnalysisFindingRead]
    unresolved_count: int = Field(ge=0)
    notice: str
    disclaimer: str
