from pathlib import Path

from setmeup.acquire import fetch as fetch_mod
from setmeup.acquire.importer import import_entries
from setmeup.sources.csv_source import CsvSource
from setmeup.state.db import connect, init_schema
from setmeup.state import wants as wants_repo
from setmeup.state.wants import WantStatus

HEADER = (
    "Track URI,Track Name,Album Name,Artist Name(s),Release Date,Duration (ms),"
    "Popularity,Explicit,Added By,Added At,Genres,Record Label\n"
)


class FakeClient:
    def __init__(self, complete_dir):
        self.complete_dir = Path(complete_dir)

    def search(self, text):
        return "sid"

    def wait_for_responses(self, sid, timeout):
        return [{"username": "bob", "hasFreeUploadSlot": True, "uploadSpeed": 9,
                 "queueLength": 0,
                 "files": [{"filename": "Tornado Wallace - Asahi Ga Yondeiru.flac",
                            "size": 10, "bitRate": 900, "length": 433}]}]

    def enqueue(self, username, files):
        self.complete_dir.mkdir(parents=True, exist_ok=True)
        (self.complete_dir / Path(files[0]["filename"]).name).write_bytes(b"audio")

    def transfer_state(self, username, filename):
        return "Completed, Succeeded"


def test_import_csv_then_fetch_lands_file(tmp_path, make_config):
    cfg = make_config()
    csv_file = tmp_path / "Vinyl.csv"
    csv_file.write_text(
        HEADER
        + 'spotify:track:6nk,"Asahi Ga Yondeiru","Asahi Ga Yondeiru",'
          '"Tornado Wallace;Courtney Bailey",2026-01-30,433510,21,false,'
          'me,now,"","Running Back"\n'
    )

    conn = connect(cfg.db_path)
    init_schema(conn)

    result = import_entries(conn, "csv", str(csv_file), CsvSource(csv_file).entries())
    assert result.imported == 1

    counts = fetch_mod.fetch(conn, cfg, FakeClient(cfg.complete_dir))

    assert counts.get("downloaded") == 1
    downloaded = wants_repo.get_wants_by_status(conn, WantStatus.DOWNLOADED.value)
    assert downloaded[0].artist == "Tornado Wallace"
    assert (cfg.complete_dir / "Tornado Wallace - Asahi Ga Yondeiru.flac").exists()
