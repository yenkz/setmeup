# setmeup — Foundation + Local Processing/Organize Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working `setmeup` CLI that scans a folder of downloaded audio files, fingerprints each one, resolves canonical metadata (AcoustID → tags → filename), extracts the mix/version, deduplicates by keeping the highest-quality copy, and **copies** the winners into a flat `Library/` folder with canonical `Artist - Track - Version` filenames — leaving the originals untouched.

**Architecture:** A staged pipeline (`process` then `organize`) backed by a SQLite state store. `process` discovers files, fingerprints, resolves metadata, scores quality, and runs keep-best dedupe. `organize` copies dedupe winners into the Library (copy → checksum-verify) and evicts inferior previously-promoted Library files to a recoverable `Trash/`. Originals in the source/Complete folder are read-only and preserved. This plan covers spec phases 1–2 only; slskd acquisition (`fetch`), `run`/`status`/`retry` chaining, and Spotify/YouTube sources are follow-on plans.

**Tech Stack:** Python 3.10, `uv` (env + deps), `pytest` (TDD), `Typer` + `Rich` (CLI), `pyacoustid`/`fpcalc` (Chromaprint fingerprint + AcoustID lookup), `mutagen` (tag/format probing), `sqlite3` (stdlib state store), `ffmpeg` (decoding; used to synthesize audio fixtures in tests).

This plan assumes the spec at `docs/superpowers/specs/2026-06-17-setmeup-dj-pipeline-design.md`.

---

## File Structure

Created in this plan (src layout under `src/setmeup/`):

| File | Responsibility |
|---|---|
| `pyproject.toml` | Project metadata, dependencies, `setmeup` script entry, pytest config |
| `src/setmeup/__init__.py` | Package marker / version |
| `src/setmeup/config.py` | `Config` dataclass + TOML/`.env` loader + default config template |
| `src/setmeup/state/__init__.py` | State subpackage marker |
| `src/setmeup/state/db.py` | SQLite connection + schema (`tracks`, `library_index`) |
| `src/setmeup/state/models.py` | `TrackStatus` enum + `Track` dataclass |
| `src/setmeup/state/repository.py` | All DB reads/writes (sole owner of SQL) |
| `src/setmeup/audio/__init__.py` | Audio subpackage marker |
| `src/setmeup/audio/version.py` | `extract_version(title)` — split mix/version off the title |
| `src/setmeup/audio/filename.py` | `parse_filename(stem)` — `Artist - Title` heuristic |
| `src/setmeup/audio/quality.py` | `probe_audio(path)` (mutagen) + pure `score_audio(info, …)` |
| `src/setmeup/audio/fingerprint.py` | `fingerprint_file(path)` — Chromaprint via `pyacoustid` |
| `src/setmeup/audio/metadata.py` | `resolve_metadata(...)` — AcoustID → tags → filename + version |
| `src/setmeup/naming.py` | `sanitize` + `build_canonical_name` |
| `src/setmeup/dedupe.py` | Pure keep-best `resolve_duplicates(...)` |
| `src/setmeup/process.py` | `process_folder(...)` orchestration |
| `src/setmeup/organize.py` | `organize(...)` orchestration (copy/verify/evict) |
| `src/setmeup/cli.py` | Typer app: `init`, `process`, `organize`, `status` |
| `tests/...` | Mirror of the above |

---

## Task 1: Project scaffold

**Files:**
- Create: `pyproject.toml`
- Create: `src/setmeup/__init__.py`
- Create: `tests/test_smoke.py`
- Create: `.gitignore`

- [ ] **Step 1: Write the failing test**

`tests/test_smoke.py`:
```python
def test_package_imports():
    import setmeup

    assert setmeup.__version__ == "0.1.0"
```

- [ ] **Step 2: Create `pyproject.toml`**

```toml
[project]
name = "setmeup"
version = "0.1.0"
description = "DJ music acquisition and library pipeline"
requires-python = ">=3.10"
dependencies = [
    "typer>=0.12",
    "rich>=13.7",
    "mutagen>=1.47",
    "pyacoustid>=1.3",
    "requests>=2.31",
    "python-dotenv>=1.0",
    "tomli>=2.0; python_version < '3.11'",
]

[project.scripts]
setmeup = "setmeup.cli:app"

[dependency-groups]
dev = ["pytest>=8.0"]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.hatch.build.targets.wheel]
packages = ["src/setmeup"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

- [ ] **Step 3: Create `src/setmeup/__init__.py`**

```python
__version__ = "0.1.0"
```

- [ ] **Step 4: Create `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
.venv/
.pytest_cache/
*.db
.env
dist/
build/
*.egg-info/
```

- [ ] **Step 5: Sync the environment**

Run: `uv sync --group dev`
Expected: creates `.venv`, installs deps, installs `setmeup` editable. Ends with a summary like `Installed N packages`.

- [ ] **Step 6: Run the test**

Run: `uv run pytest tests/test_smoke.py -v`
Expected: PASS (`test_package_imports`).

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml src/setmeup/__init__.py tests/test_smoke.py .gitignore
git commit -m "chore: scaffold setmeup package with uv + pytest"
```

---

## Task 2: Config loader

**Files:**
- Create: `src/setmeup/config.py`
- Create: `tests/test_config.py`

- [ ] **Step 1: Write the failing test**

`tests/test_config.py`:
```python
from pathlib import Path

from setmeup.config import Config, DEFAULT_CONFIG_TOML


def test_from_toml_parses_paths_and_quality(tmp_path, monkeypatch):
    monkeypatch.setenv("ACOUSTID_API_KEY", "secret-key")
    cfg_file = tmp_path / "setmeup.toml"
    cfg_file.write_text(
        '[paths]\n'
        f'complete = "{tmp_path}/Complete"\n'
        f'library = "{tmp_path}/Library"\n'
        f'trash = "{tmp_path}/Trash"\n'
        f'db = "{tmp_path}/setmeup.db"\n'
        '[quality]\n'
        'format_priority = ["wav", "flac", "mp3"]\n'
        'min_mp3_bitrate = 320\n'
    )

    cfg = Config.from_toml(cfg_file)

    assert cfg.complete_dir == tmp_path / "Complete"
    assert cfg.library_dir == tmp_path / "Library"
    assert cfg.format_priority == ["wav", "flac", "mp3"]
    assert cfg.min_mp3_bitrate == 320
    assert cfg.acoustid_api_key == "secret-key"


def test_defaults_applied_when_sections_missing(tmp_path):
    cfg_file = tmp_path / "setmeup.toml"
    cfg_file.write_text(
        '[paths]\n'
        f'complete = "{tmp_path}/Complete"\n'
        f'library = "{tmp_path}/Library"\n'
        f'trash = "{tmp_path}/Trash"\n'
        f'db = "{tmp_path}/setmeup.db"\n'
    )

    cfg = Config.from_toml(cfg_file)

    assert cfg.format_priority == ["wav", "aiff", "aif", "flac", "mp3"]
    assert cfg.min_mp3_bitrate == 320
    assert "[paths]" in DEFAULT_CONFIG_TOML
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_config.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setmeup.config'`.

