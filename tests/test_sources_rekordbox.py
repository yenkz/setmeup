from pathlib import Path

from setmeup.sources.rekordbox import RkTrack, decode_location, list_playlists, parse_collection

COLLECTION_XML = """<?xml version="1.0" encoding="UTF-8"?>
<DJ_PLAYLISTS Version="1.0.0">
  <COLLECTION Entries="3">
    <TRACK TrackID="1" Location="file://localhost/m/a.flac" Artist="Aphex Twin" Name="Xtal" Album="SAW" TotalTime="294" Kind="FLAC File"/>
    <TRACK TrackID="2" Location="file://localhost/m/b.mp3" Artist="Daft Punk" Name="Da Funk"/>
    <TRACK TrackID="3" Location="file://localhost/m/c.wav" Artist="Boards" Name="Roygbiv"/>
  </COLLECTION>
  <PLAYLISTS>
    <NODE Type="0" Name="ROOT" Count="2">
      <NODE Type="0" Name="Crates" Count="1">
        <NODE Type="1" Name="Vinyl" KeyType="0" Entries="2">
          <TRACK Key="1"/>
          <TRACK Key="2"/>
        </NODE>
      </NODE>
      <NODE Type="1" Name="Gigs" KeyType="0" Entries="1">
        <TRACK Key="3"/>
      </NODE>
    </NODE>
  </PLAYLISTS>
</DJ_PLAYLISTS>
"""


def test_parse_collection_tracks_and_nested_playlists(tmp_path):
    f = tmp_path / "collection.xml"
    f.write_text(COLLECTION_XML)
    tracks, playlists = parse_collection(f)
    assert set(tracks) == {"1", "2", "3"}
    assert tracks["1"] == RkTrack(
        track_id="1", location="file://localhost/m/a.flac",
        artist="Aphex Twin", name="Xtal", album="SAW",
        total_time_s=294, kind="FLAC File",
    )
    assert tracks["2"].album is None and tracks["2"].total_time_s is None
    assert playlists == {"Vinyl": ["1", "2"], "Gigs": ["3"]}


def test_list_playlists_returns_name_and_count(tmp_path):
    f = tmp_path / "collection.xml"
    f.write_text(COLLECTION_XML)
    assert list_playlists(f) == [("Vinyl", 2), ("Gigs", 1)]


def test_decode_strips_scheme_and_percent_decodes():
    assert decode_location(
        "file://localhost/Users/dj/My%20Track.flac"
    ) == Path("/Users/dj/My Track.flac")


def test_decode_applies_remap_prefix():
    out = decode_location(
        "file://localhost/Volumes/Old/x.flac",
        remap=[("/Volumes/Old", "/Volumes/New")],
    )
    assert out == Path("/Volumes/New/x.flac")


def test_decode_remap_first_match_wins():
    out = decode_location(
        "file://localhost/a/b.flac", remap=[("/a", "/X"), ("/a/b", "/Y")]
    )
    assert out == Path("/X/b.flac")


def test_decode_windows_drive_strips_leading_slash():
    assert decode_location(
        "file://localhost/C:/Music/x.mp3"
    ) == Path("C:/Music/x.mp3")
