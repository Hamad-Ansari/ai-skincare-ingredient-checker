"""Tests for conservative normalization and the intentionally empty production seed."""

import json
from pathlib import Path

import pytest

from backend.app.schemas.ingredients import EvidenceSourceCreate
from backend.app.services.ingredients.normalization import (
    normalize_ingredient_name,
    normalize_locale_tag,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def test_name_normalization_is_unicode_aware_and_whitespace_only() -> None:
    assert normalize_ingredient_name("  ＡＱＵＡ\u2003Water  ") == "aqua water"
    assert normalize_ingredient_name("Coco-caprylate") != normalize_ingredient_name("Cococaprylate")


def test_locale_normalization_accepts_language_tags_and_rejects_garbage() -> None:
    assert normalize_locale_tag("EN_us") == "en-us"
    assert normalize_locale_tag(" und ") == "und"
    with pytest.raises(ValueError):
        normalize_locale_tag("not a locale")


def test_source_registry_rejects_credentials_and_query_strings_in_urls() -> None:
    with pytest.raises(ValueError):
        EvidenceSourceCreate(
            publisher="Example Publisher",
            title="Reference",
            canonical_url="https://user:password@example.com/catalog",
            source_type="reference",
            license_name="Pending review",
            attribution_text="Attribution text for test.",
        )
    with pytest.raises(ValueError):
        EvidenceSourceCreate(
            publisher="Example Publisher",
            title="Reference",
            canonical_url="https://example.com/catalog?access_token=secret",
            source_type="reference",
            license_name="Pending review",
            attribution_text="Attribution text for test.",
        )


def test_production_seed_manifest_contains_no_unreviewed_or_fabricated_records() -> None:
    manifest_path = PROJECT_ROOT / "data" / "seed" / "ingredient_seed_manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert manifest["manifest_version"] == 1
    assert manifest["state"] == "awaiting_reviewed_sources"
    assert manifest["sources"] == []
    assert manifest["imports"] == []
