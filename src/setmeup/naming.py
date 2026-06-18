from __future__ import annotations

import re
from typing import Optional

_ILLEGAL = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def sanitize(name: str) -> str:
    cleaned = _ILLEGAL.sub("", name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned.strip(".")


def build_canonical_name(
    artist: Optional[str], title: Optional[str], version: Optional[str]
) -> str:
    parts = [(artist or "Unknown Artist").strip(), (title or "Unknown Title").strip()]
    if version:
        parts.append(version.strip())
    return sanitize(" - ".join(parts))