- [ ] **Step 3: Create `src/setmeup/config.py`**

```python
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

DEFAULT_FORMAT_PRIORITY = ["wav", "aiff", "aif", "flac", "mp3"]

DEFAULT_CONFIG_TOML = """# setmeup configuration
[paths]
complete = "~/Music/Complete"
library = "~/Music/Library"
trash = "~/Music/Trash"
db = "~/Music/setmeup.db"

[quality]
# Highest priority first. Anything not listed scores lowest.
format_priority = ["wav", "aiff", "aif", "flac", "mp3"]
# MP3s below this bitrate (kbps) are rejected.
min_mp3_bitrate = 320

[matching]
# Minimum fuzzy match confidence (used by later acquisition phases).
match_threshold = 0.8
"""


@dataclass
class Config:
    complete_dir: Path
    library_dir: Path
    trash_dir: Path
    db_path: Path
    acoustid_api_key: Optional[str]
    format_priority: list[str]
    min_mp3_bitrate: int
    match_threshold: float

    @classmethod
    def from_toml(cls, path: Path) -> "Config":
        load_dotenv()
        with open(path, "rb") as handle:
            data = tomllib.load(handle)

        paths = data.get("paths", {})
        quality = data.get("quality", {})
        matching = data.get("matching", {})

        def as_path(value: str) -> Path:
            return Path(value).expanduser()

        return cls(
            complete_dir=as_path(paths["complete"]),
            library_dir=as_path(paths["library"]),
            trash_dir=as_path(paths["trash"]),
            db_path=as_path(paths["db"]),
            acoustid_api_key=os.environ.get("ACOUSTID_API_KEY"),
            format_priority=quality.get("format_priority", list(DEFAULT_FORMAT_PRIORITY)),
            min_mp3_bitrate=int(quality.get("min_mp3_bitrate", 320)),
            match_threshold=float(matching.get("match_threshold", 0.8)),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_config.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add src/setmeup/config.py tests/test_config.py
git commit -m "feat: add config loader with TOML + env support"
```

---

## Task 3: State — schema & connection

**Files:**
- Create: `src/setmeup/state/__init__.py`
- Create: `src/setmeup/state/db.py`
- Create: `tests/test_db.py`

- [ ] **Step 1: Write the failing test**

`tests/test_db.py`:
```python
from setmeup.state.db import connect, init_schema


def test_init_schema_creates_tables(tmp_path):
    conn = connect(tmp_path / "setmeup.db")
    init_schema(conn)

    names = {
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'table'"
        ).fetchall()
    }

    assert {"tracks", "library_index"} <= names


def test_init_schema_is_idempotent(tmp_path):
    conn = connect(tmp_path / "setmeup.db")
    init_schema(conn)
    init_schema(conn)  # must not raise

    count = conn.execute("SELECT COUNT(*) AS n FROM tracks").fetchone()["n"]
    assert count == 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_db.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setmeup.state'`.

- [ ] **Step 3: Create `src/setmeup/state/__init__.py`**

```python
```
(empty file)

- [ ] **Step 4: Create `src/setmeup/state/db.py`**

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_db.py -v`
Expected: PASS (both tests).

- [ ] **Step 6: Commit**

```bash
git add src/setmeup/state/__init__.py src/setmeup/state/db.py tests/test_db.py
git commit -m "feat: add sqlite state schema and connection"
```

---

## Task 4: State — models & repository

**Files:**
- Create: `src/setmeup/state/models.py`
- Create: `src/setmeup/state/repository.py`
- Create: `tests/test_repository.py`

- [ ] **Step 1: Write the failing test**

`tests/test_repository.py`:
```python
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


def test_library_entry_roundtrip_and_eviction(conn):
    repo.add_library_entry(conn, "rec-1", "/lib/x.wav", 100, "A", "T", None)
    entry = repo.get_library_entry_by_key(conn, "rec-1")
    assert entry["library_path"] == "/lib/x.wav"
    assert entry["quality_score"] == 100

    assert repo.library_quality_by_key(conn) == {"rec-1": 100}

    repo.remove_library_entry(conn, "/lib/x.wav")
    assert repo.get_library_entry_by_key(conn, "rec-1") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_repository.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setmeup.state.models'`.

- [ ] **Step 3: Create `src/setmeup/state/models.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class TrackStatus(str, Enum):
    DOWNLOADED = "downloaded"
    FINGERPRINTED = "fingerprinted"
    RESOLVED = "resolved"
    DEDUPED = "deduped"
    ORGANIZED = "organized"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    FAILED = "failed"


@dataclass
class Track:
    id: Optional[int]
    source_path: str
    status: str
    artist: Optional[str] = None
    title: Optional[str] = None
    version: Optional[str] = None
    fingerprint: Optional[str] = None
    duration: Optional[float] = None
    acoustid: Optional[str] = None
    dedupe_key: Optional[str] = None
    quality_score: Optional[int] = None
    canonical_name: Optional[str] = None
    library_path: Optional[str] = None
    error: Optional[str] = None
```

- [ ] **Step 4: Create `src/setmeup/state/repository.py`**

```python
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
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_repository.py -v`
Expected: PASS (all four tests).

- [ ] **Step 6: Commit**

```bash
git add src/setmeup/state/models.py src/setmeup/state/repository.py tests/test_repository.py
git commit -m "feat: add track/library repository over sqlite state"
```

---

## Task 5: Version extraction

**Files:**
- Create: `src/setmeup/audio/__init__.py`
- Create: `src/setmeup/audio/version.py`
- Create: `tests/test_version.py`

- [ ] **Step 1: Write the failing test**

