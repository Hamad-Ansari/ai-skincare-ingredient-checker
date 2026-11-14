"""Import all ORM models so SQLAlchemy metadata and Alembic see the full schema."""

from backend.app.models.accounts import (
    AiProviderConsent,
    AuthSession,
    OneTimeToken,
    User,
    UserDeclaredIngredient,
    UserProfile,
)
from backend.app.models.ingredient_catalog import (
    AdminAuditEvent,
    EvidenceRecord,
    EvidenceSource,
    Ingredient,
    IngredientAlias,
    IngredientImportBatch,
    IngredientImportRow,
)
from backend.app.models.safety_rules import (
    AnalysisFinding,
    AnalysisFindingEvidence,
    AnalysisIngredient,
    RuleEvidenceMapping,
    RuleVersion,
    ScanAnalysis,
)
from backend.app.models.scans import Scan, ScanIngredient

__all__ = [
    "AdminAuditEvent",
    "EvidenceRecord",
    "EvidenceSource",
    "Ingredient",
    "IngredientAlias",
    "IngredientImportBatch",
    "IngredientImportRow",
    "AiProviderConsent",
    "AuthSession",
    "OneTimeToken",
    "Scan",
    "ScanIngredient",
    "RuleVersion",
    "RuleEvidenceMapping",
    "ScanAnalysis",
    "AnalysisIngredient",
    "AnalysisFinding",
    "AnalysisFindingEvidence",
    "User",
    "UserDeclaredIngredient",
    "UserProfile",
]
