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