`tests/test_version.py`:
```python
import pytest

from setmeup.audio.version import extract_version


@pytest.mark.parametrize(
    "title, expected_title, expected_version",
    [
        ("Around the World (Extended Mix)", "Around the World", "Extended Mix"),
        ("Strobe (Eric Prydz Remix)", "Strobe", "Eric Prydz Remix"),
        ("Track [Radio Edit]", "Track", "Radio Edit"),
        ("One More Time", "One More Time", None),
        ("Song (feat. Pharrell)", "Song (feat. Pharrell)", None),
        ("Voodoo People (Instrumental)", "Voodoo People", "Instrumental"),
    ],
)
def test_extract_version(title, expected_title, expected_version):
    cleaned, version = extract_version(title)
    assert cleaned == expected_title
    assert version == expected_version
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_version.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setmeup.audio'`.

- [ ] **Step 3: Create `src/setmeup/audio/__init__.py`**

```python
```
(empty file)

- [ ] **Step 4: Create `src/setmeup/audio/version.py`**

```python
from __future__ import annotations

import re
from typing import Optional

# Words that, when present in a parenthetical/bracket group, mark it as a
# mix/version descriptor rather than e.g. a featured-artist note.
_VERSION_KEYWORDS = (
    "mix",
    "remix",
    "edit",
    "dub",
    "instrumental",
    "acapella",
    "a cappella",
    "vip",
    "version",
    "bootleg",
    "rework",
    "refix",
    "flip",
)

_GROUP_RE = re.compile(r"[\(\[]([^\(\)\[\]]+)[\)\]]")


def _looks_like_version(text: str) -> bool:
    low = f" {text.lower().strip()} "
    return any(low.endswith(f"{kw} ") or f" {kw} " in low for kw in _VERSION_KEYWORDS)


def extract_version(title: str) -> tuple[str, Optional[str]]:
    """Split a mix/version descriptor off a track title.

    Returns ``(clean_title, version_or_None)``. When no version-like group is
    found the title is returned unchanged and the version is ``None``.
    """
    chosen = None
    for match in _GROUP_RE.finditer(title):
        if _looks_like_version(match.group(1)):
            chosen = match
            break

    version: Optional[str] = None
    if chosen is not None:
        version = chosen.group(1).strip()
        title = title[: chosen.start()] + title[chosen.end() :]

    cleaned = re.sub(r"\s{2,}", " ", title).strip().strip("-").strip()
    return cleaned, version
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_version.py -v`
Expected: PASS (all six parametrized cases).

- [ ] **Step 6: Commit**

```bash
git add src/setmeup/audio/__init__.py src/setmeup/audio/version.py tests/test_version.py
git commit -m "feat: add mix/version extraction from titles"
```

---

## Task 6: Filename parsing

**Files:**
- Create: `src/setmeup/audio/filename.py`
- Create: `tests/test_filename.py`

- [ ] **Step 1: Write the failing test**

`tests/test_filename.py`:
```python
import pytest

from setmeup.audio.filename import parse_filename


@pytest.mark.parametrize(
    "stem, artist, title",
    [
        ("Daft Punk - Around the World", "Daft Punk", "Around the World"),
        ("01 - Daft Punk - Around the World", "Daft Punk", "Around the World"),
        ("Artist - Title - Extended Mix", "Artist", "Title - Extended Mix"),
        ("just_a_blob", None, None),
    ],
)
def test_parse_filename(stem, artist, title):
    assert parse_filename(stem) == (artist, title)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_filename.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setmeup.audio.filename'`.

- [ ] **Step 3: Create `src/setmeup/audio/filename.py`**

```python
from __future__ import annotations

from typing import Optional


def parse_filename(stem: str) -> tuple[Optional[str], Optional[str]]:
    """Best-effort ``Artist - Title`` parse of a filename stem.

    Drops a leading bare track-number token. Returns ``(None, None)`` when the
    stem does not contain at least two dash-separated parts.
    """
    parts = [part.strip() for part in stem.split(" - ")]
    if parts and parts[0].isdigit():
        parts = parts[1:]
    if len(parts) >= 2:
        artist = parts[0] or None
        title = " - ".join(parts[1:]) or None
        return artist, title
    return None, None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_filename.py -v`
Expected: PASS (all four cases).

- [ ] **Step 5: Commit**

```bash
git add src/setmeup/audio/filename.py tests/test_filename.py
git commit -m "feat: add artist/title filename parsing"
```

---

## Task 7: Canonical naming

**Files:**
- Create: `src/setmeup/naming.py`
- Create: `tests/test_naming.py`

- [ ] **Step 1: Write the failing test**

`tests/test_naming.py`:
```python
from setmeup.naming import build_canonical_name, sanitize


def test_three_part_name():
    assert (
        build_canonical_name("Daft Punk", "Around the World", "Extended Mix")
        == "Daft Punk - Around the World - Extended Mix"
    )


def test_two_part_name_when_no_version():
    assert (
        build_canonical_name("Daft Punk", "Around the World", None)
        == "Daft Punk - Around the World"
    )


def test_sanitize_strips_illegal_characters():
    assert sanitize('a/b:c?d|e*f') == "abcdef"


def test_sanitize_collapses_whitespace():
    assert sanitize("a    b   c") == "a b c"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_naming.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setmeup.naming'`.

- [ ] **Step 3: Create `src/setmeup/naming.py`**

```python
from __future__ import annotations

import re
from typing import Optional

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize(name: str) -> str:
    cleaned = _ILLEGAL.sub("", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.strip(".")


def build_canonical_name(
    artist: Optional[str], title: Optional[str], version: Optional[str]
) -> str:
    parts = [(artist or "Unknown Artist").strip(), (title or "Unknown Title").strip()]
    if version:
        parts.append(version.strip())
    return sanitize(" - ".join(parts))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_naming.py -v`
Expected: PASS (all four tests).

- [ ] **Step 5: Commit**

```bash
git add src/setmeup/naming.py tests/test_naming.py
git commit -m "feat: add canonical name builder and sanitizer"
```

---

## Task 8: Audio quality probing & scoring

**Files:**
- Create: `src/setmeup/audio/quality.py`
- Create: `tests/test_quality.py`

- [ ] **Step 1: Write the failing test**

