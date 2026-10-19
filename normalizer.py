"""String normalization for geographic names."""

from __future__ import annotations

import re
import unicodedata

# Apply longest patterns first.
CITY_PREFIX_PATTERNS = (
    r"island garden city of",
    r"science city of",
    r"municipality of",
    r"city of",
    r"town of",
)

CITY_SUFFIX_PATTERNS = (
    r"municipality",
    r"city",
)

PARENT_SUFFIX_PATTERNS = (
    r"province",
    r"region",
    r"state",
)

# Explicit expansions used at Level 4. Keys are normalized (lowercase, no punct).
ABBREVIATION_EXPANSIONS = {
    "gen": "general",
    "sta": "santa",
    "sto": "santo",
    "mt": "mount",
}

PUNCTUATION_RE = re.compile(r"[^\w\s]", re.UNICODE)
WHITESPACE_RE = re.compile(r"\s+")
APOSTROPHE_RE = re.compile(r"['’`´]")
PERIOD_RE = re.compile(r"\.")
CITY_PREFIX_RE = re.compile(
    rf"^(?:the\s+)?(?:{'|'.join(CITY_PREFIX_PATTERNS)})\s+",
    re.IGNORECASE,
)
CITY_SUFFIX_RE = re.compile(
    rf"\s+(?:{'|'.join(CITY_SUFFIX_PATTERNS)})$",
    re.IGNORECASE,
)
PARENT_SUFFIX_RE = re.compile(
    rf"\s+(?:{'|'.join(PARENT_SUFFIX_PATTERNS)})$",
    re.IGNORECASE,
)

# Extra tokens that often mean a split or renamed administrative unit.
ADMIN_SPLIT_TOKENS = frozenset(
    {
        "norte",
        "sur",
        "north",
        "south",
        "east",
        "west",
        "oriental",
        "occidental",
        "del",
        "de",
        "oro",
    }
)


def as_text(value) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    if text.lower() == "nan":
        return ""
    return text


def strip_diacritics(text: str) -> str:
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def basic_clean(value) -> str:
    """Level 1 cleaning: trim and collapse repeated whitespace."""
    return WHITESPACE_RE.sub(" ", as_text(value))


def _prepare_text(value) -> str:
    text = strip_diacritics(basic_clean(value)).casefold()
    text = APOSTROPHE_RE.sub("", text)
    text = PERIOD_RE.sub("", text)
    return text


def normalize_name(value) -> str:
    """
    Level 2 normalization: case, whitespace, punctuation, diacritics.

    Muñoz → munoz, M'lang → mlang, Gen. → gen
    """
    text = _prepare_text(value)
    text = PUNCTUATION_RE.sub(" ", text)
    return WHITESPACE_RE.sub(" ", text).strip()


def _strip_pattern(text: str, pattern: re.Pattern[str]) -> str:
    return WHITESPACE_RE.sub(" ", pattern.sub(" ", text)).strip()


def naming_core(value) -> str:
    """
    Level 3 core name after removing common city/municipality wrappers.

    City of Laoag → laoag, Tuguegarao City → tuguegarao
    """
    text = _prepare_text(value)
    text = _strip_pattern(text, CITY_PREFIX_RE)
    text = _strip_pattern(text, CITY_SUFFIX_RE)
    return normalize_name(text)


def parent_naming_core(value) -> str:
    """Strip trailing province/region/state labels from a parent name."""
    text = _prepare_text(value)
    text = _strip_pattern(text, PARENT_SUFFIX_RE)
    return normalize_name(text)


def expand_abbreviations(value) -> str:
    """Level 4: expand known abbreviations, then normalize."""
    text = _prepare_text(value)
    text = PUNCTUATION_RE.sub(" ", text)
    text = WHITESPACE_RE.sub(" ", text).strip()
    if not text:
        return ""

    parts = []
    for token in text.split(" "):
        parts.append(ABBREVIATION_EXPANSIONS.get(token, token))
    return WHITESPACE_RE.sub(" ", " ".join(parts)).strip()


def token_set(value) -> set[str]:
    text = normalize_name(value)
    if not text:
        return set()
    return set(text.split(" "))


def is_uncertain_admin_relationship(left, right) -> bool:
    """
    True when names look related but are not interchangeable.

    Example: Maguindanao vs Maguindanao del Norte / Maguindanao del Sur.
    """
    left_tokens = token_set(left)
    right_tokens = token_set(right)
    if not left_tokens or not right_tokens or left_tokens == right_tokens:
        return False

    smaller, larger = sorted((left_tokens, right_tokens), key=len)
    if not smaller.issubset(larger):
        return False

    extra = larger - smaller
    return bool(extra & ADMIN_SPLIT_TOKENS)
