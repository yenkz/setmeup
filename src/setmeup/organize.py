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
