"""Metadata-filtered retrieval scoped to the active rule's reviewed evidence maps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from backend.app.models.safety_rules import RuleEvidenceMapping
from backend.app.services.rag.embeddings import EmbeddingError, EmbeddingProvider
from backend.app.services.rag.qdrant_store import QdrantEvidenceStore, QdrantStoreError

RetrievalState = Literal["not_run", "not_configured", "empty", "retrieved", "unavailable"]


@dataclass(frozen=True)
class RetrievalResult:
    """RAG status and rank metadata; citation text is always loaded from SQL."""

    status: RetrievalState
    rank_by_mapping_id: dict[UUID, int]


def retrieve_rule_evidence(
    *,
    store: QdrantEvidenceStore | None,
    embedder: EmbeddingProvider | None,
    query: str,
    ingredient_id: UUID,
    approved_mappings: list[RuleEvidenceMapping],
    top_k: int,
) -> RetrievalResult:
    """Retrieve only approved evidence IDs already mapped to this exact ingredient/rule."""
    if store is None or embedder is None:
        return RetrievalResult(status="not_configured", rank_by_mapping_id={})
    if not approved_mappings:
        return RetrievalResult(status="empty", rank_by_mapping_id={})

    mapping_by_evidence = {item.evidence_record_id: item for item in approved_mappings}
    try:
        vector = embedder.embed(query)
        hits = store.search_approved_evidence(
            vector=vector,
            ingredient_id=ingredient_id,
            allowed_evidence_ids=set(mapping_by_evidence),
            limit=top_k,
        )
    except (EmbeddingError, QdrantStoreError, ValueError):
        return RetrievalResult(status="unavailable", rank_by_mapping_id={})

    ranks: dict[UUID, int] = {}
    for rank, hit in enumerate(hits, start=1):
        mapping = mapping_by_evidence.get(hit.evidence_record_id)
        if mapping is not None:
            ranks[mapping.id] = rank
    return RetrievalResult(
        status="retrieved" if ranks else "empty",
        rank_by_mapping_id=ranks,
    )
