from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_path TEXT NOT NULL UNIQUE,
    status TEXT NOT NULL,
    artist TEXT,
    title TEXT,
    version TEXT,
    fingerprint TEXT,
    duration REAL,
    acoustid TEXT,
    dedupe_key TEXT,
    quality_score INTEGER,
    canonical_name TEXT,
    library_path TEXT,
    error TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE IF NOT EXISTS library_index (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    dedupe_key TEXT NOT NULL,
    library_path TEXT NOT NULL UNIQUE,
    quality_score INTEGER NOT NULL,
    artist TEXT,
    title TEXT,
    version TEXT
);

CREATE INDEX IF NOT EXISTS idx_library_key ON library_index(dedupe_key);
"""


def connect(db_path: Path) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    conn.commit()
