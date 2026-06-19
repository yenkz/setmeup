import urllib.parse
import xml.etree.ElementTree as ET

from typer.testing import CliRunner

from setmeup.cli import app

runner = CliRunner()


def test_init_writes_config(tmp_path):
    target = tmp_path / "setmeup.toml"
    result = runner.invoke(app, ["init", "--path", str(target)])
    assert result.exit_code == 0
    assert target.exists()
    assert "[paths]" in target.read_text()


def test_init_refuses_overwrite(tmp_path):
    target = tmp_path / "setmeup.toml"
    target.write_text("existing")
    result = runner.invoke(app, ["init", "--path", str(target)])
    assert result.exit_code == 1


def test_status_runs_on_fresh_db(tmp_path):
    config = tmp_path / "setmeup.toml"
    config.write_text(
        '[paths]\n'
        f'complete = "{tmp_path}/Complete"\n'
        f'library = "{tmp_path}/Library"\n'
        f'trash = "{tmp_path}/Trash"\n'
        f'db = "{tmp_path}/setmeup.db"\n'
    )
    result = runner.invoke(app, ["status", "--config", str(config)])
    assert result.exit_code == 0
    assert "Status" in result.stdout


def _write_config(tmp_path):
    config = tmp_path / "setmeup.toml"
    config.write_text(
        '[paths]\n'
        f'complete = "{tmp_path}/Complete"\n'
        f'library = "{tmp_path}/Library"\n'
        f'trash = "{tmp_path}/Trash"\n'
        f'db = "{tmp_path}/setmeup.db"\n'
    )
    return config


def test_fetch_with_no_wants_runs(tmp_path):
    config = _write_config(tmp_path)
    result = runner.invoke(app, ["fetch", "--config", str(config)])
    assert result.exit_code == 0
    assert "fetch" in result.stdout.lower()


def test_import_wantlist_then_wants(tmp_path):
    config = _write_config(tmp_path)
    wl = tmp_path / "wl.txt"
    wl.write_text("Daft Punk - Around the World\nAphex Twin - Xtal\n")

    result = runner.invoke(app, ["import", "--config", str(config), "--wantlist", str(wl)])
    assert result.exit_code == 0
    assert "imported" in result.stdout.lower()

    status = runner.invoke(app, ["wants", "--config", str(config)])
    assert status.exit_code == 0
    assert "wanted" in status.stdout


def _rkb_loc(p):
    return "file://localhost" + urllib.parse.quote(str(p))


def _write_collection(tmp_path, tracks, playlists):
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


def test_import_rekordbox_queues_missing(tmp_path):
    config = _write_config(tmp_path)
    present = tmp_path / "have.flac"
    present.write_bytes(b"x")
    missing = tmp_path / "gone.flac"  # not created
    coll = _write_collection(
        tmp_path,
        tracks=[
            {"id": "1", "location": _rkb_loc(present), "artist": "A", "name": "Have"},
            {"id": "2", "location": _rkb_loc(missing), "artist": "B", "name": "Gone"},
        ],
        playlists={"Set": ["1", "2"]},
    )
    result = runner.invoke(app, ["import", "--config", str(config),
                                 "--rekordbox", str(coll), "--playlist", "Set"])
    assert result.exit_code == 0
    assert "missing 1" in result.stdout
    assert "imported 1" in result.stdout


def test_import_rekordbox_requires_playlist(tmp_path):
    config = _write_config(tmp_path)
    coll = _write_collection(tmp_path, tracks=[], playlists={"Set": []})
    result = runner.invoke(app, ["import", "--config", str(config),
                                 "--rekordbox", str(coll)])
    assert result.exit_code == 2


def test_import_rekordbox_guard_aborts_without_force(tmp_path):
    config = _write_config(tmp_path)
    tracks = [{"id": str(i), "location": f"file://localhost/gone/{i}.flac",
               "artist": "A", "name": f"M{i}"} for i in range(10)]
    coll = _write_collection(tmp_path, tracks=tracks,
                             playlists={"Set": [str(i) for i in range(10)]})
    aborted = runner.invoke(app, ["import", "--config", str(config),
                                  "--rekordbox", str(coll), "--playlist", "Set"])
    assert aborted.exit_code == 2
    assert "missing" in aborted.stdout.lower()
    forced = runner.invoke(app, ["import", "--config", str(config),
                                 "--rekordbox", str(coll), "--playlist", "Set",
                                 "--force"])
    assert forced.exit_code == 0
    assert "imported 10" in forced.stdout
