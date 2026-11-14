"""Health endpoint response schemas."""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class HealthResponse(BaseModel):
    """Minimal health response; intentionally contains no internal dependency details."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["ok", "not_ready"]
