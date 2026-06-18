from pathlib import Path

import pytest

from setmeup.audio.metadata import ResolvedMetadata
from setmeup.config import Config
from setmeup.state.db import connect, init_schema
from setmeup.state import repository as repo
from setmeup.state.models import TrackStatus
from setmeup import process as process_mod


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
        slskd_base_url="http://localhost:5030",
        slskd_api_key=None,
        spotify_client_id=None,
        spotify_client_secret=None,
        spotify_redirect_uri="http://127.0.0.1:8888/callback",
        search_timeout_seconds=10,
        download_timeout_seconds=300,
        search_concurrency=8,
        download_attempts=3,
        duration_tolerance_seconds=20,
    )


def test_process_resolves_and_dedupes(cfg, monkeypatch):
    cfg.complete_dir.mkdir(parents=True)
    good = cfg.complete_dir / "a.wav"
    dup = cfg.complete_dir / "b.flac"
    for path in (good, dup):
        path.write_bytes(b"fake-audio")

    # Same recording for both files; wav outranks flac.
    monkeypatch.setattr(
        process_mod,
        "fingerprint_file",
        lambda path: (180.0, "FP-" + Path(path).suffix),
    )
    monkeypatch.setattr(
        process_mod,
        "resolve_metadata",
        lambda path, fp, dur, key: ResolvedMetadata(
            "Daft Punk", "Around the World", "Extended Mix", "rec-1", "acoustid"
        ),
    )
    from setmeup.audio.quality import AudioInfo

    def fake_probe(path):
        ext = Path(path).suffix.lstrip(".")
        return AudioInfo(ext=ext, bitrate=1000, sample_rate=44100, duration=180.0)

    monkeypatch.setattr(process_mod, "probe_audio", fake_probe)

    conn = connect(cfg.db_path)
    init_schema(conn)
    process_mod.process_folder(conn, cfg)

    deduped = repo.get_tracks_by_status(conn, TrackStatus.DEDUPED.value)
    skipped = repo.get_tracks_by_status(conn, TrackStatus.SKIPPED_DUPLICATE.value)
    assert len(deduped) == 1
    assert deduped[0].source_path.endswith("a.wav")
    assert deduped[0].canonical_name == "Daft Punk - Around the World - Extended Mix"
    assert len(skipped) == 1


def test_unresolvable_track_is_failed(cfg, monkeypatch):
    cfg.complete_dir.mkdir(parents=True)
    (cfg.complete_dir / "x.wav").write_bytes(b"fake")

    monkeypatch.setattr(process_mod, "fingerprint_file", lambda path: (10.0, "FP"))
    monkeypatch.setattr(
        process_mod,
        "resolve_metadata",
        lambda path, fp, dur, key: ResolvedMetadata(None, None, None, None, "none"),
    )
    from setmeup.audio.quality import AudioInfo

    monkeypatch.setattr(
        process_mod,
        "probe_audio",
        lambda path: AudioInfo("wav", 1000, 44100, 10.0),
    )

    conn = connect(cfg.db_path)
    init_schema(conn)
    process_mod.process_folder(conn, cfg)

    failed = repo.get_tracks_by_status(conn, TrackStatus.FAILED.value)
    assert len(failed) == 1
    assert failed[0].error == "could not resolve artist/title"


def test_below_min_quality_is_failed(cfg, monkeypatch):
    cfg.complete_dir.mkdir(parents=True)
    (cfg.complete_dir / "low.mp3").write_bytes(b"fake")

    monkeypatch.setattr(process_mod, "fingerprint_file", lambda path: (180.0, "FP"))
    monkeypatch.setattr(
        process_mod,
        "resolve_metadata",
        lambda path, fp, dur, key: ResolvedMetadata("Artist", "Title", None, None, "filename"),
    )
    from setmeup.audio.quality import AudioInfo

    monkeypatch.setattr(
        process_mod,
        "probe_audio",
        lambda path: AudioInfo(ext="mp3", bitrate=128, sample_rate=44100, duration=180.0),
    )

    conn = connect(cfg.db_path)
    init_schema(conn)
    process_mod.process_folder(conn, cfg)

    failed = repo.get_tracks_by_status(conn, TrackStatus.FAILED.value)
    assert len(failed) == 1
    assert failed[0].error == "below minimum quality"


def test_discover_excludes_library_and_trash(tmp_path):
    complete = tmp_path / "Complete"
    library = complete / "Library"
    trash = complete / "Trash"
    library.mkdir(parents=True)
    trash.mkdir(parents=True)
    (complete / "keep.wav").write_bytes(b"x")
    (library / "organized.wav").write_bytes(b"x")
    (trash / "evicted.wav").write_bytes(b"x")

    found = process_mod.discover(complete, exclude_dirs=(library, trash))

    assert sorted(p.name for p in found) == ["keep.wav"]