`tests/test_quality.py`:
```python
from setmeup.audio.quality import AudioInfo, score_audio

PRIORITY = ["wav", "aiff", "aif", "flac", "mp3"]


def test_higher_tier_format_scores_higher():
    wav = AudioInfo(ext="wav", bitrate=1411, sample_rate=44100, duration=180.0)
    flac = AudioInfo(ext="flac", bitrate=900, sample_rate=44100, duration=180.0)
    assert score_audio(wav, PRIORITY, 320) > score_audio(flac, PRIORITY, 320)


def test_mp3_below_min_bitrate_is_rejected():
    low = AudioInfo(ext="mp3", bitrate=256, sample_rate=44100, duration=180.0)
    assert score_audio(low, PRIORITY, 320) == -1


def test_mp3_at_min_bitrate_is_accepted():
    ok = AudioInfo(ext="mp3", bitrate=320, sample_rate=44100, duration=180.0)
    assert score_audio(ok, PRIORITY, 320) >= 0


def test_unknown_format_scores_lowest_but_acceptable():
    weird = AudioInfo(ext="ogg", bitrate=500, sample_rate=44100, duration=180.0)
    flac = AudioInfo(ext="flac", bitrate=900, sample_rate=44100, duration=180.0)
    assert 0 <= score_audio(weird, PRIORITY, 320) < score_audio(flac, PRIORITY, 320)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_quality.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setmeup.audio.quality'`.

- [ ] **Step 3: Create `src/setmeup/audio/quality.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from mutagen import File as MutagenFile


@dataclass
class AudioInfo:
    ext: str
    bitrate: Optional[int]  # kbps
    sample_rate: Optional[int]  # Hz
    duration: Optional[float]  # seconds


def probe_audio(path: Path) -> AudioInfo:
    ext = path.suffix.lower().lstrip(".")
    bitrate = sample_rate = None
    duration = None
    media = MutagenFile(path)
    info = getattr(media, "info", None)
    if info is not None:
        raw_bitrate = getattr(info, "bitrate", 0) or 0
        bitrate = (raw_bitrate // 1000) or None
        sample_rate = getattr(info, "sample_rate", None)
        duration = getattr(info, "length", None)
    return AudioInfo(ext=ext, bitrate=bitrate, sample_rate=sample_rate, duration=duration)


def score_audio(info: AudioInfo, format_priority: list[str], min_mp3_bitrate: int) -> int:
    """Composite quality score. Returns -1 for files that fail the minimum bar.

    Ordering preference: format tier, then sample rate, then bitrate.
    """
    ext = info.ext.lower()
    if ext == "mp3" and (info.bitrate or 0) < min_mp3_bitrate:
        return -1

    try:
        tier = len(format_priority) - format_priority.index(ext)
    except ValueError:
        tier = 0

    return tier * 1_000_000_000 + (info.sample_rate or 0) * 1_000 + (info.bitrate or 0)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_quality.py -v`
Expected: PASS (all four tests).

- [ ] **Step 5: Commit**

```bash
git add src/setmeup/audio/quality.py tests/test_quality.py
git commit -m "feat: add audio quality probing and scoring"
```

---

## Task 9: Fingerprinting

**Files:**
- Create: `src/setmeup/audio/fingerprint.py`
- Create: `tests/conftest.py`
- Create: `tests/test_fingerprint.py`

- [ ] **Step 1: Create the shared audio fixture helper**

`tests/conftest.py`:
```python
import shutil
import subprocess

import pytest


def _require(binary: str) -> None:
    if shutil.which(binary) is None:
        pytest.skip(f"{binary} not installed")


@pytest.fixture()
def make_audio(tmp_path):
    """Synthesize a short tone file with ffmpeg. Returns a factory."""

    def _make(filename: str, freq: int = 440, seconds: float = 3.0, extra=None):
        _require("ffmpeg")
        out = tmp_path / filename
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={freq}:duration={seconds}",
        ]
        if extra:
            cmd += extra
        cmd.append(str(out))
        subprocess.run(cmd, check=True)
        return out

    return _make
```

- [ ] **Step 2: Write the failing test**

`tests/test_fingerprint.py`:
```python
import shutil

import pytest

from setmeup.audio.fingerprint import fingerprint_file


@pytest.mark.skipif(shutil.which("fpcalc") is None, reason="fpcalc not installed")
def test_fingerprint_returns_duration_and_string(make_audio):
    path = make_audio("tone.wav", seconds=3.0)

    duration, fingerprint = fingerprint_file(path)

    assert 2.0 < duration < 4.0
    assert isinstance(fingerprint, str)
    assert len(fingerprint) > 0
```

- [ ] **Step 3: Run test to verify it fails**

Run: `uv run pytest tests/test_fingerprint.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setmeup.audio.fingerprint'`.

- [ ] **Step 4: Create `src/setmeup/audio/fingerprint.py`**

```python
from __future__ import annotations

from pathlib import Path

import acoustid


def fingerprint_file(path: Path) -> tuple[float, str]:
    """Return ``(duration_seconds, chromaprint_fingerprint)`` for an audio file.

    Uses the ``fpcalc`` binary via pyacoustid. The fingerprint is normalized to
    an ASCII ``str``.
    """
    duration, fingerprint = acoustid.fingerprint_file(str(path))
    if isinstance(fingerprint, bytes):
        fingerprint = fingerprint.decode("ascii")
    return float(duration), fingerprint
```

- [ ] **Step 5: Run test to verify it passes**

Run: `uv run pytest tests/test_fingerprint.py -v`
Expected: PASS (or SKIP if `fpcalc`/`ffmpeg` missing — both are installed in this environment, so expect PASS).

- [ ] **Step 6: Commit**

```bash
git add src/setmeup/audio/fingerprint.py tests/conftest.py tests/test_fingerprint.py
git commit -m "feat: add chromaprint fingerprinting wrapper"
```

---

## Task 10: Metadata resolver

**Files:**
- Create: `src/setmeup/audio/metadata.py`
- Create: `tests/test_metadata.py`

- [ ] **Step 1: Write the failing test**

