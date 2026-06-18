import pytest

from setmeup.audio.filename import parse_filename


@pytest.mark.parametrize(
    "stem, artist, title",
    [
        ("Daft Punk - Around the World", "Daft Punk", "Around the World"),
        ("01 - Daft Punk - Around the World", "Daft Punk", "Around the World"),
        ("Artist - Title - Extended Mix", "Artist", "Title - Extended Mix"),
        ("just_a_blob", None, None),
    ],
)
def test_parse_filename(stem, artist, title):
    assert parse_filename(stem) == (artist, title)
