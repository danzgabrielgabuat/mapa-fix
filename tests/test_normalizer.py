from normalizer import (
    expand_abbreviations,
    is_uncertain_admin_relationship,
    naming_core,
    normalize_name,
)


def test_normalize_munoz_diacritic():
    assert normalize_name("Muñoz") == "munoz"
    assert normalize_name("Munoz") == "munoz"


def test_normalize_mlang_apostrophe():
    assert normalize_name("M'lang") == "mlang"
    assert normalize_name("Mlang") == "mlang"
    assert normalize_name("MLang") == "mlang"


def test_normalize_tboli_apostrophe():
    assert normalize_name("T'Boli") == "tboli"
    assert normalize_name("TBoli") == "tboli"


def test_normalize_punctuation_and_case():
    assert normalize_name("  Gen.  ") == "gen"
    assert normalize_name("Laoag,") == "laoag"


def test_naming_core_city_wrappers():
    assert naming_core("City of Laoag") == naming_core("Laoag")
    assert naming_core("Tuguegarao City") == naming_core("Tuguegarao")
    assert naming_core("City of Calamba") == naming_core("Calamba")
    assert naming_core("Science City of Muñoz") == naming_core("Muñoz")
    assert naming_core("Science City of Muñoz") == "munoz"


def test_abbreviation_gen_to_general():
    assert expand_abbreviations("Gen.") == "general"
    assert expand_abbreviations("Gen") == "general"
    assert expand_abbreviations("General") == "general"


def test_maguindanao_is_not_treated_as_the_same_unit():
    assert is_uncertain_admin_relationship("Maguindanao", "Maguindanao del Norte")
    assert is_uncertain_admin_relationship("Maguindanao", "Maguindanao del Sur")
    assert not is_uncertain_admin_relationship("Maguindanao del Norte", "Maguindanao del Norte")
    assert not is_uncertain_admin_relationship("Laoag", "Laoag City")
