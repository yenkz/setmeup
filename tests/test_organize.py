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


def test_existing_equal_or_better_is_skipped(cfg):
    cfg.complete_dir.mkdir(parents=True)
    cfg.library_dir.mkdir(parents=True)
    old = cfg.library_dir / "A - T.wav"
    old.write_bytes(b"old-better")
    new_src = cfg.complete_dir / "a.flac"
    new_src.write_bytes(b"new-worse")

    conn = connect(cfg.db_path)
    init_schema(conn)
    repo.add_library_entry(conn, "rec-1", str(old), 100, "A", "T", None)
    _add_deduped(conn, new_src, key="rec-1", score=50, name="A - T")

    organize_mod.organize(conn, cfg)

    assert old.read_bytes() == b"old-better"  # existing better file untouched
    assert new_src.exists()  # original preserved
    assert not list(cfg.trash_dir.iterdir()) if cfg.trash_dir.exists() else True
    skipped = repo.get_tracks_by_status(conn, TrackStatus.SKIPPED_DUPLICATE.value)
    assert len(skipped) == 1
    assert repo.get_library_entry_by_key(conn, "rec-1")["library_path"] == str(old)


def test_checksum_mismatch_marks_failed_and_removes_partial(cfg, monkeypatch):
    cfg.complete_dir.mkdir(parents=True)
    src = cfg.complete_dir / "a.wav"
    src.write_bytes(b"good-bytes")

    conn = connect(cfg.db_path)
    init_schema(conn)
    _add_deduped(conn, src, key="rec-1", score=100, name="A - T")

    def corrupt_copy(source, dest):
        Path(dest).write_bytes(b"corrupted-different-bytes")

    monkeypatch.setattr(organize_mod.shutil, "copy2", corrupt_copy)

    organize_mod.organize(conn, cfg)

    failed = repo.get_tracks_by_status(conn, TrackStatus.FAILED.value)
    assert len(failed) == 1
    assert failed[0].error == "checksum mismatch after copy"
    assert not (cfg.library_dir / "A - T.wav").exists()  # partial target removed
    assert src.exists()  # original preserved


def test_distinct_tracks_with_same_name_get_discriminator(cfg):
    cfg.complete_dir.mkdir(parents=True)
    src1 = cfg.complete_dir / "a.wav"
    src2 = cfg.complete_dir / "b.wav"
    src1.write_bytes(b"one")
    src2.write_bytes(b"two")

    conn = connect(cfg.db_path)
    init_schema(conn)
    _add_deduped(conn, src1, key="rec-1", score=100, name="A - T")
    _add_deduped(conn, src2, key="rec-2", score=100, name="A - T")

    organize_mod.organize(conn, cfg)

    names = sorted(p.name for p in cfg.library_dir.iterdir())
    assert names == ["A - T (2).wav", "A - T.wav"]
    organized = repo.get_tracks_by_status(conn, TrackStatus.ORGANIZED.value)
    assert len(organized) == 2
