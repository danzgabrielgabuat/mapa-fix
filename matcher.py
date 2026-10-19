"""Deterministic-then-fuzzy geographic name matching."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from rapidfuzz import fuzz

from normalizer import (
    ADMIN_SPLIT_TOKENS,
    basic_clean,
    expand_abbreviations,
    is_uncertain_admin_relationship,
    naming_core,
    normalize_name,
    parent_naming_core,
    token_set,
)

STATUS_EXACT = "Exact"
STATUS_NORMALIZED = "Normalized Exact"
STATUS_VARIANT = "Naming Variant"
STATUS_FUZZY = "Fuzzy High Confidence"
STATUS_REVIEW = "Needs Review"
STATUS_UNMATCHED = "Unmatched"

AUTOMATIC_STATUSES = {
    STATUS_EXACT,
    STATUS_NORMALIZED,
    STATUS_VARIANT,
    STATUS_FUZZY,
}

SCORERS = (
    ("token_set_ratio", fuzz.token_set_ratio),
    ("token_sort_ratio", fuzz.token_sort_ratio),
    ("WRatio", fuzz.WRatio),
    ("ratio", fuzz.ratio),
)

SCOPE_CONFIRMED = "Confirmed province"
SCOPE_PLAUSIBLE = "Plausible provinces"
SCOPE_ALL = "All reference locations"

REASON_MULTIPLE = "Multiple municipality candidates"
REASON_MARGIN = "Insufficient fuzzy score margin"
REASON_UNRESOLVED_COMPETING = "Unresolved province with competing municipality matches"
REASON_NO_CANDIDATE = "No convincing candidate"
REASON_UNCERTAIN_ADMIN = "Uncertain administrative relationship"

METHOD_STATUS = {
    "exact": STATUS_EXACT,
    "normalized_exact": STATUS_NORMALIZED,
    "naming_variant": STATUS_VARIANT,
    "abbreviation": STATUS_VARIANT,
    "parent_variant": STATUS_VARIANT,
}

MIN_RELATED_PARENT_QUERY_LEN = 4

AUDIT_COLUMNS = [
    "Input Location",
    "Input Municipality",
    "Input Province",
    "Matched Location",
    "Matched Municipality",
    "Matched Province",
    "Province Match Method",
    "Province Match Score",
    "Province Match Status",
    "Province Candidate Count",
    "Province Candidate List",
    "Municipality Match Method",
    "Municipality Match Score",
    "Municipality Match Status",
    "Municipality Candidate Count",
    "Match Score",
    "Match Method",
    "Match Status",
    "Candidate Count",
    "Best Candidate",
    "Second-Best Candidate",
    "Score Margin",
    "Municipality Search Scope",
    "Review Reason",
]


@dataclass
class FieldMatch:
    value: Optional[str]
    score: Optional[float]
    method: str
    status: str
    candidate_count: int
    best_candidate: Optional[str]
    second_best_candidate: Optional[str]
    score_margin: Optional[float]
    matched_parent: Optional[str] = None
    review_reason: Optional[str] = None


@dataclass
class RowMatch:
    input_location: str
    input_province: str
    matched_location: Optional[str]
    matched_province: Optional[str]
    match_score: Optional[float]
    match_method: str
    match_status: str
    candidate_count: int
    best_candidate: Optional[str]
    second_best_candidate: Optional[str]
    score_margin: Optional[float]
    province_match_method: str
    province_match_score: Optional[float]
    province_match_status: str
    province_candidate_count: int
    province_candidate_list: str
    municipality_search_scope: str
    review_reason: Optional[str]

    def to_audit_dict(self) -> dict:
        return {
            "Input Location": self.input_location,
            "Input Municipality": self.input_location,
            "Input Province": self.input_province,
            "Matched Location": self.matched_location,
            "Matched Municipality": self.matched_location,
            "Matched Province": self.matched_province,
            "Province Match Method": self.province_match_method,
            "Province Match Score": self.province_match_score,
            "Province Match Status": self.province_match_status,
            "Province Candidate Count": self.province_candidate_count,
            "Province Candidate List": self.province_candidate_list,
            "Municipality Match Method": self.match_method,
            "Municipality Match Score": self.match_score,
            "Municipality Match Status": self.match_status,
            "Municipality Candidate Count": self.candidate_count,
            "Match Score": self.match_score,
            "Match Method": self.match_method,
            "Match Status": self.match_status,
            "Candidate Count": self.candidate_count,
            "Best Candidate": self.best_candidate,
            "Second-Best Candidate": self.second_best_candidate,
            "Score Margin": self.score_margin,
            "Municipality Search Scope": self.municipality_search_scope,
            "Review Reason": self.review_reason,
        }


def unique_nonempty(values: Iterable) -> list[str]:
    seen = set()
    result = []
    for value in values:
        text = basic_clean(value)
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def unique_records(records: Iterable[tuple[str, str]]) -> list[tuple[str, str]]:
    seen = set()
    result = []
    for location, parent in records:
        location_text = basic_clean(location)
        parent_text = basic_clean(parent)
        if not location_text or not parent_text:
            continue
        key = (location_text, parent_text)
        if key in seen:
            continue
        seen.add(key)
        result.append(key)
    return result


def _empty_match(
    status: str,
    method: str,
    candidate_count: int = 0,
    review_reason: Optional[str] = None,
) -> FieldMatch:
    return FieldMatch(
        value=None,
        score=None,
        method=method,
        status=status,
        candidate_count=candidate_count,
        best_candidate=None,
        second_best_candidate=None,
        score_margin=None,
        review_reason=review_reason,
    )


def _resolved(
    value: str,
    *,
    score: float,
    method: str,
    status: str,
    candidate_count: int,
    second_best: Optional[str] = None,
    margin: Optional[float] = None,
    matched_parent: Optional[str] = None,
) -> FieldMatch:
    return FieldMatch(
        value=value,
        score=score,
        method=method,
        status=status,
        candidate_count=candidate_count,
        best_candidate=value if matched_parent is None else f"{value} ({matched_parent})",
        second_best_candidate=second_best,
        score_margin=margin,
        matched_parent=matched_parent,
    )


def _review(
    *,
    method: str,
    candidate_count: int,
    best: Optional[str],
    second: Optional[str],
    score: Optional[float],
    margin: Optional[float],
    review_reason: Optional[str] = None,
) -> FieldMatch:
    return FieldMatch(
        value=None,
        score=score,
        method=method,
        status=STATUS_REVIEW,
        candidate_count=candidate_count,
        best_candidate=best,
        second_best_candidate=second,
        score_margin=margin,
        review_reason=review_reason,
    )


def _lookup_unique(query_key: str, index: dict[str, list]) -> Optional[list]:
    if not query_key:
        return None
    return index.get(query_key)


def _unique_or_review(matches: list[str], method: str, candidate_count: int) -> Optional[FieldMatch]:
    distinct = unique_nonempty(matches)
    if not distinct:
        return None
    if len(distinct) == 1:
        return _resolved(
            distinct[0],
            score=100.0,
            method=method,
            status=METHOD_STATUS[method],
            candidate_count=candidate_count,
        )
    return _review(
        method=method,
        candidate_count=candidate_count,
        best=distinct[0],
        second=distinct[1] if len(distinct) > 1 else None,
        score=100.0,
        margin=0.0,
        review_reason=REASON_MULTIPLE,
    )


def _record_label(location: str, parent: str, with_parent: bool) -> str:
    if with_parent:
        return f"{location} ({parent})"
    return location


def _unique_records_or_review(
    matches: list[tuple[str, str]],
    method: str,
    candidate_count: int,
    *,
    with_parent_label: bool,
    multi_reason: str,
) -> Optional[FieldMatch]:
    distinct = unique_records(matches)
    if not distinct:
        return None
    if len(distinct) == 1:
        location, parent = distinct[0]
        result = _resolved(
            location,
            score=100.0,
            method=method,
            status=METHOD_STATUS[method],
            candidate_count=candidate_count,
            matched_parent=parent,
        )
        result.best_candidate = _record_label(location, parent, with_parent_label)
        return result
    return _review(
        method=method,
        candidate_count=candidate_count,
        best=_record_label(distinct[0][0], distinct[0][1], True),
        second=_record_label(distinct[1][0], distinct[1][1], True),
        score=100.0,
        margin=0.0,
        review_reason=multi_reason,
    )


def _build_indexes(names: list[str], *, parent: bool) -> dict[str, dict[str, list[str]]]:
    indexes = {
        "exact": {},
        "normalized": {},
        "core": {},
        "expanded": {},
    }
    for name in names:
        indexes["exact"].setdefault(basic_clean(name), []).append(name)
        indexes["normalized"].setdefault(normalize_name(name), []).append(name)
        core = parent_naming_core(name) if parent else naming_core(name)
        indexes["core"].setdefault(core, []).append(name)
        indexes["expanded"].setdefault(expand_abbreviations(name), []).append(name)
    return indexes


def _build_record_indexes(records: list[tuple[str, str]]) -> dict[str, dict[str, list[tuple[str, str]]]]:
    indexes = {
        "exact": {},
        "normalized": {},
        "core": {},
        "expanded": {},
    }
    for location, parent in records:
        indexes["exact"].setdefault(basic_clean(location), []).append((location, parent))
        indexes["normalized"].setdefault(normalize_name(location), []).append((location, parent))
        indexes["core"].setdefault(naming_core(location), []).append((location, parent))
        indexes["expanded"].setdefault(expand_abbreviations(location), []).append((location, parent))
    return indexes


def _score_pair(left: str, right: str) -> tuple[float, str]:
    best_score = -1.0
    best_name = "ratio"
    a = normalize_name(left)
    b = normalize_name(right)
    for name, func in SCORERS:
        score = float(func(a, b))
        if score > best_score:
            best_score = score
            best_name = name
    return best_score, best_name


def _fuzzy_match(
    query: str,
    candidates: list[str],
    min_score: float,
    min_margin: float,
) -> FieldMatch:
    if not query or not candidates:
        return _empty_match(
            STATUS_UNMATCHED,
            "no_match",
            len(candidates),
            review_reason=REASON_NO_CANDIDATE,
        )

    ranked = []
    for candidate in candidates:
        score, scorer_name = _score_pair(query, candidate)
        ranked.append((candidate, score, scorer_name))

    ranked.sort(key=lambda item: item[1], reverse=True)
    best_name, best_score, best_method = ranked[0]
    second_name = ranked[1][0] if len(ranked) > 1 else None
    second_score = ranked[1][1] if len(ranked) > 1 else None
    margin = None if second_score is None else round(best_score - second_score, 4)

    if best_score < min_score:
        return FieldMatch(
            value=None,
            score=round(best_score, 4),
            method=best_method,
            status=STATUS_UNMATCHED,
            candidate_count=len(candidates),
            best_candidate=best_name,
            second_best_candidate=second_name,
            score_margin=margin,
            review_reason=REASON_NO_CANDIDATE,
        )

    if margin is not None and margin < min_margin:
        return _review(
            method=best_method,
            candidate_count=len(candidates),
            best=best_name,
            second=second_name,
            score=round(best_score, 4),
            margin=margin,
            review_reason=REASON_MARGIN,
        )

    if is_uncertain_admin_relationship(query, best_name):
        return _review(
            method="uncertain_admin",
            candidate_count=len(candidates),
            best=best_name,
            second=second_name,
            score=round(best_score, 4),
            margin=margin,
            review_reason=REASON_UNCERTAIN_ADMIN,
        )

    return _resolved(
        best_name,
        score=round(best_score, 4),
        method=best_method,
        status=STATUS_FUZZY,
        candidate_count=len(candidates),
        second_best=second_name,
        margin=margin,
    )


def _fuzzy_match_records(
    query: str,
    records: list[tuple[str, str]],
    min_score: float,
    min_margin: float,
    *,
    with_parent_label: bool,
    multi_reason: str,
    allow_fuzzy_accept: bool,
) -> FieldMatch:
    if not query or not records:
        return _empty_match(
            STATUS_UNMATCHED,
            "no_match",
            len(records),
            review_reason=REASON_NO_CANDIDATE,
        )

    ranked = []
    for location, parent in records:
        score, scorer_name = _score_pair(query, location)
        ranked.append((location, parent, score, scorer_name))

    ranked.sort(key=lambda item: item[2], reverse=True)
    best_loc, best_parent, best_score, best_method = ranked[0]
    second = ranked[1] if len(ranked) > 1 else None
    second_score = None if second is None else second[2]
    margin = None if second_score is None else round(best_score - second_score, 4)
    best_label = _record_label(best_loc, best_parent, with_parent_label or second is not None)
    second_label = None
    if second is not None:
        second_label = _record_label(second[0], second[1], True)

    if best_score < min_score:
        return FieldMatch(
            value=None,
            score=round(best_score, 4),
            method=best_method,
            status=STATUS_UNMATCHED,
            candidate_count=len(records),
            best_candidate=best_label,
            second_best_candidate=second_label,
            score_margin=margin,
            review_reason=REASON_NO_CANDIDATE,
        )

    if margin is not None and margin < min_margin:
        return _review(
            method=best_method,
            candidate_count=len(records),
            best=best_label,
            second=second_label,
            score=round(best_score, 4),
            margin=margin,
            review_reason=REASON_MARGIN if with_parent_label is False else multi_reason if second[1] != best_parent else REASON_MARGIN,
        )

    if not allow_fuzzy_accept:
        return _review(
            method=best_method,
            candidate_count=len(records),
            best=best_label,
            second=second_label,
            score=round(best_score, 4),
            margin=margin,
            review_reason=REASON_NO_CANDIDATE,
        )

    result = _resolved(
        best_loc,
        score=round(best_score, 4),
        method=best_method,
        status=STATUS_FUZZY,
        candidate_count=len(records),
        second_best=second_label,
        margin=margin,
        matched_parent=best_parent,
    )
    result.best_candidate = best_label
    return result


def match_field(
    query,
    candidates: list[str],
    min_score: float = 80.0,
    min_margin: float = 5.0,
    *,
    parent: bool = False,
) -> FieldMatch:
    query_text = basic_clean(query)
    candidate_count = len(candidates)
    if not query_text:
        return _empty_match(STATUS_UNMATCHED, "empty_query", candidate_count, REASON_NO_CANDIDATE)
    if not candidates:
        return _empty_match(STATUS_UNMATCHED, "no_candidates", 0, REASON_NO_CANDIDATE)

    indexes = _build_indexes(candidates, parent=parent)

    exact = _lookup_unique(query_text, indexes["exact"])
    if exact is not None:
        result = _unique_or_review(exact, "exact", candidate_count)
        if result:
            return result

    normalized = _lookup_unique(normalize_name(query_text), indexes["normalized"])
    if normalized is not None:
        result = _unique_or_review(normalized, "normalized_exact", candidate_count)
        if result:
            return result

    core_fn = parent_naming_core if parent else naming_core
    core = _lookup_unique(core_fn(query_text), indexes["core"])
    if core is not None:
        result = _unique_or_review(core, "parent_variant" if parent else "naming_variant", candidate_count)
        if result:
            if parent and result.status in AUTOMATIC_STATUSES:
                if is_uncertain_admin_relationship(query_text, result.value):
                    return _review(
                        method="uncertain_admin",
                        candidate_count=candidate_count,
                        best=result.value,
                        second=result.second_best_candidate,
                        score=result.score,
                        margin=result.score_margin,
                        review_reason=REASON_UNCERTAIN_ADMIN,
                    )
            return result

    expanded = _lookup_unique(expand_abbreviations(query_text), indexes["expanded"])
    if expanded is not None:
        result = _unique_or_review(expanded, "abbreviation", candidate_count)
        if result:
            return result

    return _fuzzy_match(
        query_text,
        candidates,
        min_score,
        min_margin,
    )


def match_location_records(
    query,
    records: list[tuple[str, str]],
    min_score: float = 80.0,
    min_margin: float = 5.0,
    *,
    with_parent_label: bool = False,
    multi_reason: str = REASON_MULTIPLE,
    allow_fuzzy_accept: bool = True,
) -> FieldMatch:
    query_text = basic_clean(query)
    records = unique_records(records)
    candidate_count = len(records)
    if not query_text:
        return _empty_match(STATUS_UNMATCHED, "empty_query", candidate_count, REASON_NO_CANDIDATE)
    if not records:
        return _empty_match(STATUS_UNMATCHED, "no_candidates", 0, REASON_NO_CANDIDATE)

    indexes = _build_record_indexes(records)

    exact = _lookup_unique(query_text, indexes["exact"])
    if exact is not None:
        result = _unique_records_or_review(
            exact,
            "exact",
            candidate_count,
            with_parent_label=with_parent_label,
            multi_reason=multi_reason,
        )
        if result:
            return result

    normalized = _lookup_unique(normalize_name(query_text), indexes["normalized"])
    if normalized is not None:
        result = _unique_records_or_review(
            normalized,
            "normalized_exact",
            candidate_count,
            with_parent_label=with_parent_label,
            multi_reason=multi_reason,
        )
        if result:
            return result

    core = _lookup_unique(naming_core(query_text), indexes["core"])
    if core is not None:
        result = _unique_records_or_review(
            core,
            "naming_variant",
            candidate_count,
            with_parent_label=with_parent_label,
            multi_reason=multi_reason,
        )
        if result:
            return result

    expanded = _lookup_unique(expand_abbreviations(query_text), indexes["expanded"])
    if expanded is not None:
        result = _unique_records_or_review(
            expanded,
            "abbreviation",
            candidate_count,
            with_parent_label=with_parent_label,
            multi_reason=multi_reason,
        )
        if result:
            return result

    return _fuzzy_match_records(
        query_text,
        records,
        min_score,
        min_margin,
        with_parent_label=with_parent_label,
        multi_reason=multi_reason,
        allow_fuzzy_accept=allow_fuzzy_accept,
    )


def related_parent_names(query, parent_names: list[str]) -> list[str]:
    """
    Conservative plausible-parent expansion.

    A shared prefix or directional qualifier is evidence for a candidate set,
    not proof that the names are administratively equivalent.
    """
    query_text = basic_clean(query)
    query_norm = normalize_name(query_text)
    query_core = parent_naming_core(query_text)
    query_tokens = token_set(query_text)
    content_tokens = {token for token in query_tokens if token not in ADMIN_SPLIT_TOKENS}

    if not query_norm or not content_tokens:
        return []
    if len(query_norm) < MIN_RELATED_PARENT_QUERY_LEN:
        return []

    related = []
    for name in parent_names:
        name_norm = normalize_name(name)
        name_core = parent_naming_core(name)
        name_tokens = token_set(name)
        if not name_norm:
            continue
        if name_norm == query_norm or name_core == query_core:
            related.append(name)
            continue
        if name_norm.startswith(query_norm + " ") or name_core.startswith(query_core + " "):
            related.append(name)
            continue
        if query_norm.startswith(name_norm + " ") or query_core.startswith(name_core + " "):
            related.append(name)
            continue
        if content_tokens.issubset(name_tokens) and is_uncertain_admin_relationship(query_text, name):
            related.append(name)
    return unique_nonempty(related)


def resolve_search_scope(
    province,
    parent_names: list[str],
    parent_match: FieldMatch,
) -> tuple[list[str], str]:
    if parent_match.status in AUTOMATIC_STATUSES and parent_match.value:
        return [parent_match.value], SCOPE_CONFIRMED

    related = related_parent_names(province, parent_names)
    if related:
        return related, SCOPE_PLAUSIBLE
    return list(parent_names), SCOPE_ALL


def _row_from_parts(
    *,
    input_location: str,
    input_province: str,
    location_match: FieldMatch,
    parent_match: FieldMatch,
    parent_candidates: list[str],
    search_scope: str,
) -> RowMatch:
    review_reason = location_match.review_reason
    if location_match.status != STATUS_REVIEW:
        if location_match.status == STATUS_UNMATCHED:
            review_reason = location_match.review_reason or REASON_NO_CANDIDATE
        else:
            review_reason = None

    return RowMatch(
        input_location=input_location,
        input_province=input_province,
        matched_location=location_match.value,
        matched_province=location_match.matched_parent,
        match_score=location_match.score,
        match_method=location_match.method,
        match_status=location_match.status,
        candidate_count=location_match.candidate_count,
        best_candidate=location_match.best_candidate,
        second_best_candidate=location_match.second_best_candidate,
        score_margin=location_match.score_margin,
        province_match_method=parent_match.method,
        province_match_score=parent_match.score,
        province_match_status=parent_match.status,
        province_candidate_count=len(parent_candidates),
        province_candidate_list="; ".join(parent_candidates),
        municipality_search_scope=search_scope,
        review_reason=review_reason,
    )


def match_row(
    location,
    province,
    reference_locations_by_parent: dict[str, list[str]],
    parent_names: list[str],
    min_score: float = 80.0,
    min_margin: float = 5.0,
) -> RowMatch:
    parent_match = match_field(
        province,
        parent_names,
        min_score=min_score,
        min_margin=min_margin,
        parent=True,
    )

    input_location = basic_clean(location)
    input_province = basic_clean(province)
    parent_candidates, search_scope = resolve_search_scope(province, parent_names, parent_match)

    records = []
    for parent in parent_candidates:
        for loc in reference_locations_by_parent.get(parent, []):
            records.append((loc, parent))
    records = unique_records(records)

    with_parent_label = search_scope != SCOPE_CONFIRMED
    if search_scope == SCOPE_PLAUSIBLE:
        multi_reason = REASON_UNRESOLVED_COMPETING
    elif search_scope == SCOPE_ALL:
        multi_reason = REASON_UNRESOLVED_COMPETING
    else:
        multi_reason = REASON_MULTIPLE

    location_match = match_location_records(
        location,
        records,
        min_score=min_score,
        min_margin=min_margin,
        with_parent_label=with_parent_label,
        multi_reason=multi_reason,
        allow_fuzzy_accept=search_scope != SCOPE_ALL,
    )

    if search_scope == SCOPE_CONFIRMED and location_match.value is not None:
        location_match.matched_parent = parent_match.value
        location_match.best_candidate = location_match.value

    return _row_from_parts(
        input_location=input_location,
        input_province=input_province,
        location_match=location_match,
        parent_match=parent_match,
        parent_candidates=parent_candidates,
        search_scope=search_scope,
    )


def match_dataset(
    input_rows: Iterable[tuple],
    reference_rows: Iterable[tuple],
    min_score: float = 80.0,
    min_margin: float = 5.0,
) -> list[RowMatch]:
    locations_by_parent: dict[str, list[str]] = {}
    parent_names = []
    for location, parent in reference_rows:
        parent_text = basic_clean(parent)
        location_text = basic_clean(location)
        if not parent_text or not location_text:
            continue
        if parent_text not in locations_by_parent:
            parent_names.append(parent_text)
            locations_by_parent[parent_text] = []
        locations_by_parent[parent_text].append(location_text)

    parent_names = unique_nonempty(parent_names)
    results = []
    for location, parent in input_rows:
        results.append(
            match_row(
                location,
                parent,
                locations_by_parent,
                parent_names,
                min_score=min_score,
                min_margin=min_margin,
            )
        )
    return results


def summarize(results: list[RowMatch]) -> dict[str, float]:
    total = len(results)
    counts = {
        "total_rows": total,
        "exact_matches": 0,
        "normalized_matches": 0,
        "naming_variant_matches": 0,
        "fuzzy_matches": 0,
        "needs_review_rows": 0,
        "unmatched_rows": 0,
    }
    for row in results:
        if row.match_status == STATUS_EXACT:
            counts["exact_matches"] += 1
        elif row.match_status == STATUS_NORMALIZED:
            counts["normalized_matches"] += 1
        elif row.match_status == STATUS_VARIANT:
            counts["naming_variant_matches"] += 1
        elif row.match_status == STATUS_FUZZY:
            counts["fuzzy_matches"] += 1
        elif row.match_status == STATUS_REVIEW:
            counts["needs_review_rows"] += 1
        else:
            counts["unmatched_rows"] += 1

    automatic = (
        counts["exact_matches"]
        + counts["normalized_matches"]
        + counts["naming_variant_matches"]
        + counts["fuzzy_matches"]
    )
    counts["automatic_matching_rate"] = 0.0 if total == 0 else round(100.0 * automatic / total, 2)
    return counts


def results_to_records(results: list[RowMatch]) -> list[dict]:
    return [row.to_audit_dict() for row in results]
