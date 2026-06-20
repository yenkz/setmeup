import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from setmeup.sources.rekordbox import (
    RekordboxSource,
    RkTrack,
    decode_location,
    list_playlists,
    parse_collection,
)

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


def _loc(p) -> str:
    return "file://localhost" + urllib.parse.quote(str(p))


def _build(tmp_path, tracks, playlists):
    """tracks: list of dicts (id, location, artist, name, album?, total?, kind?).
    playlists: dict name -> list of track-id strings."""
    root = ET.Element("DJ_PLAYLISTS", {"Version": "1.0.0"})
    coll = ET.SubElement(root, "COLLECTION", {"Entries": str(len(tracks))})
    for t in tracks:
        attrs = {"TrackID": t["id"], "Location": t["location"],
                 "Artist": t.get("artist", ""), "Name": t.get("name", "")}
        if t.get("album"):
            attrs["Album"] = t["album"]
        if t.get("kind"):
            attrs["Kind"] = t["kind"]
        if t.get("total") is not None:
            attrs["TotalTime"] = str(t["total"])
        ET.SubElement(coll, "TRACK", attrs)
    pls = ET.SubElement(root, "PLAYLISTS")
    rootnode = ET.SubElement(pls, "NODE", {"Type": "0", "Name": "ROOT"})
    for name, ids in playlists.items():
        node = ET.SubElement(rootnode, "NODE",
                             {"Type": "1", "Name": name, "KeyType": "0"})
        for tid in ids:
            ET.SubElement(node, "TRACK", {"Key": tid})
    out = tmp_path / "collection.xml"
    ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)
    return out


def test_scan_queues_missing_audio_only(tmp_path):
    present = tmp_path / "have.flac"
    present.write_bytes(b"x")
    missing_audio = tmp_path / "gone.flac"       # not created
    missing_video = tmp_path / "clip.mp4"        # not created
    coll = _build(
        tmp_path,
        tracks=[
            {"id": "1", "location": _loc(present), "artist": "A", "name": "Have"},
            {"id": "2", "location": _loc(missing_audio), "artist": "B",
             "name": "Gone", "total": 294},
            {"id": "3", "location": _loc(missing_video), "artist": "C", "name": "Clip"},
        ],
        playlists={"Set": ["1", "2", "3"]},
    )
    scan = RekordboxSource(coll, ["Set"]).scan
    assert (scan.present, scan.missing, scan.skipped_non_audio) == (1, 1, 1)
    entries = list(RekordboxSource(coll, ["Set"]).entries())
    assert len(entries) == 1
    assert entries[0].artist == "B" and entries[0].title == "Gone"
    assert entries[0].duration_ms == 294000


def test_remap_makes_missing_file_present(tmp_path):
    real = tmp_path / "real.flac"
    real.write_bytes(b"x")
    coll = _build(
        tmp_path,
        tracks=[{"id": "1", "location": "file://localhost/OLD/real.flac",
                 "artist": "A", "name": "T"}],
        playlists={"Set": ["1"]},
    )
    assert RekordboxSource(coll, ["Set"]).scan.missing == 1
    remapped = RekordboxSource(coll, ["Set"], remap=[("/OLD", str(tmp_path))]).scan
    assert remapped.present == 1 and remapped.missing == 0


def test_playlist_union_dedups_track_ids(tmp_path):
    f1 = tmp_path / "a.flac"
    f1.write_bytes(b"x")
    coll = _build(
        tmp_path,
        tracks=[{"id": "1", "location": _loc(f1), "artist": "A", "name": "T"}],
        playlists={"P1": ["1"], "P2": ["1"]},
    )
    scan = RekordboxSource(coll, ["P1", "P2"]).scan
    assert scan.total == 1 and scan.present == 1


def test_unknown_playlist_raises(tmp_path):
    coll = _build(tmp_path, tracks=[], playlists={"Real": []})
    with pytest.raises(ValueError):
        RekordboxSource(coll, ["Nope"])


def test_guard_trips_when_mostly_missing(tmp_path):
    present = tmp_path / "p.flac"
    present.write_bytes(b"x")
    tracks = [{"id": "0", "location": _loc(present), "artist": "A", "name": "P"}]
    ids = ["0"]
    for i in range(1, 20):  # 19 missing audio
        tracks.append({"id": str(i),
                       "location": f"file://localhost/gone/{i}.flac",
                       "artist": "A", "name": f"M{i}"})
        ids.append(str(i))
    coll = _build(tmp_path, tracks=tracks, playlists={"Set": ids})
    scan = RekordboxSource(coll, ["Set"]).scan
    assert (scan.present, scan.missing) == (1, 19)
    assert scan.guard_tripped is True


def test_guard_not_tripped_when_mostly_present(tmp_path):
    tracks, ids = [], []
    for i in range(10):
        f = tmp_path / f"p{i}.flac"
        f.write_bytes(b"x")
        tracks.append({"id": str(i), "location": _loc(f),
                       "artist": "A", "name": f"P{i}"})
        ids.append(str(i))
    tracks.append({"id": "x", "location": "file://localhost/gone/x.flac",
                   "artist": "A", "name": "X"})
    ids.append("x")
    coll = _build(tmp_path, tracks=tracks, playlists={"Set": ids})
    assert RekordboxSource(coll, ["Set"]).scan.guard_tripped is False
