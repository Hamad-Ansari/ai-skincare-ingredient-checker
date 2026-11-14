"""Owner-scoped deterministic analysis with current evidence and citation validation."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from logging import getLogger
from uuid import UUID, uuid4

from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from backend.app.models.ingredient_catalog import EvidenceRecord, EvidenceSource, Ingredient
from backend.app.models.safety_rules import (
    AnalysisFinding,
    AnalysisFindingEvidence,
    AnalysisIngredient,
    RuleEvidenceMapping,
    RuleVersion,
    ScanAnalysis,
)
from backend.app.models.scans import Scan, ScanIngredient
from backend.app.schemas.analysis import (
    AnalysisCitationRead,
    AnalysisFindingRead,
    AnalysisIngredientRead,
    AnalysisRuleVersionRead,
    AnalysisSourceRead,
    ScanAnalysisRead,
)
from backend.app.schemas.ingredients import IngredientResolution
from backend.app.schemas.safety_rules import IngredientPresenceCondition
from backend.app.services.ingredients.catalog import resolve_ingredient
from backend.app.services.rag.embeddings import EmbeddingProvider
from backend.app.services.rag.qdrant_store import QdrantEvidenceStore
from backend.app.services.rag.retrieval import RetrievalState, retrieve_rule_evidence
from backend.app.services.safety_rules.engine import (
    RESOLVER_VERSION,
    RULE_ENGINE_VERSION,
    InvalidRuleCondition,
    parse_condition,
    rule_matches,
)

logger = getLogger(__name__)
SAFETY_DISCLAIMER = (
    "Educational information only; not diagnosis or medical advice, and not a guarantee of safety."
)


class ScanAnalysisInputError(ValueError):
    """The scan is not eligible for analysis because user confirmation is missing."""


@dataclass(frozen=True)
class EvidenceBinding:
    """Current source-approved evidence behind a reviewed rule mapping."""

    mapping: RuleEvidenceMapping
    record: EvidenceRecord
    source: EvidenceSource


@dataclass(frozen=True)
class LiveRule:
    """An active rule whose target ingredients and mapped evidence remain approved."""

    rule: RuleVersion
    condition: IngredientPresenceCondition
    evidence_by_ingredient: dict[UUID, list[EvidenceBinding]]


def _active_canonical_ids(db: Session, ingredient_ids: set[UUID]) -> set[UUID]:
    if not ingredient_ids:
        return set()
    source = aliased(EvidenceSource)
    return set(
        db.scalars(
            select(Ingredient.id)
            .join(source, Ingredient.source_id == source.id)
            .where(
                Ingredient.id.in_(ingredient_ids),
                Ingredient.status == "active",
                source.rights_status == "approved",
            )
        ).all()
    )


def _live_rule_evidence(
    db: Session,
    rule_version_id: UUID,
    ingredient_ids: set[UUID],
) -> dict[UUID, list[EvidenceBinding]]:
    if not ingredient_ids:
        return {}
    evidence_source = aliased(EvidenceSource, name="rule_evidence_source")
    ingredient_source = aliased(EvidenceSource, name="rule_ingredient_source")
    rows = db.execute(
        select(RuleEvidenceMapping, EvidenceRecord, evidence_source)
        .join(EvidenceRecord, RuleEvidenceMapping.evidence_record_id == EvidenceRecord.id)
        .join(evidence_source, EvidenceRecord.source_id == evidence_source.id)
        .join(Ingredient, EvidenceRecord.ingredient_id == Ingredient.id)
        .join(ingredient_source, Ingredient.source_id == ingredient_source.id)
        .where(
            RuleEvidenceMapping.rule_version_id == rule_version_id,
            RuleEvidenceMapping.review_status == "approved",
            EvidenceRecord.review_status == "approved",
            EvidenceRecord.ingredient_id.in_(ingredient_ids),
            evidence_source.rights_status == "approved",
            Ingredient.status == "active",
            ingredient_source.rights_status == "approved",
        )
        .order_by(RuleEvidenceMapping.created_at, RuleEvidenceMapping.id)
    ).all()
    grouped: dict[UUID, list[EvidenceBinding]] = {}
    for mapping, record, source in rows:
        grouped.setdefault(record.ingredient_id, []).append(
            EvidenceBinding(mapping=mapping, record=record, source=source)
        )
    return grouped


def load_live_rules(db: Session) -> list[LiveRule]:
    """Load only active versions with current rights-cleared evidence for every target."""
    versions = db.scalars(
        select(RuleVersion)
        .where(RuleVersion.status == "active")
        .order_by(RuleVersion.rule_key, RuleVersion.version, RuleVersion.id)
    ).all()
    live: list[LiveRule] = []
    for rule in versions:
        try:
            condition = parse_condition(rule.condition)
        except InvalidRuleCondition:
            logger.warning("Ignoring malformed active rule; rule_version_id=%s", rule.id)
            continue
        targets = set(condition.ingredient_ids)
        if _active_canonical_ids(db, targets) != targets:
            continue
        evidence_by_ingredient = _live_rule_evidence(db, rule.id, targets)
        if set(evidence_by_ingredient) != targets:
            continue
        live.append(
            LiveRule(
                rule=rule,
                condition=condition,
                evidence_by_ingredient=evidence_by_ingredient,
            )
        )
    return live


def _candidate_snapshot(resolution: IngredientResolution) -> list[dict[str, str]]:
    return [
        {"id": str(candidate.id), "name": candidate.name} for candidate in resolution.candidates
    ]


def _rule_snapshot(live_rules: list[LiveRule]) -> list[dict[str, str]]:
    snapshot: list[dict[str, str]] = []
    for item in live_rules:
        encoded = json.dumps(
            {
                "rule_type": item.rule.rule_type,
                "condition": item.rule.condition,
                "title": item.rule.title,
                "message": item.rule.message,
                "severity": item.rule.severity,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
        snapshot.append(
            {
                "id": str(item.rule.id),
                "rule_key": item.rule.rule_key,
                "version": item.rule.version,
                "config_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
            }
        )
    return snapshot


def _aggregate_retrieval_status(statuses: list[RetrievalState]) -> RetrievalState:
    if not statuses:
        return "not_run"
    if "retrieved" in statuses:
        return "retrieved"
    if "unavailable" in statuses:
        return "unavailable"
    if "not_configured" in statuses:
        return "not_configured"
    return "empty"


def run_scan_analysis(
    db: Session,
    scan: Scan,
    requested_by: UUID,
    store: QdrantEvidenceStore | None,
    embedder: EmbeddingProvider | None,
    top_k: int,
    rag_unavailable: bool = False,
) -> ScanAnalysis:
    """Resolve confirmed names exactly, run active deterministic rules, and persist citations."""
    if scan.status != "confirmed" or scan.confirmed_at is None:
        raise ScanAnalysisInputError("Scan must be explicitly confirmed before analysis")
    scan_items = list(
        db.scalars(
            select(ScanIngredient)
            .where(ScanIngredient.scan_id == scan.id)
            .order_by(ScanIngredient.position, ScanIngredient.id)
        ).all()
    )
    if not scan_items or any(not item.user_confirmed for item in scan_items):
        raise ScanAnalysisInputError("Every analysis input must be explicitly confirmed")

    live_rules = load_live_rules(db)
    resolved_rows: list[tuple[ScanIngredient, IngredientResolution]] = [
        (item, resolve_ingredient(db, item.text)) for item in scan_items
    ]
    unresolved = any(resolution.status != "resolved" for _, resolution in resolved_rows)
    if not live_rules:
        status_value = "no_active_rules"
    elif unresolved:
        status_value = "needs_review"
    else:
        status_value = "completed"

    analysis_id = uuid4()
    matching_rules: list[
        tuple[ScanIngredient, IngredientResolution, LiveRule, list[EvidenceBinding]]
    ] = []
    for scan_item, resolution in resolved_rows:
        if resolution.status != "resolved" or resolution.ingredient is None:
            continue
        canonical_id = resolution.ingredient.id
        for live_rule in live_rules:
            if rule_matches(live_rule.condition, canonical_id):
                matching_rules.append(
                    (
                        scan_item,
                        resolution,
                        live_rule,
                        live_rule.evidence_by_ingredient[canonical_id],
                    )
                )

    retrieval_results: list[RetrievalState] = []
    rank_by_finding: dict[UUID, dict[UUID, int]] = {}
    finding_by_key: dict[tuple[UUID, UUID], AnalysisFinding] = {}
    for scan_item, resolution, live_rule, evidence in matching_rules:
        assert resolution.ingredient is not None
        if rag_unavailable:
            retrieval_status: RetrievalState = "unavailable"
            ranks_for_finding: dict[UUID, int] = {}
        else:
            retrieval = retrieve_rule_evidence(
                store=store,
                embedder=embedder,
                query=f"{live_rule.rule.title} {resolution.ingredient.name}",
                ingredient_id=resolution.ingredient.id,
                approved_mappings=[item.mapping for item in evidence],
                top_k=top_k,
            )
            retrieval_status = retrieval.status
            ranks_for_finding = retrieval.rank_by_mapping_id
        retrieval_results.append(retrieval_status)
        finding_id = uuid4()
        finding = AnalysisFinding(
            id=finding_id,
            analysis_id=analysis_id,
            rule_version_id=live_rule.rule.id,
            scan_ingredient_id=scan_item.id,
            ingredient_id=resolution.ingredient.id,
            ingredient_name=resolution.ingredient.name,
            rule_key=live_rule.rule.rule_key,
            rule_version=live_rule.rule.version,
            title=live_rule.rule.title,
            message=live_rule.rule.message,
            severity=live_rule.rule.severity,
        )
        finding_by_key[(scan_item.id, live_rule.rule.id)] = finding
        rank_by_finding[finding_id] = ranks_for_finding

    rule_snapshot = _rule_snapshot(live_rules)
    analysis = ScanAnalysis(
        id=analysis_id,
        scan_id=scan.id,
        requested_by=requested_by,
        status=status_value,
        engine_version=RULE_ENGINE_VERSION,
        resolver_version=RESOLVER_VERSION,
        rule_snapshot=rule_snapshot,
        retrieval_status=_aggregate_retrieval_status(retrieval_results),
    )
    db.add(analysis)
    db.flush()
    for finding in finding_by_key.values():
        db.add(finding)

    for position, (scan_item, resolution) in enumerate(resolved_rows):
        db.add(
            AnalysisIngredient(
                id=uuid4(),
                analysis_id=analysis_id,
                scan_ingredient_id=scan_item.id,
                position=position,
                input_text=scan_item.text,
                normalized_text=resolution.normalized_query,
                resolution_status=resolution.status,
                ingredient_id=resolution.ingredient.id if resolution.ingredient else None,
                ingredient_name=resolution.ingredient.name if resolution.ingredient else None,
                candidate_snapshot=_candidate_snapshot(resolution),
                matching=resolution.matching,
            )
        )
    db.flush()

    for scan_item, _resolution, live_rule, evidence in matching_rules:
        finding = finding_by_key[(scan_item.id, live_rule.rule.id)]
        ranks = rank_by_finding.get(finding.id, {})
        for binding in evidence:
            db.add(
                AnalysisFindingEvidence(
                    id=uuid4(),
                    finding_id=finding.id,
                    rule_evidence_mapping_id=binding.mapping.id,
                    retrieval_rank=ranks.get(binding.mapping.id),
                )
            )

    db.flush()
    return analysis


def _current_citations(db: Session, finding: AnalysisFinding) -> list[AnalysisCitationRead]:
    evidence_source = aliased(EvidenceSource, name="current_evidence_source")
    ingredient_source = aliased(EvidenceSource, name="current_ingredient_source")
    rows = db.execute(
        select(AnalysisFindingEvidence, EvidenceRecord, evidence_source)
        .join(
            RuleEvidenceMapping,
            AnalysisFindingEvidence.rule_evidence_mapping_id == RuleEvidenceMapping.id,
        )
        .join(EvidenceRecord, RuleEvidenceMapping.evidence_record_id == EvidenceRecord.id)
        .join(evidence_source, EvidenceRecord.source_id == evidence_source.id)
        .join(Ingredient, Ingredient.id == finding.ingredient_id)
        .join(ingredient_source, Ingredient.source_id == ingredient_source.id)
        .where(
            AnalysisFindingEvidence.finding_id == finding.id,
            RuleEvidenceMapping.rule_version_id == finding.rule_version_id,
            RuleEvidenceMapping.review_status == "approved",
            EvidenceRecord.review_status == "approved",
            EvidenceRecord.ingredient_id == finding.ingredient_id,
            evidence_source.rights_status == "approved",
            Ingredient.status == "active",
            ingredient_source.rights_status == "approved",
        )
        .order_by(
            AnalysisFindingEvidence.retrieval_rank.is_(None),
            AnalysisFindingEvidence.retrieval_rank,
            EvidenceRecord.id,
        )
    ).all()
    citations: list[AnalysisCitationRead] = []
    for finding_evidence, record, source in rows:
        try:
            citations.append(
                AnalysisCitationRead(
                    evidence_record_id=record.id,
                    evidence_kind=record.evidence_kind,
                    summary=record.summary,
                    scope=record.scope,
                    locator=record.locator,
                    excerpt=(record.excerpt if source.can_reproduce_excerpt else None),
                    source=AnalysisSourceRead(
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
                    ),
                    retrieval_rank=finding_evidence.retrieval_rank,
                )
            )
        except ValidationError:
            # Malformed stored URLs/content cannot become a displayed citation.
            logger.warning(
                "Withholding invalid evidence citation; evidence_record_id=%s", record.id
            )
    return citations


def _analysis_ingredient_reads(
    db: Session,
    analysis: ScanAnalysis,
) -> tuple[list[AnalysisIngredientRead], bool]:
    rows = db.scalars(
        select(AnalysisIngredient)
        .where(AnalysisIngredient.analysis_id == analysis.id)
        .order_by(AnalysisIngredient.position, AnalysisIngredient.id)
    ).all()
    results: list[AnalysisIngredientRead] = []
    stale = False
    for row in rows:
        current = resolve_ingredient(db, row.input_text)
        current_candidates = _candidate_snapshot(current)
        if (
            current.status != row.resolution_status
            or current.normalized_query != row.normalized_text
            or current.matching != row.matching
            or current_candidates != row.candidate_snapshot
        ):
            stale = True
        results.append(
            AnalysisIngredientRead(
                scan_ingredient_id=row.scan_ingredient_id,
                position=row.position,
                input_text=row.input_text,
                normalized_text=current.normalized_query,
                resolution=current,
            )
        )
    return results, stale


def _notice(
    status_value: str,
    findings_present: bool,
    unresolved_count: int,
) -> str:
    if status_value == "stale":
        return (
            "The catalog, active rules, or source rights changed after this run. "
            "No current findings are shown; run the analysis again."
        )
    if status_value == "no_active_rules":
        return (
            "No approved active rules are available, so no rule assessment was produced. "
            "This is not an assessment of safety."
        )
    if status_value == "needs_review" or unresolved_count:
        suffix = (
            " No rule matched the resolved items; that is not proof of safety."
            if not findings_present
            else " Findings may be incomplete because only exact matches are analyzed."
        )
        return (
            "One or more confirmed names remain unresolved or ambiguous; no guess was made."
            + suffix
        )
    if findings_present:
        return (
            "These matches cover only the reviewed rules and evidence listed here, "
            "not every possible concern."
        )
    return "No configured reviewed rule matched these confirmed items. This is not proof of safety."


def serialize_scan_analysis(db: Session, analysis: ScanAnalysis) -> ScanAnalysisRead:
    """Revalidate rules, catalog identities, source rights, and every returned citation."""
    current_rules = load_live_rules(db)
    current_rule_ids = {str(item.rule.id) for item in current_rules}
    snapshot_ids: set[str] = set()
    snapshot_rules: list[AnalysisRuleVersionRead] = []
    snapshot_valid = True
    for item in analysis.rule_snapshot:
        try:
            rule_id = str(UUID(item["id"]))
            key = item["rule_key"]
            version = item["version"]
            snapshot_ids.add(rule_id)
            snapshot_rules.append(
                AnalysisRuleVersionRead(id=UUID(rule_id), rule_key=key, version=version)
            )
        except (KeyError, TypeError, ValueError):
            snapshot_valid = False
    stale = (
        not snapshot_valid
        or snapshot_ids != current_rule_ids
        or analysis.rule_snapshot != _rule_snapshot(current_rules)
    )

    ingredients, ingredient_stale = _analysis_ingredient_reads(db, analysis)
    stale = stale or ingredient_stale
    unresolved_count = sum(item.resolution.status != "resolved" for item in ingredients)

    finding_rows = list(
        db.scalars(
            select(AnalysisFinding)
            .where(AnalysisFinding.analysis_id == analysis.id)
            .order_by(AnalysisFinding.ingredient_name, AnalysisFinding.rule_key, AnalysisFinding.id)
        ).all()
    )
    finding_reads: list[AnalysisFindingRead] = []
    for finding in finding_rows:
        citations = _current_citations(db, finding)
        if str(finding.rule_version_id) not in current_rule_ids or not citations:
            stale = True
            continue
        finding_reads.append(
            AnalysisFindingRead(
                id=finding.id,
                rule_key=finding.rule_key,
                rule_version=finding.rule_version,
                title=finding.title,
                message=finding.message,
                severity=finding.severity,
                ingredient_id=finding.ingredient_id,
                ingredient_name=finding.ingredient_name,
                citations=citations,
            )
        )

    if stale:
        status_value = "stale"
        finding_reads = []
    else:
        status_value = analysis.status
    return ScanAnalysisRead(
        id=analysis.id,
        scan_id=analysis.scan_id,
        status=status_value,
        rule_engine_version=analysis.engine_version,
        resolver_version=analysis.resolver_version,
        created_at=analysis.created_at,
        rule_versions=snapshot_rules,
        retrieval_status=analysis.retrieval_status,
        ingredients=ingredients,
        findings=finding_reads,
        unresolved_count=unresolved_count,
        notice=_notice(status_value, bool(finding_reads), unresolved_count),
        disclaimer=SAFETY_DISCLAIMER,
    )