`tests/test_metadata.py`:
```python
from pathlib import Path

from setmeup.audio import metadata
from setmeup.audio.metadata import ResolvedMetadata, resolve_metadata


def test_acoustid_wins_and_version_is_split(monkeypatch):
    monkeypatch.setattr(
        metadata,
        "_from_acoustid",
        lambda fp, dur, key: ("Daft Punk", "Around the World (Extended Mix)", "rec-1"),
    )

    result = resolve_metadata(Path("/x/file.wav"), "FP", 200.0, "key")

    assert result == ResolvedMetadata(
        artist="Daft Punk",
        title="Around the World",
        version="Extended Mix",
        acoustid="rec-1",
        source="acoustid",
    )


def test_falls_back_to_tags_then_filename(monkeypatch):
    monkeypatch.setattr(metadata, "_from_acoustid", lambda fp, dur, key: None)
    monkeypatch.setattr(metadata, "_from_tags", lambda path: None)

    result = resolve_metadata(Path("/x/Aphex Twin - Xtal.flac"), "FP", 200.0, None)

    assert result.artist == "Aphex Twin"
    assert result.title == "Xtal"
    assert result.source == "filename"


def test_unresolvable_returns_nones(monkeypatch):
    monkeypatch.setattr(metadata, "_from_acoustid", lambda fp, dur, key: None)
    monkeypatch.setattr(metadata, "_from_tags", lambda path: None)

    result = resolve_metadata(Path("/x/blob.wav"), "FP", 200.0, None)

    assert result.artist is None
    assert result.title is None
    assert result.source == "none"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_metadata.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setmeup.audio.metadata'`.

- [ ] **Step 3: Create `src/setmeup/audio/metadata.py`**

```python
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import acoustid
from mutagen import File as MutagenFile

from setmeup.audio.filename import parse_filename
from setmeup.audio.version import extract_version


@dataclass
class ResolvedMetadata:
    artist: Optional[str]
    title: Optional[str]
    version: Optional[str]
    acoustid: Optional[str]
    source: str  # "acoustid" | "tags" | "filename" | "none"


def _from_acoustid(
    fingerprint: str, duration: float, api_key: Optional[str]
) -> Optional[tuple[str, str, str]]:
    """Return ``(artist, title, recording_id)`` from AcoustID, or None."""
    if not api_key:
        return None
    try:
        response = acoustid.lookup(api_key, fingerprint, duration, meta="recordings")
    except acoustid.AcoustidError:
        return None
    for _score, recording_id, title, artist in acoustid.parse_lookup_result(response):
        if artist and title:
            return artist, title, recording_id
    return None


def _from_tags(path: Path) -> Optional[tuple[str, str]]:
    media = MutagenFile(path, easy=True)
    if media is None:
        return None
    artist = (media.get("artist") or [None])[0]
    title = (media.get("title") or [None])[0]
    if artist and title:
        return artist, title
    return None


def resolve_metadata(
    path: Path, fingerprint: str, duration: float, api_key: Optional[str]
) -> ResolvedMetadata:
    artist: Optional[str] = None
    title: Optional[str] = None
    acoustid_id: Optional[str] = None
    source = "none"

    found = _from_acoustid(fingerprint, duration, api_key)
    if found:
        artist, title, acoustid_id = found
        source = "acoustid"

    if not (artist and title):
        tagged = _from_tags(path)
        if tagged:
            artist, title = tagged
            source = "tags"

    if not (artist and title):
        parsed_artist, parsed_title = parse_filename(path.stem)
        if parsed_artist and parsed_title:
            artist, title = parsed_artist, parsed_title
            source = "filename"

    version: Optional[str] = None
    if title:
        title, version = extract_version(title)

    return ResolvedMetadata(
        artist=artist, title=title, version=version, acoustid=acoustid_id, source=source
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_metadata.py -v`
Expected: PASS (all three tests).

- [ ] **Step 5: Commit**

```bash
git add src/setmeup/audio/metadata.py tests/test_metadata.py
git commit -m "feat: add hybrid metadata resolver (acoustid/tags/filename)"
```

---

## Task 11: Dedupe logic

**Files:**
- Create: `src/setmeup/dedupe.py`
- Create: `tests/test_dedupe.py`

- [ ] **Step 1: Write the failing test**

`tests/test_dedupe.py`:
```python
from setmeup.dedupe import DedupeCandidate, resolve_duplicates


def test_keeps_best_within_batch():
    candidates = [
        DedupeCandidate(track_id=1, dedupe_key="rec-1", quality_score=10),
        DedupeCandidate(track_id=2, dedupe_key="rec-1", quality_score=20),
    ]
    result = resolve_duplicates(candidates, existing={})
    assert result.winners == [2]
    assert result.losers == [1]


def test_distinct_keys_all_win():
    candidates = [
        DedupeCandidate(track_id=1, dedupe_key="rec-1", quality_score=10),
        DedupeCandidate(track_id=2, dedupe_key="rec-2", quality_score=10),
    ]
    result = resolve_duplicates(candidates, existing={})
    assert sorted(result.winners) == [1, 2]
    assert result.losers == []


def test_existing_better_makes_candidate_a_loser():
    candidates = [DedupeCandidate(track_id=1, dedupe_key="rec-1", quality_score=5)]
    result = resolve_duplicates(candidates, existing={"rec-1": 9})
    assert result.winners == []
    assert result.losers == [1]


def test_candidate_beats_existing_and_wins():
    candidates = [DedupeCandidate(track_id=1, dedupe_key="rec-1", quality_score=15)]
    result = resolve_duplicates(candidates, existing={"rec-1": 9})
    assert result.winners == [1]
    assert result.losers == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_dedupe.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setmeup.dedupe'`.

- [ ] **Step 3: Create `src/setmeup/dedupe.py`**

```python
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DedupeCandidate:
    track_id: int
    dedupe_key: str
    quality_score: int


@dataclass
class DedupeResult:
    winners: list[int] = field(default_factory=list)
    losers: list[int] = field(default_factory=list)


def resolve_duplicates(
    candidates: list[DedupeCandidate], existing: dict[str, int]
) -> DedupeResult:
    """Keep-best deduplication.

    Within ``candidates``, the highest-scoring track per ``dedupe_key`` wins;
    the rest are losers. A per-key winner only stays a winner if it strictly
    beats any ``existing`` Library quality for that key.
    """
    result = DedupeResult()
    best: dict[str, DedupeCandidate] = {}

    for candidate in candidates:
        current = best.get(candidate.dedupe_key)
        if current is None or candidate.quality_score > current.quality_score:
            if current is not None:
                result.losers.append(current.track_id)
            best[candidate.dedupe_key] = candidate
        else:
            result.losers.append(candidate.track_id)

    for key, candidate in best.items():
        prior = existing.get(key)
        if prior is not None and prior >= candidate.quality_score:
            result.losers.append(candidate.track_id)
        else:
            result.winners.append(candidate.track_id)

    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_dedupe.py -v`
