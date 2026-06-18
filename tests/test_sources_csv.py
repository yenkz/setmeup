from setmeup.sources.csv_source import CsvSource

HEADER = (
    "Track URI,Track Name,Album Name,Artist Name(s),Release Date,Duration (ms),"
    "Popularity,Explicit,Added By,Added At,Genres,Record Label\n"
)


def test_parses_exportify_rows(tmp_path):
    f = tmp_path / "Vinyl.csv"
    f.write_text(
        HEADER
        + 'spotify:track:6nk,"Asahi Ga Yondeiru","Asahi Ga Yondeiru",'
          '"Tornado Wallace;Courtney Bailey",2026-01-30,433510,21,false,'
          'yenkz,2026-05-30T20:22:08Z,"","Running Back"\n'
    )
    entries = list(CsvSource(f).entries())
    assert len(entries) == 1
    e = entries[0]
    assert e.artist == "Tornado Wallace"  # primary artist only
    assert e.title == "Asahi Ga Yondeiru"
    assert e.album == "Asahi Ga Yondeiru"
    assert e.duration_ms == 433510
    assert e.spotify_uri == "spotify:track:6nk"


def test_skips_rows_missing_artist_or_title(tmp_path):
    f = tmp_path / "x.csv"
    f.write_text(HEADER + 'uri,,"Album","",2026,1000,0,false,me,now,"","Label"\n')
    assert list(CsvSource(f).entries()) == []
