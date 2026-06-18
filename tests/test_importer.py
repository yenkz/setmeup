import pytest

from setmeup.acquire.importer import ImportResult, import_entries
from setmeup.sources.base import WantlistEntry
from setmeup.state.db import connect, init_schema
from setmeup.state import repository as repo
from setmeup.state import wants as wants_repo
from setmeup.state.wants import WantStatus


@pytest.fixture()
def conn(tmp_path):
    c = connect(tmp_path / "setmeup.db")
    init_schema(c)
    return c


def test_imports_new_wants(conn):
    entries = [
        WantlistEntry("Daft Punk", "Around the World (Extended Mix)"),
        WantlistEntry("Aphex Twin", "Xtal"),
    ]
    result = import_entries(conn, "wantlist", "wl.txt", entries)
    assert result == ImportResult(imported=2, already_have=0, duplicates=0)
    w = wants_repo.get_want_by_key(conn, "daft punk|around the world|extended mix")
    assert w.title == "Around the World" and w.version == "Extended Mix"
    assert w.status == WantStatus.WANTED.value


def test_skips_library_haves(conn):
    repo.add_library_entry(conn, "rec-1", "/lib/x.flac", 100, "Aphex Twin", "Xtal", None)
    result = import_entries(conn, "wantlist", "wl.txt", [WantlistEntry("Aphex Twin", "Xtal")])
    assert result == ImportResult(imported=0, already_have=1, duplicates=0)
    assert wants_repo.get_want_by_key(conn, "aphex twin|xtal|").status == WantStatus.ALREADY_HAVE.value


def test_duplicate_entries_counted_not_reinserted(conn):
    entries = [WantlistEntry("A", "T"), WantlistEntry("A", "T")]
    result = import_entries(conn, "wantlist", "wl.txt", entries)
    assert result == ImportResult(imported=1, already_have=0, duplicates=1)


def test_reimport_same_entry_counts_as_duplicate(conn):
    first = import_entries(conn, "wantlist", "wl.txt", [WantlistEntry("A", "T")])
    second = import_entries(conn, "wantlist", "wl.txt", [WantlistEntry("A", "T")])
    assert first == ImportResult(imported=1, already_have=0, duplicates=0)
    assert second == ImportResult(imported=0, already_have=0, duplicates=1)
