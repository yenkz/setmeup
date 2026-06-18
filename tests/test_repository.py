import pytest

from setmeup.state.db import connect, init_schema
from setmeup.state.models import TrackStatus
from setmeup.state import repository as repo


@pytest.fixture()
def conn(tmp_path):
    c = connect(tmp_path / "setmeup.db")
    init_schema(c)
    return c


def test_add_track_is_idempotent_on_path(conn):
    first = repo.add_track(conn, "/music/a.wav", TrackStatus.DOWNLOADED.value)
    second = repo.add_track(conn, "/music/a.wav", TrackStatus.DOWNLOADED.value)
    assert first == second


def test_update_and_fetch_by_status(conn):
    tid = repo.add_track(conn, "/music/a.wav", TrackStatus.DOWNLOADED.value)
    repo.update_track(
        conn,
        tid,
        status=TrackStatus.RESOLVED.value,
        artist="Daft Punk",
        title="Around the World",
        dedupe_key="rec-1",
        quality_score=42,
        canonical_name="Daft Punk - Around the World",
    )

    resolved = repo.get_tracks_by_status(conn, TrackStatus.RESOLVED.value)
    assert len(resolved) == 1
    assert resolved[0].artist == "Daft Punk"
    assert resolved[0].quality_score == 42


def test_count_by_status(conn):
    repo.add_track(conn, "/music/a.wav", TrackStatus.DOWNLOADED.value)
    repo.add_track(conn, "/music/b.wav", TrackStatus.DOWNLOADED.value)
    tid = repo.add_track(conn, "/music/c.wav", TrackStatus.DOWNLOADED.value)
    repo.update_track(conn, tid, status=TrackStatus.ORGANIZED.value)

    counts = repo.count_by_status(conn)
    assert counts == {"downloaded": 2, "organized": 1}


def test_update_track_rejects_unknown_column(conn):
    tid = repo.add_track(conn, "/music/a.wav", TrackStatus.DOWNLOADED.value)
    with pytest.raises(ValueError):
        repo.update_track(conn, tid, not_a_column="x")


def test_library_entry_roundtrip_and_eviction(conn):
    repo.add_library_entry(conn, "rec-1", "/lib/x.wav", 100, "A", "T", None)
    entry = repo.get_library_entry_by_key(conn, "rec-1")
    assert entry["library_path"] == "/lib/x.wav"
    assert entry["quality_score"] == 100

    assert repo.library_quality_by_key(conn) == {"rec-1": 100}

    repo.remove_library_entry(conn, "/lib/x.wav")
    assert repo.get_library_entry_by_key(conn, "rec-1") is None
