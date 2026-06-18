import shutil

import pytest

from setmeup.audio.metadata import ResolvedMetadata
from setmeup.config import Config
from setmeup.state.db import connect, init_schema
from setmeup.state import repository as repo
from setmeup.state.models import TrackStatus
from setmeup import organize as organize_mod
from setmeup import process as process_mod


@pytest.mark.skipif(
    shutil.which("ffmpeg") is None or shutil.which("fpcalc") is None,
    reason="ffmpeg/fpcalc required",
)
def test_process_then_organize_end_to_end(tmp_path, make_audio, monkeypatch):
    complete = tmp_path / "Complete"
    complete.mkdir()
    # A lossless and a 320k mp3 of the same tone => same recording, wav wins.
    wav = make_audio("tone.wav", seconds=4.0)
    mp3 = make_audio("tone.mp3", seconds=4.0, extra=["-b:a", "320k"])
    shutil.move(str(wav), complete / "tone.wav")
    shutil.move(str(mp3), complete / "tone.mp3")

    cfg = Config(
        complete_dir=complete,
        library_dir=tmp_path / "Library",
        trash_dir=tmp_path / "Trash",
        db_path=tmp_path / "setmeup.db",
        acoustid_api_key=None,
        format_priority=["wav", "aiff", "aif", "flac", "mp3"],
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

    # Force both files to resolve to the same recording (offline, no AcoustID key).
    monkeypatch.setattr(
        process_mod,
        "resolve_metadata",
        lambda path, fp, dur, key: ResolvedMetadata(
            "Daft Punk", "Around the World", None, "rec-shared", "acoustid"
        ),
    )

    conn = connect(cfg.db_path)
    init_schema(conn)
    process_mod.process_folder(conn, cfg)
    organize_mod.organize(conn, cfg)

    # Exactly one promoted, and it is the wav.
    library_files = sorted(p.name for p in cfg.library_dir.iterdir())
    assert library_files == ["Daft Punk - Around the World.wav"]

    # Copy-not-move: both originals still in Complete.
    assert (complete / "tone.wav").exists()
    assert (complete / "tone.mp3").exists()

    # Trash is empty (no eviction on a fresh library).
    assert not any(cfg.trash_dir.iterdir()) if cfg.trash_dir.exists() else True

    organized = repo.get_tracks_by_status(conn, TrackStatus.ORGANIZED.value)
    skipped = repo.get_tracks_by_status(conn, TrackStatus.SKIPPED_DUPLICATE.value)
    assert len(organized) == 1
    assert len(skipped) == 1
