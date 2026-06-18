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
