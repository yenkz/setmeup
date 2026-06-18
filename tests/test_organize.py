from pathlib import Path

import pytest

from setmeup.config import Config
from setmeup.state.db import connect, init_schema
from setmeup.state import repository as repo
from setmeup.state.models import TrackStatus
from setmeup import organize as organize_mod


@pytest.fixture()
def cfg(tmp_path):
    return Config(
        complete_dir=tmp_path / "Complete",
        library_dir=tmp_path / "Library",
        trash_dir=tmp_path / "Trash",
        db_path=tmp_path / "setmeup.db",
        acoustid_api_key=None,
        format_priority=["wav", "flac", "mp3"],
        min_mp3_bitrate=320,
        match_threshold=0.8,
    )


def _add_deduped(conn, source_path, *, key, score, name):
    tid = repo.add_track(conn, str(source_path), TrackStatus.DOWNLOADED.value)
    repo.update_track(
        conn,
        tid,
        status=TrackStatus.DEDUPED.value,
        artist="A",
        title="T",
        dedupe_key=key,
        quality_score=score,
        canonical_name=name,
    )
    return tid


def test_organize_copies_and_preserves_original(cfg):
    cfg.complete_dir.mkdir(parents=True)
    src = cfg.complete_dir / "a.wav"
    src.write_bytes(b"audio-bytes")

    conn = connect(cfg.db_path)
    init_schema(conn)
    _add_deduped(conn, src, key="rec-1", score=100, name="A - T")

    organize_mod.organize(conn, cfg)

    target = cfg.library_dir / "A - T.wav"
    assert target.exists()
    assert target.read_bytes() == b"audio-bytes"
    assert src.exists()  # copy-not-move: original preserved
    assert repo.get_library_entry_by_key(conn, "rec-1")["library_path"] == str(target)
    organized = repo.get_tracks_by_status(conn, TrackStatus.ORGANIZED.value)
    assert organized[0].library_path == str(target)


def test_better_copy_evicts_existing_to_trash(cfg):
    cfg.complete_dir.mkdir(parents=True)
    cfg.library_dir.mkdir(parents=True)
    old = cfg.library_dir / "A - T.flac"
    old.write_bytes(b"old")
    new_src = cfg.complete_dir / "a.wav"
    new_src.write_bytes(b"new")

    conn = connect(cfg.db_path)
    init_schema(conn)
    repo.add_library_entry(conn, "rec-1", str(old), 50, "A", "T", None)
    _add_deduped(conn, new_src, key="rec-1", score=100, name="A - T")

    organize_mod.organize(conn, cfg)

    assert not old.exists()
    assert (cfg.trash_dir / "A - T.flac").exists()
    assert (cfg.library_dir / "A - T.wav").exists()
    assert repo.get_library_entry_by_key(conn, "rec-1")["library_path"].endswith("A - T.wav")
