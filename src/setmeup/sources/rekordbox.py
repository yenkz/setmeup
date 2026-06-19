from __future__ import annotations

import urllib.parse
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

from setmeup.sources.base import WantlistEntry

AUDIO_EXTS = {"wav", "aiff", "aif", "flac", "mp3", "m4a", "aac", "ogg"}
GUARD_THRESHOLD = 0.9


@dataclass
class RkTrack:
    track_id: str
    location: str
    artist: str
    name: str
    album: Optional[str] = None
    total_time_s: Optional[int] = None
    kind: Optional[str] = None


def parse_collection(path) -> tuple[dict[str, RkTrack], dict[str, list[str]]]:
    root = ET.parse(path).getroot()

    tracks: dict[str, RkTrack] = {}
    collection = root.find("COLLECTION")
    for el in (collection.findall("TRACK") if collection is not None else []):
        track_id = el.get("TrackID")
        if track_id is None:
            continue
        total = el.get("TotalTime")
        tracks[track_id] = RkTrack(
            track_id=track_id,
            location=el.get("Location", ""),
            artist=el.get("Artist", ""),
            name=el.get("Name", ""),
            album=el.get("Album") or None,
            total_time_s=int(total) if total and total.isdigit() else None,
            kind=el.get("Kind") or None,
        )

    playlists: dict[str, list[str]] = {}

    def walk(node) -> None:
        if node.get("Type") == "1":  # playlist leaf
            ids = [t.get("Key") for t in node.findall("TRACK") if t.get("Key")]
            playlists[node.get("Name", "")] = ids
        else:  # folder (Type 0): recurse
            for child in node.findall("NODE"):
                walk(child)

    playlists_root = root.find("PLAYLISTS")
    if playlists_root is not None:
        for node in playlists_root.findall("NODE"):
            walk(node)

    return tracks, playlists


def list_playlists(path) -> list[tuple[str, int]]:
    _, playlists = parse_collection(path)
    return [(name, len(ids)) for name, ids in playlists.items()]


def decode_location(
    location: str, remap: Optional[list[tuple[str, str]]] = None
) -> Path:
    raw = urllib.parse.unquote(urllib.parse.urlparse(location).path)
    # Windows drive paths decode to "/C:/..."; drop the leading slash.
    if len(raw) >= 3 and raw[0] == "/" and raw[2] == ":":
        raw = raw[1:]
    for old, new in remap or []:
        if raw.startswith(old):
            raw = new + raw[len(old):]
            break
    return Path(raw)


def _ext(path: Path) -> str:
    return path.suffix.lstrip(".").lower()


@dataclass
class RekordboxScanResult:
    total: int
    present: int
    missing: int
    skipped_non_audio: int
    missing_entries: list[WantlistEntry]

    @property
    def missing_fraction(self) -> float:
        denom = self.present + self.missing
        return self.missing / denom if denom else 0.0

    @property
    def guard_tripped(self) -> bool:
        return (self.present + self.missing) > 0 and self.missing_fraction > GUARD_THRESHOLD


class RekordboxSource:
    def __init__(self, path, playlists: list[str],
                 remap: Optional[list[tuple[str, str]]] = None):
        self.path = Path(path)
        tracks, all_playlists = parse_collection(self.path)
        unknown = [name for name in playlists if name not in all_playlists]
        if unknown:
            raise ValueError(f"playlist(s) not found: {unknown}")
        seen: set[str] = set()
        ids: list[str] = []
        for name in playlists:
            for tid in all_playlists[name]:
                if tid not in seen:
                    seen.add(tid)
                    ids.append(tid)
        self.scan = self._scan(tracks, ids, remap)

    def _scan(self, tracks, ids, remap) -> RekordboxScanResult:
        present = missing = skipped = 0
        entries: list[WantlistEntry] = []
        for tid in ids:
            track = tracks.get(tid)
            if track is None:
                continue
            file_path = decode_location(track.location, remap)
            is_audio = _ext(file_path) in AUDIO_EXTS
            exists = file_path.exists()
            if not is_audio:
                if not exists:
                    skipped += 1
                continue
            if exists:
                present += 1
                continue
            missing += 1
            entries.append(WantlistEntry(
                artist=track.artist,
                title=track.name,
                album=track.album,
                duration_ms=track.total_time_s * 1000 if track.total_time_s else None,
            ))
        return RekordboxScanResult(
            total=len(ids), present=present, missing=missing,
            skipped_non_audio=skipped, missing_entries=entries,
        )

    def entries(self) -> Iterator[WantlistEntry]:
        return iter(self.scan.missing_entries)
