"""Conservative exact-name normalization for ingredient lookup."""

import re
import unicodedata

_LOCALE_PATTERN = re.compile(r"^[a-zA-Z]{2,8}(?:-[A-Za-z0-9]{1,8})*$")


def normalize_ingredient_name(value: str) -> str:
    """Apply Unicode NFKC, case folding, and whitespace collapse—never fuzzy matching.

    Punctuation is intentionally preserved so chemically distinct or editorially
    ambiguous names do not become accidental matches.
    """
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return " ".join(normalized.split())


def normalize_locale_tag(value: str) -> str:
    """Normalize a simple BCP-47-style language tag or the undetermined tag."""
    normalized = value.strip().replace("_", "-")
    if normalized.casefold() == "und":
        return "und"
    if not _LOCALE_PATTERN.fullmatch(normalized):
        raise ValueError("Locale must be 'und' or a language tag such as 'en' or 'en-US'")
    return normalized.casefold()
