"""Rights-aware indexing of reviewed evidence summaries into Qdrant."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from backend.app.models.ingredient_catalog import EvidenceRecord, EvidenceSource, Ingredient
from backend.app.services.rag.embeddings import EmbeddingError, EmbeddingProvider
from backend.app.services.rag.qdrant_store import QdrantEvidenceStore, QdrantStoreError


class EvidenceNotIndexable(ValueError):
    """An evidence record or one of its provenance sources is not currently approved."""


class EvidenceIndexError(RuntimeError):
    """Safe wrapper for embedding/Qdrant failures during indexing."""


@dataclass(frozen=True)
class IndexableEvidence:
    """Current SQL-backed evidence/provenance eligible for the public evidence index."""

    record: EvidenceRecord
    ingredient: Ingredient
    source: EvidenceSource


def get_indexable_evidence(db: Session, evidence_record_id: UUID) -> IndexableEvidence:
    """Return only currently approved evidence and active canonical ingredient provenance."""
    evidence_source = aliased(EvidenceSource, name="evidence_source")
    ingredient_source = aliased(EvidenceSource, name="ingredient_source")
    row = db.execute(
        select(EvidenceRecord, Ingredient, evidence_source)
        .join(Ingredient, EvidenceRecord.ingredient_id == Ingredient.id)
        .join(evidence_source, EvidenceRecord.source_id == evidence_source.id)
        .join(ingredient_source, Ingredient.source_id == ingredient_source.id)
        .where(
            EvidenceRecord.id == evidence_record_id,
            EvidenceRecord.review_status == "approved",
            evidence_source.rights_status == "approved",
            Ingredient.status == "active",
            ingredient_source.rights_status == "approved",
        )
    ).one_or_none()
    if row is None:
        raise EvidenceNotIndexable("Evidence and ingredient sources must be currently approved")
    record, ingredient, source = row
    return IndexableEvidence(record=record, ingredient=ingredient, source=source)


def index_approved_evidence(
    db: Session,
    evidence_record_id: UUID,
    store: QdrantEvidenceStore,
    embedder: EmbeddingProvider,
) -> IndexableEvidence:
    """Embed a reviewed summary only; never index source excerpts or private scan content."""
    eligible = get_indexable_evidence(db, evidence_record_id)
    summary = eligible.record.summary.strip()
    if not summary or len(summary) > 16_000:
        raise EvidenceNotIndexable("Reviewed evidence summary is empty or too long to index")
    try:
        vector = embedder.embed(summary)
        store.upsert_approved_evidence(
            evidence_record_id=eligible.record.id,
            ingredient_id=eligible.ingredient.id,
            source_id=eligible.source.id,
            vector=vector,
        )
    except (EmbeddingError, QdrantStoreError, ValueError) as exc:
        raise EvidenceIndexError("The approved evidence could not be indexed") from exc

    try:
        current = get_indexable_evidence(db, evidence_record_id)
    except EvidenceNotIndexable as exc:
        try:
            store.delete_source(eligible.source.id)
        except QdrantStoreError:
            pass
        raise EvidenceNotIndexable("Source rights changed during evidence indexing") from exc
    return current
