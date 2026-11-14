"""Synthetic unit tests for deterministic rules, Ollama embedding validation, and Qdrant filters."""

import json
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

import pytest
from qdrant_client import QdrantClient, models

from backend.app.schemas.safety_rules import IngredientPresenceCondition
from backend.app.services.rag.embeddings import EmbeddingError, OllamaEmbeddingProvider
from backend.app.services.rag.qdrant_store import QdrantEvidenceStore, QdrantStoreError
from backend.app.services.rag.retrieval import retrieve_rule_evidence
from backend.app.services.safety_rules.engine import (
    InvalidRuleCondition,
    parse_condition,
    rule_matches,
)


def test_deterministic_rule_matches_only_canonical_ids() -> None:
    target = uuid4()
    other = uuid4()
    condition = IngredientPresenceCondition(ingredient_ids=[target])

    assert rule_matches(condition, target) is True
    assert rule_matches(condition, other) is False
    assert parse_condition({"ingredient_ids": [str(target)]}) == condition

    try:
        parse_condition({"ingredient_ids": [str(target)], "python": "__import__('os')"})
    except InvalidRuleCondition:
        pass
    else:
        raise AssertionError("Unsupported rule fields must fail closed")


def test_qdrant_search_enforces_approved_metadata_ingredient_and_mapping_filters() -> None:
    client = QdrantClient(":memory:")
    store = QdrantEvidenceStore(client, "synthetic-filter-test")
    ingredient_id = uuid4()
    other_ingredient_id = uuid4()
    eligible_id, wrong_ingredient_id, pending_id, restricted_id = (uuid4() for _ in range(4))
    store.ensure_collection(2)

    points = [
        models.PointStruct(
            id=str(eligible_id),
            vector=[1.0, 0.0],
            payload={
                "evidence_record_id": str(eligible_id),
                "ingredient_id": str(ingredient_id),
                "source_id": str(uuid4()),
                "review_status": "approved",
                "source_rights_status": "approved",
            },
        ),
        models.PointStruct(
            id=str(wrong_ingredient_id),
            vector=[1.0, 0.0],
            payload={
                "evidence_record_id": str(wrong_ingredient_id),
                "ingredient_id": str(other_ingredient_id),
                "source_id": str(uuid4()),
                "review_status": "approved",
                "source_rights_status": "approved",
            },
        ),
        models.PointStruct(
            id=str(pending_id),
            vector=[1.0, 0.0],
            payload={
                "evidence_record_id": str(pending_id),
                "ingredient_id": str(ingredient_id),
                "source_id": str(uuid4()),
                "review_status": "pending",
                "source_rights_status": "approved",
            },
        ),
        models.PointStruct(
            id=str(restricted_id),
            vector=[1.0, 0.0],
            payload={
                "evidence_record_id": str(restricted_id),
                "ingredient_id": str(ingredient_id),
                "source_id": str(uuid4()),
                "review_status": "approved",
                "source_rights_status": "restricted",
            },
        ),
    ]
    client.upsert(collection_name=store.collection_name, points=points, wait=True)

    hits = store.search_approved_evidence(
        vector=[1.0, 0.0],
        ingredient_id=ingredient_id,
        allowed_evidence_ids={eligible_id, wrong_ingredient_id, pending_id, restricted_id},
        limit=5,
    )
    assert [hit.evidence_record_id for hit in hits] == [eligible_id]
    assert (
        store.search_approved_evidence(
            vector=[1.0, 0.0],
            ingredient_id=ingredient_id,
            allowed_evidence_ids=set(),
            limit=5,
        )
        == []
    )
    with pytest.raises(ValueError, match="finite numbers"):
        store.upsert_approved_evidence(
            evidence_record_id=uuid4(),
            ingredient_id=ingredient_id,
            source_id=uuid4(),
            vector=[float("nan")],
        )
    with pytest.raises(QdrantStoreError, match="dimensions"):
        store.ensure_collection(3)
    store.close()


def test_qdrant_collection_creation_race_accepts_the_concurrent_collection() -> None:
    client = Mock()
    client.collection_exists.side_effect = [False, True]
    client.create_collection.side_effect = RuntimeError("already exists")
    client.get_collection.return_value = SimpleNamespace(
        config=SimpleNamespace(
            params=SimpleNamespace(
                vectors=models.VectorParams(size=2, distance=models.Distance.COSINE)
            )
        )
    )
    store = QdrantEvidenceStore(client, "race-test")

    store.ensure_collection(2)

    client.create_collection.assert_called_once()
    assert client.collection_exists.call_count == 2
    client.get_collection.assert_called_once_with("race-test")


def test_ollama_embedding_api_response_is_validated_without_network(monkeypatch) -> None:
    class FakeResponse:
        def __init__(self, body: bytes) -> None:
            self.body = body

        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self, size: int = -1) -> bytes:
            return self.body if size < 0 else self.body[:size]

    def fake_urlopen(request, timeout: int):
        assert request.full_url == "http://ollama.test:11434/api/embed"
        assert timeout == 7
        posted = json.loads(request.data)
        assert posted == {"model": "fixture-embedding", "input": "Synthetic query text"}
        return FakeResponse(b'{"embeddings": [[1.0, 0.25]]}')

    monkeypatch.setattr("backend.app.services.rag.embeddings.urlopen", fake_urlopen)
    provider = OllamaEmbeddingProvider("http://ollama.test:11434/", "fixture-embedding", 7)
    assert provider.embed("Synthetic query text") == [1.0, 0.25]

    def invalid_response(_request, timeout: int):
        return FakeResponse(b'{"embeddings": [[NaN]]}')

    monkeypatch.setattr("backend.app.services.rag.embeddings.urlopen", invalid_response)
    try:
        provider.embed("Synthetic query text")
    except EmbeddingError:
        pass
    else:
        raise AssertionError("Non-finite model vectors must be rejected")


def test_retrieval_without_qdrant_or_approved_mapping_fails_closed() -> None:
    disabled = retrieve_rule_evidence(
        store=None,
        embedder=None,
        query="Synthetic test-only query",
        ingredient_id=uuid4(),
        approved_mappings=[],
        top_k=5,
    )
    assert disabled.status == "not_configured"
    assert disabled.rank_by_mapping_id == {}