Expected: PASS (all four tests).

- [ ] **Step 5: Commit**

```bash
git add src/setmeup/dedupe.py tests/test_dedupe.py
git commit -m "feat: add keep-best dedupe resolution"
```

---

## Task 12: Process orchestration

**Files:**
- Create: `src/setmeup/process.py`
- Create: `tests/test_process.py`

- [ ] **Step 1: Write the failing test**

`tests/test_process.py`:
```python
from pathlib import Path

import pytest

from setmeup.audio.metadata import ResolvedMetadata
from setmeup.config import Config
from setmeup.state.db import connect, init_schema
from setmeup.state import repository as repo
from setmeup.state.models import TrackStatus
from setmeup import process as process_mod


@pytest.fixture()
def cfg(tmp_path):
    return Config(
        complete_dir=tmp_path / "Complete",
        library_dir=tmp_path / "Library",
        trash_dir=tmp_path / "Trash",
        db_path=tmp_path / "setmeup.db",
        acoustid_api_key=None,
        format_priority=["wav", "flac", "mp3"],
        min_mp3_bitrate=320,
        match_threshold=0.8,
    )


def test_process_resolves_and_dedupes(cfg, monkeypatch):
    cfg.complete_dir.mkdir(parents=True)
    good = cfg.complete_dir / "a.wav"
    dup = cfg.complete_dir / "b.flac"
    for path in (good, dup):
        path.write_bytes(b"fake-audio")

    # Same recording for both files; wav outranks flac.
    monkeypatch.setattr(
        process_mod,
        "fingerprint_file",
        lambda path: (180.0, "FP-" + Path(path).suffix),
    )
    monkeypatch.setattr(
        process_mod,
        "resolve_metadata",
        lambda path, fp, dur, key: ResolvedMetadata(
            "Daft Punk", "Around the World", "Extended Mix", "rec-1", "acoustid"
        ),
    )
    from setmeup.audio.quality import AudioInfo

    def fake_probe(path):
        ext = Path(path).suffix.lstrip(".")
        return AudioInfo(ext=ext, bitrate=1000, sample_rate=44100, duration=180.0)

    monkeypatch.setattr(process_mod, "probe_audio", fake_probe)

    conn = connect(cfg.db_path)
    init_schema(conn)
    process_mod.process_folder(conn, cfg)

    deduped = repo.get_tracks_by_status(conn, TrackStatus.DEDUPED.value)
    skipped = repo.get_tracks_by_status(conn, TrackStatus.SKIPPED_DUPLICATE.value)
    assert len(deduped) == 1
    assert deduped[0].source_path.endswith("a.wav")
    assert deduped[0].canonical_name == "Daft Punk - Around the World - Extended Mix"
    assert len(skipped) == 1


def test_unresolvable_track_is_failed(cfg, monkeypatch):
    cfg.complete_dir.mkdir(parents=True)
    (cfg.complete_dir / "x.wav").write_bytes(b"fake")

    monkeypatch.setattr(process_mod, "fingerprint_file", lambda path: (10.0, "FP"))
    monkeypatch.setattr(
        process_mod,
        "resolve_metadata",
        lambda path, fp, dur, key: ResolvedMetadata(None, None, None, None, "none"),
    )
    from setmeup.audio.quality import AudioInfo

    monkeypatch.setattr(
        process_mod,
        "probe_audio",
        lambda path: AudioInfo("wav", 1000, 44100, 10.0),
    )

    conn = connect(cfg.db_path)
    init_schema(conn)
    process_mod.process_folder(conn, cfg)

    failed = repo.get_tracks_by_status(conn, TrackStatus.FAILED.value)
    assert len(failed) == 1
    assert "resolve" in failed[0].error
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_process.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setmeup.process'`.

- [ ] **Step 3: Create `src/setmeup/process.py`**

```python
from __future__ import annotations

import sqlite3
from pathlib import Path

from setmeup.audio.fingerprint import fingerprint_file
from setmeup.audio.metadata import resolve_metadata
from setmeup.audio.quality import probe_audio, score_audio
from setmeup.config import Config
from setmeup.dedupe import DedupeCandidate, resolve_duplicates
from setmeup.naming import build_canonical_name
from setmeup.state import repository as repo
from setmeup.state.models import TrackStatus

AUDIO_EXTS = {".wav", ".aiff", ".aif", ".flac", ".mp3"}


def discover(complete_dir: Path) -> list[Path]:
    if not complete_dir.exists():
        return []
    return sorted(
        path
        for path in complete_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in AUDIO_EXTS
    )


def process_folder(conn: sqlite3.Connection, config: Config) -> None:
    # 1. Register newly seen files.
    for path in discover(config.complete_dir):
        repo.add_track(conn, str(path), TrackStatus.DOWNLOADED.value)

    # 2. Fingerprint, resolve, score each freshly downloaded track.
    for track in repo.get_tracks_by_status(conn, TrackStatus.DOWNLOADED.value):
        path = Path(track.source_path)
        try:
            duration, fingerprint = fingerprint_file(path)
            meta = resolve_metadata(path, fingerprint, duration, config.acoustid_api_key)
            info = probe_audio(path)
            score = score_audio(info, config.format_priority, config.min_mp3_bitrate)

            if score < 0:
                repo.update_track(
                    conn,
                    track.id,
                    status=TrackStatus.FAILED.value,
                    error="below minimum quality",
                )
                continue
            if not (meta.artist and meta.title):
                repo.update_track(
                    conn,
                    track.id,
                    status=TrackStatus.FAILED.value,
                    error="could not resolve artist/title",
                )
                continue

            dedupe_key = meta.acoustid or fingerprint
            canonical = build_canonical_name(meta.artist, meta.title, meta.version)
            repo.update_track(
                conn,
                track.id,
                status=TrackStatus.RESOLVED.value,
                fingerprint=fingerprint,
                duration=duration,
                artist=meta.artist,
                title=meta.title,
                version=meta.version,
                acoustid=meta.acoustid,
                dedupe_key=dedupe_key,
                quality_score=score,
                canonical_name=canonical,
                error=None,
            )
        except Exception as exc:  # noqa: BLE001 - record and continue the batch
            repo.update_track(
                conn, track.id, status=TrackStatus.FAILED.value, error=str(exc)
            )

    # 3. Keep-best dedupe across resolved tracks + the existing Library.
    resolved = repo.get_tracks_by_status(conn, TrackStatus.RESOLVED.value)
    candidates = [
        DedupeCandidate(t.id, t.dedupe_key, t.quality_score) for t in resolved
    ]
    existing = repo.library_quality_by_key(conn)
    result = resolve_duplicates(candidates, existing)

    for track_id in result.winners:
        repo.update_track(conn, track_id, status=TrackStatus.DEDUPED.value)
    for track_id in result.losers:
        repo.update_track(conn, track_id, status=TrackStatus.SKIPPED_DUPLICATE.value)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_process.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add src/setmeup/process.py tests/test_process.py
git commit -m "feat: add process orchestration (fingerprint/resolve/dedupe)"
```

