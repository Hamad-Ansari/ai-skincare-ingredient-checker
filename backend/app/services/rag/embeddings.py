"""Local Ollama embeddings behind a small injectable interface."""

from __future__ import annotations

import json
import math
from collections.abc import Sequence
from typing import Protocol
from urllib.error import URLError
from urllib.request import Request, urlopen


class EmbeddingError(RuntimeError):
    """A provider failure safe to report without exposing request text or credentials."""


class EmbeddingProvider(Protocol):
    """Minimal vectorizer contract used by indexing and retrieval."""

    def embed(self, text: str) -> list[float]:
        """Return one finite embedding vector for the supplied text."""
        ...


class OllamaEmbeddingProvider:
    """Call Ollama's local `/api/embed` endpoint using the configured embedding model."""

    def __init__(self, base_url: str, model: str, timeout_seconds: int = 30) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def embed(self, text: str) -> list[float]:
        """Create and validate one vector; no text is logged or sent to a chat model."""
        if not text.strip() or len(text) > 16_000:
            raise EmbeddingError("Embedding input is empty or exceeds the configured limit")

        request_body = json.dumps({"model": self.model, "input": text}).encode("utf-8")
        request = Request(
            f"{self.base_url}/api/embed",
            data=request_body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                response_bytes = response.read(1_048_577)
            if len(response_bytes) > 1_048_576:
                raise EmbeddingError("The embedding service response exceeds the configured limit")
            payload = json.loads(response_bytes)
        except (URLError, TimeoutError, OSError, ValueError) as exc:
            raise EmbeddingError("The configured embedding service is unavailable") from exc

        if not isinstance(payload, dict):
            raise EmbeddingError("The embedding service returned an invalid response")
        vectors = payload.get("embeddings")
        if not isinstance(vectors, list) or len(vectors) != 1:
            raise EmbeddingError("The embedding service returned an invalid vector count")
        vector = vectors[0]
        if not isinstance(vector, list):
            raise EmbeddingError("The embedding service returned an invalid vector")
        try:
            return validate_vector(vector)
        except ValueError as exc:
            raise EmbeddingError("The embedding service returned an invalid vector") from exc


def validate_vector(vector: Sequence[float]) -> list[float]:
    """Validate vectors before they cross the vector-store boundary."""
    if not vector or len(vector) > 8192:
        raise ValueError("Vector must contain between 1 and 8192 dimensions")
    converted: list[float] = []
    for value in vector:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValueError("Vector values must be finite numbers")
        try:
            numeric_value = float(value)
        except (OverflowError, ValueError) as exc:
            raise ValueError("Vector values must be finite numbers") from exc
        if not math.isfinite(numeric_value):
            raise ValueError("Vector values must be finite numbers")
        converted.append(numeric_value)
    return converted
