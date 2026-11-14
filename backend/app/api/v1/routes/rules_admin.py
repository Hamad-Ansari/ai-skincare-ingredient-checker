"""Admin-only versioned deterministic rules, evidence mappings, and safe index operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, aliased

from backend.app.api.dependencies import AdminUser
from backend.app.database.dependencies import get_db_session
from backend.app.models.accounts import User
from backend.app.models.ingredient_catalog import (
    AdminAuditEvent,
    EvidenceRecord,
    EvidenceSource,
    Ingredient,
)
from backend.app.models.safety_rules import RuleEvidenceMapping, RuleVersion
from backend.app.schemas.safety_rules import (
    EvidenceIndexRead,
    IngredientPresenceCondition,
    ReviewDecision,
    RuleEvidenceMappingRead,
    RuleVersionCreate,
    RuleVersionRead,
)
from backend.app.services.evidence.indexing import (
    EvidenceIndexError,
    EvidenceNotIndexable,
    get_indexable_evidence,
    index_approved_evidence,
)
from backend.app.services.rag.qdrant_store import QdrantStoreError
from backend.app.services.rag.runtime import RagRuntimeUnavailable, get_rag_services
from backend.app.services.safety_rules.engine import InvalidRuleCondition, parse_condition

router = APIRouter(prefix="/admin", tags=["admin"])
DbSession = Annotated[Session, Depends(get_db_session)]
RuleStatusFilter = Literal["draft", "approved", "active", "retired", "rejected"]


def _http_error(code: str, message: str, status_code: int) -> HTTPException:
    return HTTPException(status_code=status_code, detail={"code": code, "message": message})


def _audit(
    db: Session,
    request: Request,
    admin: User,
    action: str,
    object_type: str,
    object_id: UUID,
    details: dict[str, object],
) -> None:
    db.add(
        AdminAuditEvent(
            actor_user_id=admin.id,
            action=action,
            object_type=object_type,
            object_id=str(object_id),
            request_id=getattr(request.state, "request_id", None),
            details=details,
        )
    )


def _rule_or_404(db: Session, rule_version_id: UUID, *, lock: bool = False) -> RuleVersion:
    query = select(RuleVersion).where(RuleVersion.id == rule_version_id)
    if lock:
        query = query.with_for_update()
    rule = db.scalar(query)
    if rule is None:
        raise _http_error("rule_version_not_found", "Rule version not found.", 404)
    return rule


def _eligible_ingredient_ids(db: Session, ingredient_ids: set[UUID]) -> set[UUID]:
    if not ingredient_ids:
        return set()
    canonical_source = aliased(EvidenceSource)
    return set(
        db.scalars(
            select(Ingredient.id)
            .join(canonical_source, Ingredient.source_id == canonical_source.id)
            .where(
                Ingredient.id.in_(ingredient_ids),
                Ingredient.status == "active",
                canonical_source.rights_status == "approved",
            )
        ).all()
    )


def _eligible_evidence_targets(db: Session, evidence_ids: set[UUID]) -> dict[UUID, UUID]:
    if not evidence_ids:
        return {}
    evidence_source = aliased(EvidenceSource)
    ingredient_source = aliased(EvidenceSource)
    rows = db.execute(
        select(EvidenceRecord.id, EvidenceRecord.ingredient_id)
        .join(evidence_source, EvidenceRecord.source_id == evidence_source.id)
        .join(Ingredient, EvidenceRecord.ingredient_id == Ingredient.id)
        .join(ingredient_source, Ingredient.source_id == ingredient_source.id)
        .where(
            EvidenceRecord.id.in_(evidence_ids),
            EvidenceRecord.review_status == "approved",
            evidence_source.rights_status == "approved",
            Ingredient.status == "active",
            ingredient_source.rights_status == "approved",
        )
    ).all()
    return {evidence_id: ingredient_id for evidence_id, ingredient_id in rows}


def _validate_rule_evidence(
    db: Session,
    rule: RuleVersion,
    *,
    allow_pending: bool = False,
) -> tuple[IngredientPresenceCondition, list[RuleEvidenceMapping]]:
    """Re-check current catalog/source rights and require a reviewed source per target ID."""
    try:
        condition = parse_condition(rule.condition)
    except InvalidRuleCondition as exc:
        raise _http_error(
            "rule_condition_invalid", "The stored rule condition is invalid.", 409
        ) from exc

    targets = set(condition.ingredient_ids)
    if _eligible_ingredient_ids(db, targets) != targets:
        raise _http_error(
            "rule_target_not_approved",
            "Every target ingredient must remain active with currently approved source rights.",
            409,
        )

    mappings = list(
        db.scalars(
            select(RuleEvidenceMapping)
            .where(RuleEvidenceMapping.rule_version_id == rule.id)
            .order_by(RuleEvidenceMapping.created_at, RuleEvidenceMapping.id)
        ).all()
    )
    if not mappings or (
        not allow_pending and any(item.review_status == "pending" for item in mappings)
    ):
        raise _http_error(
            "rule_evidence_review_incomplete",
            "Every evidence mapping must be reviewed before rule approval or activation.",
            409,
        )

    approved_mappings = [item for item in mappings if item.review_status == "approved"]
    evidence_targets = _eligible_evidence_targets(
        db, {item.evidence_record_id for item in approved_mappings}
    )
    covered_targets = {
        evidence_targets[item.evidence_record_id]
        for item in approved_mappings
        if item.evidence_record_id in evidence_targets
    }
    if covered_targets != targets:
        raise _http_error(
            "rule_evidence_incomplete",
            "Each target ingredient needs one or more approved, currently rights-cleared "
            "evidence mappings.",
            409,
        )
    return condition, approved_mappings


def _mapping_reads(db: Session, rule: RuleVersion) -> list[RuleEvidenceMappingRead]:
    rows = db.execute(
        select(RuleEvidenceMapping, EvidenceRecord, EvidenceSource)
        .join(EvidenceRecord, RuleEvidenceMapping.evidence_record_id == EvidenceRecord.id)
        .join(EvidenceSource, EvidenceRecord.source_id == EvidenceSource.id)
        .where(RuleEvidenceMapping.rule_version_id == rule.id)
        .order_by(RuleEvidenceMapping.created_at, RuleEvidenceMapping.id)
    ).all()
    return [
        RuleEvidenceMappingRead(
            id=mapping.id,
            evidence_record_id=record.id,
            ingredient_id=record.ingredient_id,
            evidence_kind=record.evidence_kind,
            summary=record.summary,
            scope=record.scope,
            locator=record.locator,
            excerpt=(
                record.excerpt
                if source.rights_status == "approved" and source.can_reproduce_excerpt
                else None
            ),
            source_id=source.id,
            source_title=source.title,
            canonical_url=source.canonical_url,
            source_rights_status=source.rights_status,
            review_status=mapping.review_status,
            review_note=mapping.review_note,
            reviewed_by=mapping.reviewed_by,
            reviewed_at=mapping.reviewed_at,
            created_at=mapping.created_at,
        )
        for mapping, record, source in rows
    ]


def _rule_read(db: Session, rule: RuleVersion) -> RuleVersionRead:
    try:
        condition = parse_condition(rule.condition)
    except InvalidRuleCondition as exc:
        raise _http_error(
            "rule_condition_invalid", "The stored rule condition is invalid.", 409
        ) from exc
    return RuleVersionRead(
        id=rule.id,
        rule_key=rule.rule_key,
        version=rule.version,
        rule_type=rule.rule_type,
        condition=condition,
        title=rule.title,
        message=rule.message,
        severity=rule.severity,
        status=rule.status,
        created_by=rule.created_by,
        created_at=rule.created_at,
        reviewed_by=rule.reviewed_by,
        review_note=rule.review_note,
        reviewed_at=rule.reviewed_at,
        activated_at=rule.activated_at,
        retired_at=rule.retired_at,
        evidence_mappings=_mapping_reads(db, rule),
    )


@router.post(
    "/rule-versions",
    response_model=RuleVersionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_rule_version(
    payload: RuleVersionCreate,
    request: Request,
    admin: AdminUser,
    db: DbSession,
) -> RuleVersionRead:
    """Submit a deterministic rule draft; it is inert until mapping review and activation."""
    if db.scalar(
        select(RuleVersion.id).where(
            RuleVersion.rule_key == payload.rule_key,
            RuleVersion.version == payload.version,
        )
    ):
        raise _http_error("rule_version_exists", "That rule version already exists.", 409)

    targets = set(payload.condition.ingredient_ids)
    if _eligible_ingredient_ids(db, targets) != targets:
        raise _http_error(
            "rule_target_not_approved",
            "Rule targets must be active canonical ingredients with approved source rights.",
            409,
        )

    evidence_targets = _eligible_evidence_targets(db, set(payload.evidence_record_ids))
    if len(evidence_targets) != len(payload.evidence_record_ids):
        raise _http_error(
            "evidence_not_approved",
            "Every mapped evidence record and its source must currently be approved.",
            409,
        )
    if not set(evidence_targets.values()).issubset(targets):
        raise _http_error(
            "evidence_target_mismatch",
            "Evidence may be mapped only to an ingredient named in this rule condition.",
            422,
        )
    if set(evidence_targets.values()) != targets:
        raise _http_error(
            "rule_evidence_incomplete",
            "Provide at least one approved evidence record for every target ingredient.",
            422,
        )

    rule = RuleVersion(
        rule_key=payload.rule_key,
        version=payload.version,
        rule_type="ingredient_presence",
        condition=payload.condition.model_dump(mode="json"),
        title=payload.title,
        message=payload.message,
        severity=payload.severity,
        status="draft",
        created_by=admin.id,
    )
    db.add(rule)
    try:
        db.flush()
        for evidence_id in payload.evidence_record_ids:
            db.add(
                RuleEvidenceMapping(
                    rule_version_id=rule.id,
                    evidence_record_id=evidence_id,
                    review_status="pending",
                    created_by=admin.id,
                )
            )
        _audit(
            db,
            request,
            admin,
            "rule_version_created",
            "rule_version",
            rule.id,
            {
                "rule_key": rule.rule_key,
                "version": rule.version,
                "evidence_mapping_count": len(payload.evidence_record_ids),
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _http_error(
            "rule_version_conflict", "The rule version conflicts with an existing record.", 409
        ) from exc
    db.refresh(rule)
    return _rule_read(db, rule)


@router.get("/rule-versions", response_model=list[RuleVersionRead])
def list_rule_versions(
    _admin: AdminUser,
    db: DbSession,
    rule_status: Annotated[RuleStatusFilter | None, Query(alias="status")] = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[RuleVersionRead]:
    """List rule versions for admin review; production seed remains empty by default."""
    query = select(RuleVersion)
    if rule_status is not None:
        query = query.where(RuleVersion.status == rule_status)
    rules = db.scalars(
        query.order_by(RuleVersion.rule_key, RuleVersion.version).limit(limit).offset(offset)
    ).all()
    return [_rule_read(db, rule) for rule in rules]


@router.get("/rule-versions/{rule_version_id}", response_model=RuleVersionRead)
def get_rule_version(
    rule_version_id: UUID,
    _admin: AdminUser,
    db: DbSession,
) -> RuleVersionRead:
    """Inspect one rule version and its source-rights-aware evidence map state."""
    return _rule_read(db, _rule_or_404(db, rule_version_id))


@router.post(
    "/rule-versions/{rule_version_id}/evidence-mappings/{mapping_id}/review",
    response_model=RuleVersionRead,
)
def review_rule_evidence_mapping(
    rule_version_id: UUID,
    mapping_id: UUID,
    payload: ReviewDecision,
    request: Request,
    admin: AdminUser,
    db: DbSession,
) -> RuleVersionRead:
    """Record a separate decision for one mapping while its rule remains a draft."""
    rule = _rule_or_404(db, rule_version_id, lock=True)
    if rule.status != "draft":
        raise _http_error(
            "rule_version_not_reviewable", "Only draft rule mappings can be reviewed.", 409
        )
    mapping = db.scalar(
        select(RuleEvidenceMapping).where(
            RuleEvidenceMapping.id == mapping_id,
            RuleEvidenceMapping.rule_version_id == rule.id,
        )
    )
    if mapping is None:
        raise _http_error("rule_evidence_mapping_not_found", "Evidence mapping not found.", 404)
    if mapping.review_status != "pending":
        raise _http_error(
            "rule_evidence_mapping_already_reviewed",
            "This evidence mapping has already been reviewed.",
            409,
        )
    if payload.decision == "approved":
        try:
            eligible = get_indexable_evidence(db, mapping.evidence_record_id)
        except EvidenceNotIndexable as exc:
            raise _http_error(
                "evidence_not_approved",
                "The evidence record, ingredient, and sources must remain approved.",
                409,
            ) from exc
        condition = parse_condition(rule.condition)
        if eligible.ingredient.id not in condition.ingredient_ids:
            raise _http_error(
                "evidence_target_mismatch",
                "Evidence must support an ingredient named in this rule condition.",
                409,
            )
    mapping.review_status = payload.decision
    mapping.review_note = payload.note
    mapping.reviewed_by = admin.id
    mapping.reviewed_at = datetime.now(UTC)
    _audit(
        db,
        request,
        admin,
        "rule_evidence_mapping_reviewed",
        "rule_evidence_mapping",
        mapping.id,
        {"decision": payload.decision, "rule_version_id": str(rule.id)},
    )
    db.commit()
    db.refresh(rule)
    return _rule_read(db, rule)


@router.post("/rule-versions/{rule_version_id}/review", response_model=RuleVersionRead)
def review_rule_version(
    rule_version_id: UUID,
    payload: ReviewDecision,
    request: Request,
    admin: AdminUser,
    db: DbSession,
) -> RuleVersionRead:
    """Approve only a deterministic rule with fully reviewed, current source mappings."""
    rule = _rule_or_404(db, rule_version_id, lock=True)
    if rule.status != "draft":
        raise _http_error(
            "rule_version_not_reviewable", "Only a draft rule version can be reviewed.", 409
        )
    if payload.decision == "approved":
        _validate_rule_evidence(db, rule)
        rule.status = "approved"
    else:
        rule.status = "rejected"
    now = datetime.now(UTC)
    rule.reviewed_by = admin.id
    rule.review_note = payload.note
    rule.reviewed_at = now
    rule.updated_at = now
    _audit(
        db,
        request,
        admin,
        "rule_version_reviewed",
        "rule_version",
        rule.id,
        {"decision": payload.decision, "rule_key": rule.rule_key, "version": rule.version},
    )
    db.commit()
    db.refresh(rule)
    return _rule_read(db, rule)


@router.post("/rule-versions/{rule_version_id}/activate", response_model=RuleVersionRead)
def activate_rule_version(
    rule_version_id: UUID,
    request: Request,
    admin: AdminUser,
    db: DbSession,
) -> RuleVersionRead:
    """Activate a reviewed version after rechecking all evidence and source-rights gates."""
    rule = _rule_or_404(db, rule_version_id, lock=True)
    if rule.status != "approved":
        raise _http_error(
            "rule_version_not_approved", "Only an approved rule version can be activated.", 409
        )
    _validate_rule_evidence(db, rule)
    now = datetime.now(UTC)
    previous = list(
        db.scalars(
            select(RuleVersion)
            .where(RuleVersion.rule_key == rule.rule_key, RuleVersion.status == "active")
            .with_for_update()
        ).all()
    )
    for active in previous:
        active.status = "retired"
        active.retired_at = now
        active.updated_at = now
    db.flush()
    rule.status = "active"
    rule.activated_at = now
    rule.updated_at = now
    _audit(
        db,
        request,
        admin,
        "rule_version_activated",
        "rule_version",
        rule.id,
        {"rule_key": rule.rule_key, "version": rule.version},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise _http_error(
            "rule_activation_conflict",
            "Another version of this rule became active; refresh and retry.",
            409,
        ) from exc
    db.refresh(rule)
    return _rule_read(db, rule)


@router.post("/rule-versions/{rule_version_id}/retire", response_model=RuleVersionRead)
def retire_rule_version(
    rule_version_id: UUID,
    request: Request,
    admin: AdminUser,
    db: DbSession,
) -> RuleVersionRead:
    """Retire an active rule without deleting its reviewed version or audit history."""
    rule = _rule_or_404(db, rule_version_id, lock=True)
    if rule.status != "active":
        raise _http_error("rule_version_not_active", "Only an active rule can be retired.", 409)
    now = datetime.now(UTC)
    rule.status = "retired"
    rule.retired_at = now
    rule.updated_at = now
    _audit(
        db,
        request,
        admin,
        "rule_version_retired",
        "rule_version",
        rule.id,
        {"rule_key": rule.rule_key, "version": rule.version},
    )
    db.commit()
    db.refresh(rule)
    return _rule_read(db, rule)


@router.post(
    "/evidence/{evidence_record_id}/index",
    response_model=EvidenceIndexRead,
    status_code=status.HTTP_200_OK,
)
def index_evidence_record(
    evidence_record_id: UUID,
    request: Request,
    admin: AdminUser,
    db: DbSession,
) -> EvidenceIndexRead:
    """Explicitly index one currently approved reviewer summary, never excerpts or user data."""
    if db.get(EvidenceRecord, evidence_record_id) is None:
        raise _http_error("evidence_not_found", "Evidence record not found.", 404)
    try:
        store, embedder = get_rag_services(request)
    except RagRuntimeUnavailable as exc:
        raise _http_error(
            "rag_not_configured",
            "Qdrant and the configured embedding service are unavailable.",
            503,
        ) from exc
    if store is None or embedder is None:
        raise _http_error(
            "rag_not_configured",
            "Qdrant and the configured embedding service are unavailable.",
            503,
        )
    try:
        indexed = index_approved_evidence(db, evidence_record_id, store, embedder)
    except EvidenceNotIndexable as exc:
        raise _http_error(
            "evidence_not_approved", "Only current approved evidence can be indexed.", 409
        ) from exc
    except (EvidenceIndexError, QdrantStoreError) as exc:
        raise _http_error(
            "evidence_index_unavailable", "The evidence index could not be updated.", 503
        ) from exc
    _audit(
        db,
        request,
        admin,
        "evidence_indexed",
        "ingredient_evidence_record",
        evidence_record_id,
        {"ingredient_id": str(indexed.ingredient.id), "collection": store.collection_name},
    )
    db.commit()
    return EvidenceIndexRead(
        evidence_record_id=evidence_record_id,
        ingredient_id=indexed.ingredient.id,
        collection=store.collection_name,
    )
