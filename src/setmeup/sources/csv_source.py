from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterator

from setmeup.sources.base import WantlistEntry


class CsvSource:
    def __init__(self, path: Path):
        self.path = Path(path)

    def entries(self) -> Iterator[WantlistEntry]:
        with open(self.path, newline="", encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                title = (row.get("Track Name") or "").strip()
                artists = (row.get("Artist Name(s)") or "").strip()
                artist = artists.split(";")[0].strip() if artists else ""
                if not artist or not title:
                    continue
                duration = row.get("Duration (ms)") or ""
                duration_ms = int(duration) if duration.strip().isdigit() else None
                yield WantlistEntry(
                    artist=artist,
                    title=title,
                    album=(row.get("Album Name") or "").strip() or None,
                    duration_ms=duration_ms,
                    spotify_uri=(row.get("Track URI") or "").strip() or None,
                )
