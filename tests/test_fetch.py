from pathlib import Path

import pytest

from setmeup.acquire import fetch as fetch_mod
from setmeup.state.db import connect, init_schema
from setmeup.state import wants as wants_repo
from setmeup.state.wants import WantStatus


@pytest.fixture()
def conn(tmp_path):
    c = connect(tmp_path / "setmeup.db")
    init_schema(c)
    return c


def _want(conn, key="a|t|", artist="A", title="T"):
    return wants_repo.add_want(
        conn, source="wantlist", source_ref="wl", artist=artist, title=title,
        version=None, album=None, duration_ms=None, spotify_uri=None,
        dedupe_key=key, status=WantStatus.WANTED.value,
    )


class FakeClient:
    """Deterministic slskd stand-in. files: response file dicts; behavior controls transfer."""

    def __init__(self, files, complete_dir, transfer="Completed, Succeeded"):
        self.files = files
        self.complete_dir = Path(complete_dir)
        self.transfer = transfer
        self.enqueued = []

    def search(self, text):
        return "sid"

    def wait_for_responses(self, sid, timeout):
        if not self.files:
            return []
        return [{"username": "bob", "hasFreeUploadSlot": True, "uploadSpeed": 9,
                 "queueLength": 0, "files": self.files}]

    def enqueue(self, username, files):
        self.enqueued.append((username, files))
        if self.transfer.startswith("Completed, Succeeded"):
            self.complete_dir.mkdir(parents=True, exist_ok=True)
            (self.complete_dir / Path(files[0]["filename"]).name).write_bytes(b"audio")

    def transfer_state(self, username, filename):
        return self.transfer


def test_successful_download_marks_downloaded(conn, make_config):
    cfg = make_config(search_concurrency=2)
    _want(conn)
    client = FakeClient(
        files=[{"filename": "A - T.flac", "size": 10, "bitRate": 900, "length": 200}],
        complete_dir=cfg.complete_dir,
    )
    counts = fetch_mod.fetch(conn, cfg, client)
    assert counts.get("downloaded") == 1
    assert (cfg.complete_dir / "A - T.flac").exists()
    assert client.enqueued  # really attempted


def test_no_results_marks_no_match(conn, make_config):
    cfg = make_config()
    _want(conn)
    client = FakeClient(files=[], complete_dir=cfg.complete_dir)
    counts = fetch_mod.fetch(conn, cfg, client)
    assert counts.get("no_match") == 1


def test_transfer_error_marks_failed(conn, make_config):
    cfg = make_config(download_attempts=1)
    _want(conn)
    client = FakeClient(
        files=[{"filename": "A - T.flac", "size": 10, "bitRate": 900, "length": 200}],
        complete_dir=cfg.complete_dir, transfer="Completed, Errored",
    )
    counts = fetch_mod.fetch(conn, cfg, client)
    assert counts.get("failed") == 1


def test_search_exception_marks_failed(conn, make_config):
    cfg = make_config()
    _want(conn)

    class BoomClient(FakeClient):
        def search(self, text):
            raise RuntimeError("slskd unreachable")

    client = BoomClient(files=[], complete_dir=cfg.complete_dir)
    counts = fetch_mod.fetch(conn, cfg, client)

    assert counts.get("failed") == 1


def test_downloaded_path_is_full_path_under_complete(conn, make_config):
    cfg = make_config()
    _want(conn)
    client = FakeClient(
        files=[{"filename": "A - T.flac", "size": 10, "bitRate": 900, "length": 200}],
        complete_dir=cfg.complete_dir,
    )
    fetch_mod.fetch(conn, cfg, client)
    done = wants_repo.get_wants_by_status(conn, WantStatus.DOWNLOADED.value)
    assert done[0].downloaded_path == str(cfg.complete_dir / "A - T.flac")
