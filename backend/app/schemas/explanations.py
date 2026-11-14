"""On-demand explanation request/response schemas; generated text cannot alter findings."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StringConstraints

ExplanationProviderName = Literal["ollama", "openai", "groq"]
ExplanationStatus = Literal["generated", "fallback"]


class FindingExplanationRequest(BaseModel):
    """Select one configured provider; callers cannot supply prompts or citation data."""

    model_config = ConfigDict(extra="forbid")

    provider: ExplanationProviderName


class FindingExplanationRead(BaseModel):
    """Supplementary prose only; source links and rule facts remain server-owned."""

    finding_id: UUID
    provider: ExplanationProviderName
    status: ExplanationStatus
    explanation: Annotated[
        str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1200)
    ]
    notice: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=400)]
    disclaimer: str = Field(
        default=(
            "Educational information only; not diagnosis or medical advice, "
            "and not a guarantee of safety."
        ),
        max_length=200,
    )
