import pytest

from setmeup.state.db import connect, init_schema
from setmeup.state import wants as wants_repo
from setmeup.state import repository as repo
from setmeup.state.wants import WantStatus


@pytest.fixture()
def conn(tmp_path):
    c = connect(tmp_path / "setmeup.db")
    init_schema(c)
    return c


def _add(conn, key, **over):
    fields = dict(
        source="wantlist", source_ref="wl.txt", artist="A", title="T",
        version=None, album=None, duration_ms=None, spotify_uri=None,
        dedupe_key=key, status=WantStatus.WANTED.value,
    )
    fields.update(over)
    return wants_repo.add_want(conn, **fields)


def test_add_is_idempotent_on_dedupe_key(conn):
    first = _add(conn, "a|t|")
    second = _add(conn, "a|t|")
    assert first == second
    assert wants_repo.get_want_by_key(conn, "a|t|").artist == "A"


def test_update_and_status_queries(conn):
    wid = _add(conn, "a|t|")
    wants_repo.update_want(conn, wid, status=WantStatus.DOWNLOADED.value,
                           downloaded_path="/x/a.flac")
    assert wants_repo.get_wants_by_status(conn, WantStatus.WANTED.value) == []
    done = wants_repo.get_wants_by_status(conn, WantStatus.DOWNLOADED.value)
    assert done[0].downloaded_path == "/x/a.flac"


def test_update_rejects_unknown_column(conn):
    wid = _add(conn, "a|t|")
    with pytest.raises(ValueError):
        wants_repo.update_want(conn, wid, bogus="x")


def test_count_by_status(conn):
    _add(conn, "a|t|")
    wid = _add(conn, "b|t|")
    wants_repo.update_want(conn, wid, status=WantStatus.NO_MATCH.value)
    assert wants_repo.count_wants_by_status(conn) == {"wanted": 1, "no_match": 1}


def test_all_library_entries(conn):
    repo.add_library_entry(conn, "rec-1", "/lib/x.wav", 100, "Daft Punk", "Around the World", "Extended Mix")
    rows = repo.all_library_entries(conn)
    assert (rows[0]["artist"], rows[0]["title"], rows[0]["version"]) == (
        "Daft Punk", "Around the World", "Extended Mix",
    )
