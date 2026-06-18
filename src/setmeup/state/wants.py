from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from enum import Enum
from typing import Optional


class WantStatus(str, Enum):
    WANTED = "wanted"
    SEARCHING = "searching"
    DOWNLOADING = "downloading"
    DOWNLOADED = "downloaded"
    NO_MATCH = "no_match"
    FAILED = "failed"
    ALREADY_HAVE = "already_have"


@dataclass
class Want:
    id: Optional[int]
    source: str
    source_ref: Optional[str]
    artist: str
    title: str
    version: Optional[str]
    album: Optional[str]
    duration_ms: Optional[int]
    spotify_uri: Optional[str]
    dedupe_key: str
    status: str
    slskd_username: Optional[str] = None
    slskd_filename: Optional[str] = None
    downloaded_path: Optional[str] = None
    attempts: int = 0
    error: Optional[str] = None


_WANT_FIELDS = set(Want.__dataclass_fields__)
# Columns update_want may set (everything except the id primary key).
_UPDATABLE_COLUMNS = _WANT_FIELDS - {"id"}


def _row_to_want(row: sqlite3.Row) -> Want:
    return Want(**{key: row[key] for key in row.keys() if key in _WANT_FIELDS})


def add_want(
    conn: sqlite3.Connection,
    *,
    source: str,
    source_ref: Optional[str],
    artist: str,
    title: str,
    version: Optional[str],
    album: Optional[str],
    duration_ms: Optional[int],
    spotify_uri: Optional[str],
    dedupe_key: str,
    status: str,
) -> int:
    conn.execute(
        "INSERT OR IGNORE INTO wants "
        "(source, source_ref, artist, title, version, album, duration_ms, "
        " spotify_uri, dedupe_key, status) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (source, source_ref, artist, title, version, album, duration_ms,
         spotify_uri, dedupe_key, status),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM wants WHERE dedupe_key = ?", (dedupe_key,)
    ).fetchone()
    return int(row["id"])


def get_want_by_key(conn: sqlite3.Connection, dedupe_key: str) -> Optional[Want]:
    row = conn.execute(
        "SELECT * FROM wants WHERE dedupe_key = ?", (dedupe_key,)
    ).fetchone()
    return _row_to_want(row) if row else None


def get_wants_by_status(conn: sqlite3.Connection, status: str) -> list[Want]:
    rows = conn.execute(
        "SELECT * FROM wants WHERE status = ? ORDER BY id", (status,)
    ).fetchall()
    return [_row_to_want(row) for row in rows]


def update_want(conn: sqlite3.Connection, want_id: int, **fields) -> None:
    if not fields:
        return
    unknown = set(fields) - _UPDATABLE_COLUMNS
    if unknown:
        raise ValueError(f"Unknown want columns: {sorted(unknown)}")
    assignments = ", ".join(f"{column} = ?" for column in fields)
    values = list(fields.values()) + [want_id]
    conn.execute(
        f"UPDATE wants SET {assignments}, updated_at = datetime('now') WHERE id = ?",
        values,
    )
    conn.commit()


def count_wants_by_status(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM wants GROUP BY status"
    ).fetchall()
    return {row["status"]: int(row["n"]) for row in rows}
