from setmeup.sources.wantlist import WantlistSource


def test_parses_lines_skips_comments_and_blanks(tmp_path):
    f = tmp_path / "wl.txt"
    f.write_text(
        "# my crate\n"
        "Daft Punk - Around the World\n"
        "\n"
        "Aphex Twin - Xtal - Remaster\n"
    )
    entries = list(WantlistSource(f).entries())
    assert [(e.artist, e.title) for e in entries] == [
        ("Daft Punk", "Around the World"),
        ("Aphex Twin", "Xtal - Remaster"),
    ]


def test_skips_malformed_lines(tmp_path):
    f = tmp_path / "wl.txt"
    f.write_text("no dash here\nArtist - Title\n")
    entries = list(WantlistSource(f).entries())
    assert [(e.artist, e.title) for e in entries] == [("Artist", "Title")]
