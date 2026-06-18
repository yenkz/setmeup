from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

try:  # Python 3.11+
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib

DEFAULT_FORMAT_PRIORITY = ["wav", "aiff", "aif", "flac", "mp3"]

DEFAULT_CONFIG_TOML = """# setmeup configuration
[paths]
complete = "~/Music/Complete"
library = "~/Music/Library"
trash = "~/Music/Trash"
db = "~/Music/setmeup.db"

[quality]
# Highest priority first. Anything not listed scores lowest.
format_priority = ["wav", "aiff", "aif", "flac", "mp3"]
# MP3s below this bitrate (kbps) are rejected.
min_mp3_bitrate = 320

[matching]
# Minimum fuzzy match confidence (used by later acquisition phases).
match_threshold = 0.8
"""


@dataclass
class Config:
    complete_dir: Path
    library_dir: Path
    trash_dir: Path
    db_path: Path
    acoustid_api_key: Optional[str]
    format_priority: list[str]
    min_mp3_bitrate: int
    match_threshold: float

    @classmethod
    def from_toml(cls, path: Path) -> "Config":
        load_dotenv()
        with open(path, "rb") as handle:
            data = tomllib.load(handle)

        paths = data.get("paths", {})
        quality = data.get("quality", {})
        matching = data.get("matching", {})

        def as_path(value: str) -> Path:
            return Path(value).expanduser()

        return cls(
            complete_dir=as_path(paths["complete"]),
            library_dir=as_path(paths["library"]),
            trash_dir=as_path(paths["trash"]),
            db_path=as_path(paths["db"]),
            acoustid_api_key=os.environ.get("ACOUSTID_API_KEY"),
            format_priority=quality.get("format_priority", list(DEFAULT_FORMAT_PRIORITY)),
            min_mp3_bitrate=int(quality.get("min_mp3_bitrate", 320)),
            match_threshold=float(matching.get("match_threshold", 0.8)),
        )
