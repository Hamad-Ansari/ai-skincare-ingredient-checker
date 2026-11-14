"""Exact resolver for active, source-approved ingredient names and aliases."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from backend.app.models.ingredient_catalog import EvidenceSource, Ingredient, IngredientAlias
from backend.app.schemas.ingredients import IngredientCandidate, IngredientResolution
from backend.app.services.ingredients.normalization import normalize_ingredient_name


def resolve_ingredient(
    db: Session,
    term: str,
    locale: str | None = None,
) -> IngredientResolution:
    """Resolve only exact normalized matches; ambiguity is returned, never guessed through."""
    normalized = normalize_ingredient_name(term)
    candidates: dict[UUID, IngredientCandidate] = {}

    canonical_source = aliased(EvidenceSource)
    canonical_rows = db.execute(
        select(Ingredient.id, Ingredient.name)
        .join(canonical_source, Ingredient.source_id == canonical_source.id)
        .where(
            Ingredient.normalized_name == normalized,
            Ingredient.status == "active",
            canonical_source.rights_status == "approved",
        )
    ).all()
    for ingredient_id, name in canonical_rows:
        candidates[ingredient_id] = IngredientCandidate(id=ingredient_id, name=name)

    ingredient_source = aliased(EvidenceSource)
    alias_source = aliased(EvidenceSource)
    alias_query = (
        select(Ingredient.id, Ingredient.name)
        .join(ingredient_source, Ingredient.source_id == ingredient_source.id)
        .join(IngredientAlias, IngredientAlias.ingredient_id == Ingredient.id)
        .join(alias_source, IngredientAlias.source_id == alias_source.id)
        .where(
            IngredientAlias.normalized_alias == normalized,
            IngredientAlias.status == "active",
            Ingredient.status == "active",
            ingredient_source.rights_status == "approved",
            alias_source.rights_status == "approved",
        )
    )
    if locale is not None:
        alias_query = alias_query.where(IngredientAlias.locale.in_([locale, "und"]))
    for ingredient_id, name in db.execute(alias_query).all():
        candidates[ingredient_id] = IngredientCandidate(id=ingredient_id, name=name)

    ordered = sorted(candidates.values(), key=lambda item: (item.name.casefold(), str(item.id)))
    if len(ordered) == 1:
        status = "resolved"
        ingredient = ordered[0]
    elif len(ordered) > 1:
        status = "ambiguous"
        ingredient = None
    else:
        status = "unresolved"
        ingredient = None

    return IngredientResolution(
        query=term,
        normalized_query=normalized,
        matching="exact_normalized_v1",
        status=status,
        ingredient=ingredient,
        candidates=ordered,
    )
