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
