from __future__ import annotations

from dataclasses import dataclass
from pathlib import PurePosixPath, PureWindowsPath
from typing import Optional

from rapidfuzz import fuzz

from setmeup.audio.quality import AudioInfo, score_audio

AUDIO_EXTS = {"wav", "aiff", "aif", "flac", "mp3"}


@dataclass
class Candidate:
    username: str
    filename: str
    size: int
    bitrate: Optional[int]
    length: Optional[int]
    free_slot: bool
    upload_speed: int
    queue_length: int


@dataclass
class SelectionTarget:
    artist: str
    title: str
    version: Optional[str]
    duration_ms: Optional[int]


def _basename(filename: str) -> str:
    # slskd filenames are Windows-style backslash paths; handle both.
    name = PureWindowsPath(filename).name
    return PurePosixPath(name).name


def _ext(filename: str) -> str:
    base = _basename(filename)
    return base.rsplit(".", 1)[-1].lower() if "." in base else ""


def _stem(filename: str) -> str:
    base = _basename(filename)
    return base.rsplit(".", 1)[0] if "." in base else base


def candidates_from_responses(responses: list[dict]) -> list[Candidate]:
    out: list[Candidate] = []
    for response in responses:
        for file in response.get("files", []):
            filename = file.get("filename", "")
            if _ext(filename) not in AUDIO_EXTS:
                continue
            out.append(Candidate(
                username=response.get("username", ""),
                filename=filename,
                size=file.get("size", 0),
                bitrate=file.get("bitRate"),
                length=file.get("length"),
                free_slot=bool(response.get("hasFreeUploadSlot")),
                upload_speed=response.get("uploadSpeed", 0),
                queue_length=response.get("queueLength", 0),
            ))
    return out


def _match_string(target: SelectionTarget) -> str:
    return " ".join(p for p in (target.artist, target.title, target.version) if p)


def rank(target: SelectionTarget, candidates: list[Candidate], config) -> list[Candidate]:
    match_str = _match_string(target)
    scored = []
    for cand in candidates:
        quality = score_audio(
            AudioInfo(ext=_ext(cand.filename), bitrate=cand.bitrate,
                      sample_rate=None, duration=cand.length),
            config.format_priority, config.min_mp3_bitrate,
        )
        if quality < 0:
            continue
        confidence = fuzz.token_set_ratio(_stem(cand.filename), match_str)
        if confidence < config.match_threshold * 100:
            continue
        if target.duration_ms is not None and cand.length is not None:
            if abs(cand.length - target.duration_ms / 1000) > config.duration_tolerance_seconds:
                continue
        scored.append((quality, confidence, cand.free_slot, cand.upload_speed,
                       -cand.queue_length, cand))
    scored.sort(key=lambda s: s[:5], reverse=True)
    return [s[-1] for s in scored]
