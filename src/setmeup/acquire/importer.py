from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from typing import Iterable

from setmeup.audio.version import extract_version
from setmeup.matching import normalize_key
from setmeup.sources.base import WantlistEntry
from setmeup.state import repository as repo
from setmeup.state import wants as wants_repo
from setmeup.state.wants import WantStatus


@dataclass
class ImportResult:
    imported: int
    already_have: int
    duplicates: int


def _library_keys(conn: sqlite3.Connection) -> set[str]:
    keys = set()
    for row in repo.all_library_entries(conn):
        keys.add(normalize_key(row["artist"] or "", row["title"] or "", row["version"]))
    return keys


def import_entries(
    conn: sqlite3.Connection,
    source_name: str,
    source_ref: str | None,
    entries: Iterable[WantlistEntry],
) -> ImportResult:
    library_keys = _library_keys(conn)
    imported = already = duplicates = 0

    for entry in entries:
        clean_title, version = extract_version(entry.title)
        key = normalize_key(entry.artist, clean_title, version)

        if wants_repo.get_want_by_key(conn, key) is not None:
            duplicates += 1
            continue

        if key in library_keys:
            status = WantStatus.ALREADY_HAVE.value
            already += 1
        else:
            status = WantStatus.WANTED.value
            imported += 1

        wants_repo.add_want(
            conn,
            source=source_name,
            source_ref=source_ref,
            artist=entry.artist,
            title=clean_title,
            version=version,
            album=entry.album,
            duration_ms=entry.duration_ms,
            spotify_uri=entry.spotify_uri,
            dedupe_key=key,
            status=status,
        )

    return ImportResult(imported=imported, already_have=already, duplicates=duplicates)
