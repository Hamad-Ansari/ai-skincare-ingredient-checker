"""Small deterministic rule executor; it never parses or evaluates rule text/code."""

from uuid import UUID

from pydantic import ValidationError

from backend.app.schemas.safety_rules import IngredientPresenceCondition

RULE_ENGINE_VERSION = "deterministic-ingredient-rules-v1"
RESOLVER_VERSION = "exact_normalized_v1"


class InvalidRuleCondition(ValueError):
    """Stored rule data does not conform to the supported deterministic schema."""


def parse_condition(value: object) -> IngredientPresenceCondition:
    """Validate stored JSON before execution; unsupported or malformed rules fail closed."""
    try:
        return IngredientPresenceCondition.model_validate(value)
    except (ValidationError, TypeError, ValueError) as exc:
        raise InvalidRuleCondition("Stored rule condition is invalid") from exc


def rule_matches(condition: IngredientPresenceCondition, ingredient_id: UUID) -> bool:
    """Match a resolved canonical ingredient ID, never a fuzzy/raw scan name."""
    return ingredient_id in condition.ingredient_ids
