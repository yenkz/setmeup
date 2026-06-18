from setmeup.matching import normalize, normalize_key


def test_normalize_lowercases_strips_punct_and_collapses():
    assert normalize("  Daft   Punk! ") == "daft punk"


def test_key_is_case_and_punctuation_insensitive():
    assert normalize_key("Daft Punk", "Around the World", "Extended Mix") == normalize_key(
        "daft punk", "around the world!", "extended mix"
    )


def test_version_difference_changes_key():
    assert normalize_key("A", "T", "Extended Mix") != normalize_key("A", "T", None)


def test_none_version_normalizes_to_empty_segment():
    assert normalize_key("A", "T", None) == "a|t|"
