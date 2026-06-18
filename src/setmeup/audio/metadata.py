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
