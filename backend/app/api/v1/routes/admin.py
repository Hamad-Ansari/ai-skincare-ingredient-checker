"""Role-restricted source registry and ingredient import review workflow."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from logging import getLogger
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from backend.app.api.dependencies import AdminUser
from backend.app.database.dependencies import get_db_session
from backend.app.models.ingredient_catalog import (
    AdminAuditEvent,
    EvidenceRecord,
    EvidenceSource,
    Ingredient,
    IngredientAlias,
    IngredientImportBatch,
    IngredientImportRow,
)
from backend.app.models.safety_rules import RuleEvidenceMapping, RuleVersion
from backend.app.schemas.ingredients import (
    AdminAuditEventRead,
    EvidenceSourceCreate,
    EvidenceSourceRead,
    EvidenceSourceRightsReview,
    IngredientEvidenceInput,
    IngredientImportBatchRead,
    IngredientImportBatchReject,
    IngredientImportBatchSummary,
    IngredientImportCreate,
    IngredientImportRecord,
    IngredientImportRowRead,
    IngredientImportRowReview,
)
from backend.app.services.ingredients.normalization import normalize_ingredient_name
from backend.app.services.rag.runtime import get_rag_services
from backend.app.services.safety_rules.engine import InvalidRuleCondition, parse_condition

logger = getLogger(__name__)
router = APIRouter(prefix="/admin", tags=["admin"])
DbSession = Annotated[Session, Depends(get_db_session)]


def _audit(
    db: Session,
    request: Request,
    actor_id: UUID,
    action: str,
    object_type: str,
    object_id: UUID,
    details: dict[str, object],
) -> None:
    """Queue an allowlisted audit event in the same transaction as the change."""
    db.add(
        AdminAuditEvent(
            actor_user_id=actor_id,
            action=action,
            object_type=object_type,
            object_id=str(object_id),
            request_id=getattr(request.state, "request_id", None),
            details=details,
        )
    )


def _retire_rules_affected_by_source(
    db: Session,
    request: Request,
    admin_id: UUID,
    source_id: UUID,
) -> None:
    """Retire dependent rules when rights are withdrawn; reapproval cannot reactivate them."""
    evidence_ids = set(
        db.scalars(select(EvidenceRecord.id).where(EvidenceRecord.source_id == source_id)).all()
    )
    evidence_rule_ids: set[UUID] = set()
    if evidence_ids:
        evidence_rule_ids = set(
            db.scalars(
                select(RuleEvidenceMapping.rule_version_id).where(
                    RuleEvidenceMapping.evidence_record_id.in_(evidence_ids)
                )
            ).all()
        )
    ingredient_ids = set(
        db.scalars(select(Ingredient.id).where(Ingredient.source_id == source_id)).all()
    )
    if not evidence_rule_ids and not ingredient_ids:
        return

    now = datetime.now(UTC)
    active_rules = db.scalars(
        select(RuleVersion).where(RuleVersion.status == "active").with_for_update()
    ).all()
    for rule in active_rules:
        affected = rule.id in evidence_rule_ids
        if not affected and ingredient_ids:
            try:
                condition = parse_condition(rule.condition)
                affected = bool(ingredient_ids.intersection(condition.ingredient_ids))
            except InvalidRuleCondition:
                affected = False
        if affected:
            rule.status = "retired"
            rule.retired_at = now
            rule.updated_at = now
            _audit(
                db,
                request,
                admin_id,
                "rule_version_retired_source_rights",
                "rule_version",
                rule.id,
                {"rule_key": rule.rule_key, "version": rule.version, "source_id": str(source_id)},
            )


def _source_or_404(db: Session, source_id: UUID) -> EvidenceSource:
    source = db.get(EvidenceSource, source_id)
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "source_not_found", "message": "Source not found."},
        )
    return source


def _batch_or_404(db: Session, batch_id: UUID) -> IngredientImportBatch:
    batch = db.get(IngredientImportBatch, batch_id)
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "import_not_found", "message": "Ingredient import not found."},
        )
    return batch


def _batch_read(db: Session, batch: IngredientImportBatch) -> IngredientImportBatchRead:
    summary = IngredientImportBatchSummary.model_validate(batch)
    rows = db.scalars(
        select(IngredientImportRow)
        .where(IngredientImportRow.batch_id == batch.id)
        .order_by(IngredientImportRow.row_number)
    ).all()
    return IngredientImportBatchRead(
        **summary.model_dump(),
        rows=[IngredientImportRowRead.model_validate(row) for row in rows],
    )


def _contains_excerpts(records: list[IngredientImportRecord]) -> bool:
    return any(item.excerpt is not None for record in records for item in record.evidence)


@router.post(
    "/sources",
    response_model=EvidenceSourceRead,
    status_code=status.HTTP_201_CREATED,
)
def register_source(
    payload: EvidenceSourceCreate,
    request: Request,
    admin: AdminUser,
    db: DbSession,
) -> EvidenceSource:
    """Record provenance and license metadata without granting reuse rights."""
    canonical_url = str(payload.canonical_url)
    if db.scalar(select(EvidenceSource.id).where(EvidenceSource.canonical_url == canonical_url)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "source_exists", "message": "That source URL is already registered."},
        )

    source = EvidenceSource(
        publisher=payload.publisher,
        title=payload.title,
        canonical_url=canonical_url,
        source_type=payload.source_type,
        license_name=payload.license_name,
        license_url=str(payload.license_url) if payload.license_url else None,
        attribution_text=payload.attribution_text,
        source_version=payload.source_version,
        checksum_sha256=payload.checksum_sha256,
        retrieved_at=payload.retrieved_at,
        rights_status="pending",
        can_reproduce_excerpt=False,
        created_by=admin.id,
    )
    db.add(source)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "source_exists", "message": "That source URL is already registered."},
        ) from exc

    _audit(
        db,
        request,
        admin.id,
        "source_registered",
        "evidence_source",
        source.id,
        {"rights_status": "pending", "source_type": source.source_type},
    )
    db.commit()
    db.refresh(source)
    return source


@router.get("/sources", response_model=list[EvidenceSourceRead])
def list_sources(
    _admin: AdminUser,
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[EvidenceSource]:
    """List source/license records for editorial review."""
    return list(
        db.scalars(
            select(EvidenceSource)
            .order_by(EvidenceSource.created_at.desc(), EvidenceSource.id)
            .limit(limit)
            .offset(offset)
        ).all()
    )


@router.post("/sources/{source_id}/rights-review", response_model=EvidenceSourceRead)
def review_source_rights(
    source_id: UUID,
    payload: EvidenceSourceRightsReview,
    request: Request,
    admin: AdminUser,
    db: DbSession,
) -> EvidenceSource:
    """Record an explicit rights decision; excerpt reuse is separately opt-in."""
    source = db.scalar(
        select(EvidenceSource).where(EvidenceSource.id == source_id).with_for_update()
    )
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "source_not_found", "message": "Source not found."},
        )

    prior_rights_status = source.rights_status
    prior_excerpt_permission = source.can_reproduce_excerpt
    source.rights_status = payload.decision
    source.can_reproduce_excerpt = (
        payload.can_reproduce_excerpt if payload.decision == "approved" else False
    )
    if payload.decision != "approved":
        _retire_rules_affected_by_source(db, request, admin.id, source.id)
    source.rights_review_note = payload.note
    source.rights_reviewed_at = datetime.now(UTC)
    source.rights_reviewed_by = admin.id
    _audit(
        db,
        request,
        admin.id,
        "source_rights_reviewed",
        "evidence_source",
        source.id,
        {
            "decision": source.rights_status,
            "can_reproduce_excerpt": source.can_reproduce_excerpt,
        },
    )
    db.commit()
    db.refresh(source)
    if (
        prior_rights_status != source.rights_status
        or prior_excerpt_permission != source.can_reproduce_excerpt
    ):
        try:
            store, _ = get_rag_services(request)
            if store is not None:
                store.delete_source(source.id)
        except Exception as exc:
            # SQL rights checks block retrieval even if the best-effort vector purge is offline.
            logger.warning(
                "Evidence index purge failed after source-rights change; "
                "source_id=%s error_type=%s",
                source.id,
                type(exc).__name__,
            )
    return source


@router.post(
    "/ingredient-imports",
    response_model=IngredientImportBatchRead,
    status_code=status.HTTP_201_CREATED,
)
def submit_ingredient_import(
    payload: IngredientImportCreate,
    request: Request,
    admin: AdminUser,
    db: DbSession,
) -> IngredientImportBatchRead:
    """Validate and store a source-specific batch in review; never activate on submission."""
    source = _source_or_404(db, payload.source_id)
    if source.rights_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "source_rights_not_approved",
                "message": "Source rights must be approved before importing its content.",
            },
        )
    if _contains_excerpts(payload.records) and not source.can_reproduce_excerpt:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail={
                "code": "source_excerpt_not_permitted",
                "message": "This source has not been approved for excerpt reproduction.",
            },
        )

    manifest_content = {
        "source_id": str(payload.source_id),
        "dataset_version": payload.dataset_version,
        "records": [record.model_dump(mode="json") for record in payload.records],
    }
    canonical_json = json.dumps(
        manifest_content, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    content_sha256 = hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()
    if db.scalar(
        select(IngredientImportBatch.id).where(
            IngredientImportBatch.source_id == source.id,
            IngredientImportBatch.content_sha256 == content_sha256,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "import_duplicate",
                "message": "This exact source batch was already submitted.",
            },
        )

    batch = IngredientImportBatch(
        source_id=source.id,
        dataset_version=payload.dataset_version,
        content_sha256=content_sha256,
        status="in_review",
        row_count=len(payload.records),
        submitted_by=admin.id,
    )
    db.add(batch)
    try:
        db.flush()
        for row_number, record in enumerate(payload.records, start=1):
            db.add(
                IngredientImportRow(
                    batch_id=batch.id,
                    row_number=row_number,
                    normalized_name=normalize_ingredient_name(record.name),
                    payload=record.model_dump(mode="json"),
                    decision="pending",
                )
            )
        _audit(
            db,
            request,
            admin.id,
            "ingredient_import_submitted",
            "ingredient_import_batch",
            batch.id,
            {"row_count": len(payload.records), "dataset_version": payload.dataset_version},
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "import_duplicate",
                "message": "This source batch conflicts with an existing import.",
            },
        ) from exc
    db.refresh(batch)
    return _batch_read(db, batch)


@router.get("/ingredient-imports", response_model=list[IngredientImportBatchSummary])
def list_ingredient_imports(
    _admin: AdminUser,
    db: DbSession,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[IngredientImportBatch]:
    """List import batches and review state without activating content."""
    return list(
        db.scalars(
            select(IngredientImportBatch)
            .order_by(IngredientImportBatch.created_at.desc(), IngredientImportBatch.id)
            .limit(limit)
            .offset(offset)
        ).all()
    )


@router.get("/ingredient-imports/{batch_id}", response_model=IngredientImportBatchRead)
def get_ingredient_import(
    batch_id: UUID,
    _admin: AdminUser,
    db: DbSession,
) -> IngredientImportBatchRead:
    """Inspect all submitted rows and their review decisions."""
    return _batch_read(db, _batch_or_404(db, batch_id))


@router.post(
    "/ingredient-imports/{batch_id}/rows/{row_id}/review",
    response_model=IngredientImportRowRead,
)
def review_ingredient_import_row(
    batch_id: UUID,
    row_id: UUID,
    payload: IngredientImportRowReview,
    request: Request,
    admin: AdminUser,
    db: DbSession,
) -> IngredientImportRow:
    """Approve or reject one row with a recorded reviewer note."""
    batch = _batch_or_404(db, batch_id)
    row = db.scalar(
        select(IngredientImportRow)
        .where(IngredientImportRow.id == row_id, IngredientImportRow.batch_id == batch.id)
        .with_for_update()
    )
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "import_row_not_found", "message": "Ingredient import row not found."},
        )
    if batch.status != "in_review" or row.decision != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "import_row_already_reviewed",
                "message": "This row is no longer awaiting review.",
            },
        )

    row.decision = payload.decision
    row.review_note = payload.note
    row.reviewed_by = admin.id
    row.reviewed_at = datetime.now(UTC)
    _audit(
        db,
        request,
        admin.id,
        "ingredient_import_row_reviewed",
        "ingredient_import_row",
        row.id,
        {"decision": row.decision, "row_number": row.row_number},
    )
    db.commit()
    db.refresh(row)
    return row


@router.post("/ingredient-imports/{batch_id}/reject", response_model=IngredientImportBatchRead)
def reject_ingredient_import(
    batch_id: UUID,
    payload: IngredientImportBatchReject,
    request: Request,
    admin: AdminUser,
    db: DbSession,
) -> IngredientImportBatchRead:
    """Reject a complete batch and close all still-pending rows."""
    batch = db.scalar(
        select(IngredientImportBatch).where(IngredientImportBatch.id == batch_id).with_for_update()
    )
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "import_not_found", "message": "Ingredient import not found."},
        )
    if batch.status != "in_review":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "import_not_reviewable",
                "message": "This import is no longer awaiting review.",
            },
        )

    now = datetime.now(UTC)
    rows = db.scalars(
        select(IngredientImportRow).where(IngredientImportRow.batch_id == batch.id)
    ).all()
    for row in rows:
        row.decision = "rejected"
        row.review_note = payload.note
        row.reviewed_by = admin.id
        row.reviewed_at = now
    batch.status = "rejected"
    _audit(
        db,
        request,
        admin.id,
        "ingredient_import_rejected",
        "ingredient_import_batch",
        batch.id,
        {"row_count": len(rows)},
    )
    db.commit()
    db.refresh(batch)
    return _batch_read(db, batch)


@router.post("/ingredient-imports/{batch_id}/activate", response_model=IngredientImportBatchRead)
def activate_ingredient_import(
    batch_id: UUID,
    request: Request,
    admin: AdminUser,
    db: DbSession,
) -> IngredientImportBatchRead:
    """Activate only fully reviewed rows from a currently approved source."""
    batch = db.scalar(
        select(IngredientImportBatch).where(IngredientImportBatch.id == batch_id).with_for_update()
    )
    if batch is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "import_not_found", "message": "Ingredient import not found."},
        )
    if batch.status != "in_review":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "import_not_reviewable",
                "message": "This import is no longer awaiting review.",
            },
        )

    source = _source_or_404(db, batch.source_id)
    if source.rights_status != "approved":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "source_rights_not_approved",
                "message": "Source rights must be approved at activation time.",
            },
        )

    rows = db.scalars(
        select(IngredientImportRow)
        .where(IngredientImportRow.batch_id == batch.id)
        .order_by(IngredientImportRow.row_number)
    ).all()
    if any(row.decision == "pending" for row in rows):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "import_review_incomplete",
                "message": "Every row must be reviewed before activation.",
            },
        )
    approved_rows = [row for row in rows if row.decision == "approved"]
    if not approved_rows:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "import_has_no_approved_rows",
                "message": "At least one row must be approved.",
            },
        )

    records = [(row, IngredientImportRecord.model_validate(row.payload)) for row in approved_rows]
    if _contains_excerpts([record for _, record in records]) and not source.can_reproduce_excerpt:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "source_excerpt_not_permitted",
                "message": "Excerpt reuse approval was removed before activation.",
            },
        )

    names = [normalize_ingredient_name(record.name) for _, record in records]
    existing = set(
        db.scalars(
            select(Ingredient.normalized_name).where(Ingredient.normalized_name.in_(names))
        ).all()
    )
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "canonical_name_conflict",
                "message": "A preferred name already exists; submit a corrected reviewed import.",
            },
        )

    now = datetime.now(UTC)
    evidence_count = 0
    try:
        for row, record in records:
            ingredient = Ingredient(
                name=record.name,
                normalized_name=normalize_ingredient_name(record.name),
                name_kind=record.name_kind,
                status="active",
                source_id=source.id,
                source_locator=record.source_locator,
                dataset_version=batch.dataset_version,
            )
            db.add(ingredient)
            db.flush()

            for alias in record.aliases:
                db.add(
                    IngredientAlias(
                        ingredient_id=ingredient.id,
                        alias=alias.alias,
                        normalized_alias=normalize_ingredient_name(alias.alias),
                        locale=alias.locale,
                        alias_type=alias.alias_type,
                        status="active",
                        source_id=source.id,
                        source_locator=alias.source_locator or record.source_locator,
                    )
                )
            for evidence in record.evidence:
                _add_evidence_record(db, evidence, ingredient.id, source.id, admin.id, row, now)
                evidence_count += 1

        batch.status = "activated"
        batch.activated_by = admin.id
        batch.activated_at = now
        _audit(
            db,
            request,
            admin.id,
            "ingredient_import_activated",
            "ingredient_import_batch",
            batch.id,
            {
                "ingredient_count": len(records),
                "evidence_count": evidence_count,
                "dataset_version": batch.dataset_version,
            },
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "code": "catalog_conflict",
                "message": "The import conflicts with existing catalog data; "
                "no rows were activated.",
            },
        ) from exc

    db.refresh(batch)
    return _batch_read(db, batch)


def _add_evidence_record(
    db: Session,
    evidence: IngredientEvidenceInput,
    ingredient_id: UUID,
    source_id: UUID,
    reviewer_id: UUID,
    row: IngredientImportRow,
    now: datetime,
) -> None:
    db.add(
        EvidenceRecord(
            ingredient_id=ingredient_id,
            source_id=source_id,
            evidence_kind=evidence.evidence_kind,
            summary=evidence.summary,
            scope=evidence.scope,
            locator=evidence.locator,
            excerpt=evidence.excerpt,
            review_status="approved",
            review_note=row.review_note or "",
            reviewed_at=now,
            reviewed_by=reviewer_id,
        )
    )


@router.get("/audit-events", response_model=list[AdminAuditEventRead])
def list_admin_audit_events(
    _admin: AdminUser,
    db: DbSession,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> list[AdminAuditEvent]:
    """Read the minimal audit trail for editorial actions."""
    return list(
        db.scalars(
            select(AdminAuditEvent)
            .order_by(AdminAuditEvent.created_at.desc(), AdminAuditEvent.id)
            .limit(limit)
            .offset(offset)
        ).all()
    )
