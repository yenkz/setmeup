import pytest

from setmeup.audio.version import extract_version


@pytest.mark.parametrize(
    "title, expected_title, expected_version",
    [
        ("Around the World (Extended Mix)", "Around the World", "Extended Mix"),
        ("Strobe (Eric Prydz Remix)", "Strobe", "Eric Prydz Remix"),
        ("Track [Radio Edit]", "Track", "Radio Edit"),
        ("One More Time", "One More Time", None),
        ("Song (feat. Pharrell)", "Song (feat. Pharrell)", None),
        ("Voodoo People (Instrumental)", "Voodoo People", "Instrumental"),
    ],
)
def test_extract_version(title, expected_title, expected_version):
    cleaned, version = extract_version(title)
    assert cleaned == expected_title
    assert version == expected_version
