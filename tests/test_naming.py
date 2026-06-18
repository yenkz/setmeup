from setmeup.naming import build_canonical_name, sanitize


def test_three_part_name():
    assert (
        build_canonical_name("Daft Punk", "Around the World", "Extended Mix")
        == "Daft Punk - Around the World - Extended Mix"
    )


def test_two_part_name_when_no_version():
    assert (
        build_canonical_name("Daft Punk", "Around the World", None)
        == "Daft Punk - Around the World"
    )


def test_sanitize_strips_illegal_characters():
    assert sanitize('a/b:c?d|e*f') == "abcdef"


def test_sanitize_collapses_whitespace():
    assert sanitize("a    b   c") == "a b c"
