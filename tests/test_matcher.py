from matcher import (
    SCOPE_ALL,
    SCOPE_CONFIRMED,
    SCOPE_PLAUSIBLE,
    STATUS_EXACT,
    STATUS_FUZZY,
    STATUS_NORMALIZED,
    STATUS_REVIEW,
    STATUS_UNMATCHED,
    STATUS_VARIANT,
    match_dataset,
    match_field,
)

REFERENCE = [
    ("Laoag", "Ilocos Norte"),
    ("Burgos", "Ilocos Norte"),
    ("Pasuquin", "Ilocos Norte"),
    ("Vigan", "Ilocos Sur"),
    ("Burgos", "Ilocos Sur"),
    ("Santa", "Ilocos Sur"),
    ("Tuguegarao", "Cagayan"),
    ("Calamba", "Laguna"),
    ("Muñoz", "Nueva Ecija"),
    ("M'lang", "Cotabato"),
    ("T'Boli", "South Cotabato"),
    ("General Tinio", "Nueva Ecija"),
    ("Cabanatuan", "Nueva Ecija"),
    ("Santa Rosa", "Laguna"),
    ("Iligan", "Lanao del Norte"),
    ("Iligan", "Lanao del Sur"),
    ("Datu Odin Sinsuat", "Maguindanao del Norte"),
    ("Buluan", "Maguindanao del Sur"),
    ("Shared Town", "Maguindanao del Norte"),
    ("Shared Town", "Maguindanao del Sur"),
]


def _match(location, province, min_score=80.0, min_margin=5.0, reference=None):
    return match_dataset(
        [(location, province)],
        reference or REFERENCE,
        min_score=min_score,
        min_margin=min_margin,
    )[0]


def test_exact_match():
    result = _match("Laoag", "Ilocos Norte")
    assert result.match_status == STATUS_EXACT
    assert result.matched_location == "Laoag"
    assert result.matched_province == "Ilocos Norte"
    assert result.match_score == 100.0
    assert result.municipality_search_scope == SCOPE_CONFIRMED
    assert result.province_match_status == STATUS_EXACT


def test_normalized_exact_munoz():
    result = _match("Munoz", "Nueva Ecija")
    assert result.match_status == STATUS_NORMALIZED
    assert result.matched_location == "Muñoz"


def test_normalized_exact_mlang_and_tboli():
    mlang = _match("Mlang", "Cotabato")
    assert mlang.match_status == STATUS_NORMALIZED
    assert mlang.matched_location == "M'lang"

    tboli = _match("TBoli", "South Cotabato")
    assert tboli.match_status == STATUS_NORMALIZED
    assert tboli.matched_location == "T'Boli"


def test_city_of_laoag_naming_variant():
    result = _match("City of Laoag", "Ilocos Norte")
    assert result.match_status == STATUS_VARIANT
    assert result.matched_location == "Laoag"


def test_tuguegarao_city_naming_variant():
    result = _match("Tuguegarao City", "Cagayan")
    assert result.match_status == STATUS_VARIANT
    assert result.matched_location == "Tuguegarao"


def test_science_city_of_munoz_naming_variant():
    result = _match("Science City of Muñoz", "Nueva Ecija")
    assert result.match_status == STATUS_VARIANT
    assert result.matched_location == "Muñoz"


def test_abbreviation_general_tinio():
    result = _match("Gen. Tinio", "Nueva Ecija")
    assert result.match_status == STATUS_VARIANT
    assert result.matched_location == "General Tinio"


def test_no_match_unknown_place():
    result = _match("Atlantis", "Nueva Ecija")
    assert result.match_status == STATUS_UNMATCHED
    assert result.matched_location is None


def test_province_scoped_matching():
    result = _match("Calamba", "Laguna")
    assert result.matched_location == "Calamba"
    assert result.matched_province == "Laguna"
    assert result.municipality_search_scope == SCOPE_CONFIRMED


def test_wrong_province_does_not_cross_match():
    result = _match("Calamba", "Nueva Ecija")
    assert result.match_status in {STATUS_UNMATCHED, STATUS_REVIEW}
    assert result.matched_location != "Calamba" or result.matched_province != "Laguna"
    assert result.municipality_search_scope == SCOPE_CONFIRMED


def test_ambiguous_fuzzy_match_needs_review():
    result = match_field(
        "Santa Cruz",
        ["Santa Cruz A", "Santa Cruz B"],
        min_score=80.0,
        min_margin=5.0,
        parent=False,
    )
    assert result.status == STATUS_REVIEW
    assert result.best_candidate is not None
    assert result.second_best_candidate is not None
    assert result.score_margin is not None
    assert result.score_margin < 5.0


def test_maguindanao_split_needs_review():
    result = match_field(
        "Maguindanao",
        ["Maguindanao del Norte", "Maguindanao del Sur", "Lanao del Norte"],
        min_score=80.0,
        min_margin=5.0,
        parent=True,
    )
    assert result.status == STATUS_REVIEW
    assert result.value is None


