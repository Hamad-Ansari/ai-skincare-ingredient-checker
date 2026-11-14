"""Qdrant storage/search for public, reviewed evidence only."""

from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from uuid import UUID

from qdrant_client import QdrantClient, models

from backend.app.services.rag.embeddings import validate_vector


class QdrantStoreError(RuntimeError):
    """A Qdrant failure safe to report without exposing payloads or connection secrets."""


@dataclass(frozen=True)
class QdrantHit:
    """A candidate record identifier and similarity score; never a trusted citation."""

    evidence_record_id: UUID
    score: float


class QdrantEvidenceStore:
    """Metadata-filtered Qdrant access; SQL remains authoritative for evidence/citations."""

    def __init__(self, client: QdrantClient, collection_name: str) -> None:
        self.client = client
        self.collection_name = collection_name

    def ensure_collection(self, vector_size: int) -> None:
        """Create a collection once or fail closed on vector-dimension drift."""
        if not 1 <= vector_size <= 8192:
            raise ValueError("Qdrant vector size must be between 1 and 8192")
        try:
            exists = self.client.collection_exists(self.collection_name)
            if not exists:
                try:
                    self.client.create_collection(
                        collection_name=self.collection_name,
                        vectors_config=models.VectorParams(
                            size=vector_size,
                            distance=models.Distance.COSINE,
                        ),
                    )
                except Exception:
                    # A concurrent process may have created the collection after the first check.
                    if not self.client.collection_exists(self.collection_name):
                        raise
            info = self.client.get_collection(self.collection_name)
        except Exception as exc:
            raise QdrantStoreError("Qdrant collection is unavailable") from exc

        configured = info.config.params.vectors
        if not isinstance(configured, models.VectorParams) or configured.size != vector_size:
            raise QdrantStoreError("Qdrant collection vector dimensions do not match the embedder")

    def upsert_approved_evidence(
        self,
        *,
        evidence_record_id: UUID,
        ingredient_id: UUID,
        source_id: UUID,
        vector: list[float],
    ) -> None:
        """Store an embedding and minimal provenance metadata, never a citation URL or user data."""
        checked_vector = validate_vector(vector)
        self.ensure_collection(len(checked_vector))
        payload = {
            "evidence_record_id": str(evidence_record_id),
            "ingredient_id": str(ingredient_id),
            "source_id": str(source_id),
            "review_status": "approved",
            "source_rights_status": "approved",
        }
        try:
            self.client.upsert(
                collection_name=self.collection_name,
                points=[
                    models.PointStruct(
                        id=str(evidence_record_id),
                        vector=checked_vector,
                        payload=payload,
                    )
                ],
                wait=True,
            )
        except Exception as exc:
            raise QdrantStoreError("Evidence could not be added to Qdrant") from exc

    def search_approved_evidence(
        self,
        *,
        vector: list[float],
        ingredient_id: UUID,
        allowed_evidence_ids: set[UUID],
        limit: int,
    ) -> list[QdrantHit]:
        """Search only records allowed by the live SQL rule/evidence mapping."""
        if not allowed_evidence_ids:
            return []
        if not 1 <= limit <= 20:
            raise ValueError("Qdrant retrieval limit must be between 1 and 20")
        checked_vector = validate_vector(vector)

        try:
            if not self.client.collection_exists(self.collection_name):
                return []
            evidence_condition = models.FieldCondition(
                key="evidence_record_id",
                match=models.MatchAny(any=sorted(str(item) for item in allowed_evidence_ids)),
            )
            query_filter = models.Filter(
                must=[
                    models.FieldCondition(
                        key="review_status", match=models.MatchValue(value="approved")
                    ),
                    models.FieldCondition(
                        key="source_rights_status", match=models.MatchValue(value="approved")
                    ),
                    models.FieldCondition(
                        key="ingredient_id", match=models.MatchValue(value=str(ingredient_id))
                    ),
                    evidence_condition,
                ]
            )
            result = self.client.query_points(
                collection_name=self.collection_name,
                query=checked_vector,
                query_filter=query_filter,
                limit=limit,
                with_payload=True,
            )
        except Exception as exc:
            raise QdrantStoreError("Qdrant evidence retrieval is unavailable") from exc

        allowed = {str(item) for item in allowed_evidence_ids}
        hits: list[QdrantHit] = []
        for point in result.points:
            payload = point.payload or {}
            raw_id = payload.get("evidence_record_id")
            if (
                not isinstance(raw_id, str)
                or raw_id not in allowed
                or payload.get("ingredient_id") != str(ingredient_id)
                or payload.get("review_status") != "approved"
                or payload.get("source_rights_status") != "approved"
            ):
                continue
            try:
                evidence_id = UUID(raw_id)
                score = float(point.score)
            except (TypeError, ValueError):
                continue
            if isfinite(score):
                hits.append(QdrantHit(evidence_record_id=evidence_id, score=score))
        return hits

    def delete_source(self, source_id: UUID) -> None:
        """Best-effort purge of all indexed evidence from a source whose rights changed."""
        try:
            if not self.client.collection_exists(self.collection_name):
                return
            self.client.delete(
                collection_name=self.collection_name,
                points_selector=models.FilterSelector(
                    filter=models.Filter(
                        must=[
                            models.FieldCondition(
                                key="source_id", match=models.MatchValue(value=str(source_id))
                            )
                        ]
                    )
                ),
                wait=True,
            )
        except Exception as exc:
            raise QdrantStoreError("Evidence index source purge is unavailable") from exc

    def close(self) -> None:
        """Close the configured Qdrant client."""
        self.client.close()
