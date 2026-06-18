from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Optional, Protocol


@dataclass
class WantlistEntry:
    artist: str
    title: str
    album: Optional[str] = None
    duration_ms: Optional[int] = None
    spotify_uri: Optional[str] = None


class PlaylistSource(Protocol):
    def entries(self) -> Iterator[WantlistEntry]: ...