def test_single_maguindanao_successor_still_needs_review():
    result = match_field(
        "Maguindanao",
        ["Maguindanao del Norte", "Nueva Ecija"],
        min_score=80.0,
        min_margin=5.0,
        parent=True,
    )
    assert result.status == STATUS_REVIEW
    assert result.value is None


def test_high_confidence_fuzzy_typo():
    result = _match("Cabanataun", "Nueva Ecija")
    assert result.match_status == STATUS_FUZZY
    assert result.matched_location == "Cabanatuan"
    assert result.match_score >= 80


def test_incomplete_province_unique_municipality():
    result = _match("Pasuquin", "Ilocos")
    assert result.match_status == STATUS_EXACT
    assert result.matched_location == "Pasuquin"
    assert result.matched_province == "Ilocos Norte"
    assert result.municipality_search_scope == SCOPE_PLAUSIBLE
    assert result.province_match_status == STATUS_REVIEW
    assert "Ilocos Norte" in result.province_candidate_list
    assert "Ilocos Sur" in result.province_candidate_list
    assert result.province_match_status != STATUS_EXACT


def test_incomplete_province_duplicate_municipality():
    result = _match("Burgos", "Ilocos")
    assert result.match_status == STATUS_REVIEW
    assert result.matched_location is None
    assert result.municipality_search_scope == SCOPE_PLAUSIBLE
    assert result.best_candidate is not None
    assert result.second_best_candidate is not None
    assert "Ilocos Norte" in result.best_candidate or "Ilocos Norte" in result.second_best_candidate
    assert "Ilocos Sur" in result.best_candidate or "Ilocos Sur" in result.second_best_candidate
    assert result.review_reason


def test_incomplete_province_unique_fuzzy_municipality():
    result = _match("Pasuqin", "Ilocos")
    assert result.match_status == STATUS_FUZZY
    assert result.matched_location == "Pasuquin"
    assert result.matched_province == "Ilocos Norte"
    assert result.municipality_search_scope == SCOPE_PLAUSIBLE
    assert result.province_match_status == STATUS_REVIEW


def test_incomplete_province_no_municipality_match():
    result = _match("Atlantis", "Ilocos")
    assert result.match_status == STATUS_UNMATCHED
    assert result.matched_location is None
    assert result.municipality_search_scope == SCOPE_PLAUSIBLE


def test_confident_province_stays_restricted():
    result = _match("Burgos", "Ilocos Norte")
    assert result.match_status == STATUS_EXACT
    assert result.matched_location == "Burgos"
    assert result.matched_province == "Ilocos Norte"
    assert result.municipality_search_scope == SCOPE_CONFIRMED
    assert result.province_match_status == STATUS_EXACT


def test_competing_fuzzy_municipality_candidates():
    reference = [
        ("Santa Cruz Norte", "Demo Province"),
        ("Santa Cruz Sur", "Demo Province"),
    ]
    result = _match("Santa Cruz", "Demo Province", reference=reference)
    assert result.match_status == STATUS_REVIEW
    assert result.municipality_search_scope == SCOPE_CONFIRMED
    assert result.score_margin is not None
    assert result.score_margin < 5.0


def test_unresolved_province_broader_fallback_does_not_silently_match():
    result = _match("Atlantis", "ZZ Nonexistent Province")
    assert result.match_status == STATUS_UNMATCHED
    assert result.matched_location is None
    assert result.municipality_search_scope == SCOPE_ALL
    assert result.province_match_status == STATUS_UNMATCHED


def test_unresolved_province_broader_fallback_does_not_accept_unrelated_fuzzy():
    result = _match("Laoagx", "ZZ Nonexistent Province")
    assert result.match_status in {STATUS_UNMATCHED, STATUS_REVIEW}
    assert result.matched_location is None
    assert result.municipality_search_scope == SCOPE_ALL


def test_maguindanao_is_not_automatically_mapped():
    result = _match("Shared Town", "Maguindanao")
    assert result.province_match_status == STATUS_REVIEW
    assert result.province_match_status != STATUS_EXACT
    assert result.matched_province is None
    assert result.match_status == STATUS_REVIEW
    assert result.municipality_search_scope == SCOPE_PLAUSIBLE
    assert "Maguindanao del Norte" in result.province_candidate_list
    assert "Maguindanao del Sur" in result.province_candidate_list


def test_maguindanao_unique_municipality_can_resolve_location():
    result = _match("Buluan", "Maguindanao")
    assert result.match_status == STATUS_EXACT
    assert result.matched_location == "Buluan"
    assert result.matched_province == "Maguindanao del Sur"
    assert result.province_match_status == STATUS_REVIEW
    assert result.municipality_search_scope == SCOPE_PLAUSIBLE
