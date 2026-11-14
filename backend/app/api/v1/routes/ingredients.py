"""Public exact-match ingredient resolution and source-linked detail routes."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.database.dependencies import get_db_session
from backend.app.models.ingredient_catalog import (
    EvidenceRecord,
    EvidenceSource,
    Ingredient,
    IngredientAlias,
)
from backend.app.schemas.ingredients import (
    IngredientAliasRead,
    IngredientDetailRead,
    IngredientEvidenceRead,
    IngredientResolution,
    IngredientResolutionRequest,
    SourceCitation,
)
from backend.app.services.ingredients.catalog import resolve_ingredient

router = APIRouter(prefix="/ingredients", tags=["ingredients"])
DbSession = Annotated[Session, Depends(get_db_session)]


def _source_citation(source: EvidenceSource) -> SourceCitation:
    return SourceCitation(
        id=source.id,
        publisher=source.publisher,
        title=source.title,
        canonical_url=source.canonical_url,
        source_type=source.source_type,
        license_name=source.license_name,
        license_url=source.license_url,
        attribution_text=source.attribution_text,
        source_version=source.source_version,
        checksum_sha256=source.checksum_sha256,
        retrieved_at=source.retrieved_at,
    )


@router.post("/resolve", response_model=IngredientResolution)
def resolve_name(payload: IngredientResolutionRequest, db: DbSession) -> IngredientResolution:
    """Return exact candidates; fuzzy or ambiguous terms are never auto-resolved."""
    return resolve_ingredient(db, payload.term, payload.locale)


@router.get("/{ingredient_id}", response_model=IngredientDetailRead)
def get_ingredient(ingredient_id: UUID, db: DbSession) -> IngredientDetailRead:
    """Return an active ingredient only while its provenance source remains approved."""
    source = EvidenceSource
    ingredient = db.scalar(
        select(Ingredient)
        .join(source, Ingredient.source_id == source.id)
        .where(
            Ingredient.id == ingredient_id,
            Ingredient.status == "active",
            source.rights_status == "approved",
        )
    )
    if ingredient is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "ingredient_not_found", "message": "Ingredient not found."},
        )

    ingredient_source = db.get(EvidenceSource, ingredient.source_id)
    assert ingredient_source is not None
    alias_source = EvidenceSource
    aliases = db.scalars(
        select(IngredientAlias)
        .join(alias_source, IngredientAlias.source_id == alias_source.id)
        .where(
            IngredientAlias.ingredient_id == ingredient.id,
            IngredientAlias.status == "active",
            alias_source.rights_status == "approved",
        )
        .order_by(IngredientAlias.normalized_alias, IngredientAlias.locale)
    ).all()

    evidence_source = EvidenceSource
    evidence_rows = db.execute(
        select(EvidenceRecord, evidence_source)
        .join(evidence_source, EvidenceRecord.source_id == evidence_source.id)
        .where(
            EvidenceRecord.ingredient_id == ingredient.id,
            EvidenceRecord.review_status == "approved",
            evidence_source.rights_status == "approved",
        )
        .order_by(EvidenceRecord.created_at, EvidenceRecord.id)
    ).all()
    evidence = [
        IngredientEvidenceRead(
            id=record.id,
            evidence_kind=record.evidence_kind,
            summary=record.summary,
            scope=record.scope,
            locator=record.locator,
            excerpt=record.excerpt if record_source.can_reproduce_excerpt else None,
            source=_source_citation(record_source),
        )
        for record, record_source in evidence_rows
    ]

    return IngredientDetailRead(
        id=ingredient.id,
        name=ingredient.name,
        name_kind=ingredient.name_kind,
        dataset_version=ingredient.dataset_version,
        source_locator=ingredient.source_locator,
        source=_source_citation(ingredient_source),
        aliases=[
            IngredientAliasRead(
                alias=alias.alias,
                locale=alias.locale,
                alias_type=alias.alias_type,
                source_locator=alias.source_locator,
            )
            for alias in aliases
        ],
        evidence=evidence,
    )
