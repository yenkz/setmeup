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