---

## Task 13: Organize orchestration

**Files:**
- Create: `src/setmeup/organize.py`
- Create: `tests/test_organize.py`

- [ ] **Step 1: Write the failing test**

`tests/test_organize.py`:
```python
from pathlib import Path

import pytest

from setmeup.config import Config
from setmeup.state.db import connect, init_schema
from setmeup.state import repository as repo
from setmeup.state.models import TrackStatus
from setmeup import organize as organize_mod


@pytest.fixture()
def cfg(tmp_path):
    return Config(
        complete_dir=tmp_path / "Complete",
        library_dir=tmp_path / "Library",
        trash_dir=tmp_path / "Trash",
        db_path=tmp_path / "setmeup.db",
        acoustid_api_key=None,
        format_priority=["wav", "flac", "mp3"],
        min_mp3_bitrate=320,
        match_threshold=0.8,
    )


def _add_deduped(conn, source_path, *, key, score, name):
    tid = repo.add_track(conn, str(source_path), TrackStatus.DOWNLOADED.value)
    repo.update_track(
        conn,
        tid,
        status=TrackStatus.DEDUPED.value,
        artist="A",
        title="T",
        dedupe_key=key,
        quality_score=score,
        canonical_name=name,
    )
    return tid


def test_organize_copies_and_preserves_original(cfg):
    cfg.complete_dir.mkdir(parents=True)
    src = cfg.complete_dir / "a.wav"
    src.write_bytes(b"audio-bytes")

    conn = connect(cfg.db_path)
    init_schema(conn)
    _add_deduped(conn, src, key="rec-1", score=100, name="A - T")

    organize_mod.organize(conn, cfg)

    target = cfg.library_dir / "A - T.wav"
    assert target.exists()
    assert target.read_bytes() == b"audio-bytes"
    assert src.exists()  # copy-not-move: original preserved
    assert repo.get_library_entry_by_key(conn, "rec-1")["library_path"] == str(target)
    organized = repo.get_tracks_by_status(conn, TrackStatus.ORGANIZED.value)
    assert organized[0].library_path == str(target)


def test_better_copy_evicts_existing_to_trash(cfg):
    cfg.complete_dir.mkdir(parents=True)
    cfg.library_dir.mkdir(parents=True)
    old = cfg.library_dir / "A - T.flac"
    old.write_bytes(b"old")
    new_src = cfg.complete_dir / "a.wav"
    new_src.write_bytes(b"new")

    conn = connect(cfg.db_path)
    init_schema(conn)
    repo.add_library_entry(conn, "rec-1", str(old), 50, "A", "T", None)
    _add_deduped(conn, new_src, key="rec-1", score=100, name="A - T")

    organize_mod.organize(conn, cfg)

    assert not old.exists()
    assert (cfg.trash_dir / "A - T.flac").exists()
    assert (cfg.library_dir / "A - T.wav").exists()
    assert repo.get_library_entry_by_key(conn, "rec-1")["library_path"].endswith("A - T.wav")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_organize.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setmeup.organize'`.

- [ ] **Step 3: Create `src/setmeup/organize.py`**

```python
from __future__ import annotations

import hashlib
import shutil
import sqlite3
from pathlib import Path

from setmeup.config import Config
from setmeup.state import repository as repo
from setmeup.state.models import TrackStatus


def _checksum(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unique_target(library_dir: Path, name: str, ext: str) -> Path:
    target = library_dir / f"{name}{ext}"
    counter = 2
    while target.exists():
        target = library_dir / f"{name} ({counter}){ext}"
        counter += 1
    return target


def organize(conn: sqlite3.Connection, config: Config) -> None:
    config.library_dir.mkdir(parents=True, exist_ok=True)
    config.trash_dir.mkdir(parents=True, exist_ok=True)

    for track in repo.get_tracks_by_status(conn, TrackStatus.DEDUPED.value):
        src = Path(track.source_path)
        ext = src.suffix.lower()

        existing = repo.get_library_entry_by_key(conn, track.dedupe_key)
        if existing is not None:
            if existing["quality_score"] < track.quality_score:
                old = Path(existing["library_path"])
                if old.exists():
                    shutil.move(str(old), str(config.trash_dir / old.name))
                repo.remove_library_entry(conn, existing["library_path"])
            else:
                # Existing copy is as good or better; do not promote.
                repo.update_track(
                    conn, track.id, status=TrackStatus.SKIPPED_DUPLICATE.value
                )
                continue

        target = _unique_target(config.library_dir, track.canonical_name, ext)
        shutil.copy2(src, target)
        if _checksum(src) != _checksum(target):
            target.unlink(missing_ok=True)
            repo.update_track(
                conn,
                track.id,
                status=TrackStatus.FAILED.value,
                error="checksum mismatch after copy",
            )
            continue

        repo.add_library_entry(
            conn,
            track.dedupe_key,
            str(target),
            track.quality_score,
            track.artist,
            track.title,
            track.version,
        )
        repo.update_track(
            conn,
            track.id,
            status=TrackStatus.ORGANIZED.value,
            library_path=str(target),
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_organize.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add src/setmeup/organize.py tests/test_organize.py
git commit -m "feat: add organize stage with copy/verify/evict"
```

---

## Task 14: CLI

**Files:**
- Create: `src/setmeup/cli.py`
- Create: `tests/test_cli.py`

- [ ] **Step 1: Write the failing test**

