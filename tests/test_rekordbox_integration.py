import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path

from setmeup.acquire import fetch as fetch_mod
from setmeup.acquire.importer import import_entries
from setmeup.sources.rekordbox import RekordboxSource
from setmeup.state.db import connect, init_schema
from setmeup.state import wants as wants_repo
from setmeup.state.wants import WantStatus


def _loc(p):
    return "file://localhost" + urllib.parse.quote(str(p))


def _collection(tmp_path, tracks, playlists):
    root = ET.Element("DJ_PLAYLISTS", {"Version": "1.0.0"})
    coll = ET.SubElement(root, "COLLECTION")
    for t in tracks:
        ET.SubElement(coll, "TRACK", {
            "TrackID": t["id"], "Location": t["location"],
            "Artist": t.get("artist", ""), "Name": t.get("name", ""),
        })
    pls = ET.SubElement(root, "PLAYLISTS")
    rn = ET.SubElement(pls, "NODE", {"Type": "0", "Name": "ROOT"})
    for name, ids in playlists.items():
        n = ET.SubElement(rn, "NODE", {"Type": "1", "Name": name, "KeyType": "0"})
        for tid in ids:
            ET.SubElement(n, "TRACK", {"Key": tid})
    out = tmp_path / "collection.xml"
    ET.ElementTree(root).write(out, encoding="utf-8", xml_declaration=True)
    return out


class FakeClient:
    def __init__(self, complete_dir):
        self.complete_dir = Path(complete_dir)

    def search(self, text):
        return "sid"

    def wait_for_responses(self, sid, timeout):
        return [{"username": "bob", "hasFreeUploadSlot": True, "uploadSpeed": 9,
                 "queueLength": 0,
                 "files": [{"filename": "Aphex Twin - Xtal.flac",
                            "size": 10, "bitRate": 900, "length": 294}]}]

    def enqueue(self, username, files):
        self.complete_dir.mkdir(parents=True, exist_ok=True)
        (self.complete_dir / Path(files[0]["filename"]).name).write_bytes(b"audio")

    def transfer_state(self, username, filename):
        return "Completed, Succeeded"


def test_rekordbox_recover_missing_then_fetch(tmp_path, make_config):
    cfg = make_config()
    missing = tmp_path / "Xtal.flac"  # not created -> missing
    coll = _collection(
        tmp_path,
        tracks=[{"id": "1", "location": _loc(missing),
                 "artist": "Aphex Twin", "name": "Xtal"}],
        playlists={"Set": ["1"]},
    )

    conn = connect(cfg.db_path)
    init_schema(conn)

    source = RekordboxSource(coll, ["Set"])
    result = import_entries(conn, "rekordbox", str(coll), source.entries())
    assert result.imported == 1

    counts = fetch_mod.fetch(conn, cfg, FakeClient(cfg.complete_dir))

    assert counts.get("downloaded") == 1
    downloaded = wants_repo.get_wants_by_status(conn, WantStatus.DOWNLOADED.value)
    assert downloaded[0].artist == "Aphex Twin"
    assert (cfg.complete_dir / "Aphex Twin - Xtal.flac").exists()
