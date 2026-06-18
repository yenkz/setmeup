from __future__ import annotations

import sqlite3
from typing import Optional

from setmeup.state.models import Track

_TRACK_FIELDS = set(Track.__dataclass_fields__)


def _row_to_track(row: sqlite3.Row) -> Track:
    return Track(**{key: row[key] for key in row.keys() if key in _TRACK_FIELDS})


def add_track(conn: sqlite3.Connection, source_path: str, status: str) -> int:
    conn.execute(
        "INSERT OR IGNORE INTO tracks (source_path, status) VALUES (?, ?)",
        (source_path, status),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM tracks WHERE source_path = ?", (source_path,)
    ).fetchone()
    return int(row["id"])


def update_track(conn: sqlite3.Connection, track_id: int, **fields) -> None:
    if not fields:
        return
    assignments = ", ".join(f"{column} = ?" for column in fields)
    values = list(fields.values()) + [track_id]
    conn.execute(
        f"UPDATE tracks SET {assignments}, updated_at = datetime('now') WHERE id = ?",
        values,
    )
    conn.commit()


def get_track_by_path(conn: sqlite3.Connection, source_path: str) -> Optional[Track]:
    row = conn.execute(
        "SELECT * FROM tracks WHERE source_path = ?", (source_path,)
    ).fetchone()
    return _row_to_track(row) if row else None


def get_tracks_by_status(conn: sqlite3.Connection, status: str) -> list[Track]:
    rows = conn.execute(
        "SELECT * FROM tracks WHERE status = ? ORDER BY id", (status,)
    ).fetchall()
    return [_row_to_track(row) for row in rows]


def count_by_status(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT status, COUNT(*) AS n FROM tracks GROUP BY status"
    ).fetchall()
    return {row["status"]: int(row["n"]) for row in rows}


def add_library_entry(
    conn: sqlite3.Connection,
    dedupe_key: str,
    library_path: str,
    quality_score: int,
    artist: Optional[str],
    title: Optional[str],
    version: Optional[str],
) -> None:
    conn.execute(
        "INSERT OR REPLACE INTO library_index "
        "(dedupe_key, library_path, quality_score, artist, title, version) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (dedupe_key, library_path, quality_score, artist, title, version),
    )
    conn.commit()


def get_library_entry_by_key(
    conn: sqlite3.Connection, dedupe_key: str
) -> Optional[sqlite3.Row]:
    return conn.execute(
        "SELECT * FROM library_index WHERE dedupe_key = ? "
        "ORDER BY quality_score DESC LIMIT 1",
        (dedupe_key,),
    ).fetchone()


def remove_library_entry(conn: sqlite3.Connection, library_path: str) -> None:
    conn.execute(
        "DELETE FROM library_index WHERE library_path = ?", (library_path,)
    )
    conn.commit()


def library_quality_by_key(conn: sqlite3.Connection) -> dict[str, int]:
    rows = conn.execute(
        "SELECT dedupe_key, MAX(quality_score) AS q FROM library_index "
        "GROUP BY dedupe_key"
    ).fetchall()
    return {row["dedupe_key"]: int(row["q"]) for row in rows}