`tests/test_cli.py`:
```python
from typer.testing import CliRunner

from setmeup.cli import app

runner = CliRunner()


def test_init_writes_config(tmp_path):
    target = tmp_path / "setmeup.toml"
    result = runner.invoke(app, ["init", "--path", str(target)])
    assert result.exit_code == 0
    assert target.exists()
    assert "[paths]" in target.read_text()


def test_init_refuses_overwrite(tmp_path):
    target = tmp_path / "setmeup.toml"
    target.write_text("existing")
    result = runner.invoke(app, ["init", "--path", str(target)])
    assert result.exit_code == 1


def test_status_runs_on_fresh_db(tmp_path):
    config = tmp_path / "setmeup.toml"
    config.write_text(
        '[paths]\n'
        f'complete = "{tmp_path}/Complete"\n'
        f'library = "{tmp_path}/Library"\n'
        f'trash = "{tmp_path}/Trash"\n'
        f'db = "{tmp_path}/setmeup.db"\n'
    )
    result = runner.invoke(app, ["status", "--config", str(config)])
    assert result.exit_code == 0
    assert "Status" in result.stdout
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'setmeup.cli'`.

- [ ] **Step 3: Create `src/setmeup/cli.py`**

```python
from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from setmeup import organize as organize_mod
from setmeup import process as process_mod
from setmeup.config import Config, DEFAULT_CONFIG_TOML
from setmeup.state import repository as repo
from setmeup.state.db import connect, init_schema

app = typer.Typer(help="setmeup - DJ music library pipeline")
console = Console()

ConfigOption = typer.Option(Path("setmeup.toml"), "--config", help="Path to config TOML")


def _open(config_path: Path):
    cfg = Config.from_toml(config_path)
    conn = connect(cfg.db_path)
    init_schema(conn)
    return cfg, conn


def _print_status(conn) -> None:
    counts = repo.count_by_status(conn)
    table = Table("Status", "Count", title="setmeup")
    for status, count in sorted(counts.items()):
        table.add_row(status, str(count))
    if not counts:
        table.add_row("(none)", "0")
    console.print(table)


@app.command()
def init(path: Path = typer.Option(Path("setmeup.toml"), "--path", help="Where to write the config")):
    """Write a starter config file."""
    if path.exists():
        console.print(f"[yellow]{path} already exists; not overwriting.[/]")
        raise typer.Exit(1)
    path.write_text(DEFAULT_CONFIG_TOML)
    console.print(f"[green]Wrote {path}[/]")


@app.command()
def process(config: Path = ConfigOption):
    """Fingerprint, resolve, and dedupe files in the Complete folder."""
    cfg, conn = _open(config)
    process_mod.process_folder(conn, cfg)
    _print_status(conn)


@app.command()
def organize(config: Path = ConfigOption):
    """Copy dedupe winners into the Library."""
    cfg, conn = _open(config)
    organize_mod.organize(conn, cfg)
    _print_status(conn)


@app.command()
def status(config: Path = ConfigOption):
    """Show track counts by pipeline state."""
    _, conn = _open(config)
    _print_status(conn)


if __name__ == "__main__":
    app()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_cli.py -v`
Expected: PASS (all three tests).

- [ ] **Step 5: Verify the installed entry point works**

Run: `uv run setmeup --help`
Expected: usage text listing `init`, `process`, `organize`, `status`.

- [ ] **Step 6: Commit**

```bash
git add src/setmeup/cli.py tests/test_cli.py
git commit -m "feat: add typer CLI (init/process/organize/status)"
```

---

## Task 15: End-to-end integration test

**Files:**
- Create: `tests/test_integration.py`

- [ ] **Step 1: Write the end-to-end test**

`tests/test_integration.py`:
```python
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
```

- [ ] **Step 2: Run the test**

Run: `uv run pytest tests/test_integration.py -v`
Expected: PASS (or SKIP if `ffmpeg`/`fpcalc` missing — both present here, so expect PASS).

- [ ] **Step 3: Run the whole suite**

Run: `uv run pytest -v`
Expected: all tests PASS (none failing; fixture-dependent ones may SKIP only if binaries are absent).

- [ ] **Step 4: Commit**

```bash
git add tests/test_integration.py
git commit -m "test: add end-to-end process+organize integration test"
```

---

## Self-Review (completed during planning)

**Spec coverage (phases 1–2):**
- Config + `.env` secrets → Task 2 ✅
- SQLite state store (`tracks`, `library_index`, state machine) → Tasks 3–4 ✅
- Fingerprint once (Chromaprint) → Task 9, reused in Task 12 ✅
- Hybrid metadata (AcoustID → tags → filename) → Task 10 ✅
- Version extraction, omit when unknown → Task 5 (`extract_version`), applied in Task 12; `build_canonical_name` drops the 3rd segment when version is `None` (Task 7) ✅
- Quality scoring incl. format priority WAV/AIFF→FLAC→MP3-320 and below-320 reject → Task 8 ✅
- Keep-best dedupe vs batch + Library index → Task 11 + Task 12 ✅
- Copy-into-Library, originals preserved, eviction → Trash → Task 13, asserted in Task 15 ✅
- Flat Library with canonical filenames → Task 13 (`_unique_target`) ✅
- CLI with Rich (`init`/`process`/`organize`/`status`) → Task 14 ✅
- Checksum-verify on copy; per-track failure isolation; idempotent re-runs (status-keyed `add_track`/queries) → Tasks 12–13 ✅

**Deferred to later plans (out of scope here, by design):** slskd `fetch`/search/selection, playlist sources (wantlist/CSV/Rekordbox/Spotify/YouTube), `run` chaining, `retry`, fingerprint-*similarity* matching (this plan groups by AcoustID id, falling back to exact-fingerprint equality).

**Placeholder scan:** no TBD/TODO/"add error handling"; every code step is complete.

**Type/name consistency:** `Config`, `TrackStatus`, `Track`, `ResolvedMetadata`, `AudioInfo`, `DedupeCandidate`/`DedupeResult`, and repository function names (`add_track`, `update_track`, `get_tracks_by_status`, `count_by_status`, `add_library_entry`, `get_library_entry_by_key`, `remove_library_entry`, `library_quality_by_key`) are defined once and used consistently. `process.py` references `fingerprint_file`/`resolve_metadata`/`probe_audio` as module-level names so tests can monkeypatch them.
