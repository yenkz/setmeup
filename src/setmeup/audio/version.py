from __future__ import annotations

import re
from typing import Optional

# Words that, when present in a parenthetical/bracket group, mark it as a
# mix/version descriptor rather than e.g. a featured-artist note.
_VERSION_KEYWORDS = (
    "mix",
    "remix",
    "edit",
    "dub",
    "instrumental",
    "acapella",
    "a cappella",
    "vip",
    "version",
    "bootleg",
    "rework",
    "refix",
    "flip",
)

_GROUP_RE = re.compile(r"[\(\[]([^\(\)\[\]]+)[\)\]]")


def _looks_like_version(text: str) -> bool:
    low = f" {text.lower().strip()} "
    return any(low.endswith(f"{kw} ") or f" {kw} " in low for kw in _VERSION_KEYWORDS)


def extract_version(title: str) -> tuple[str, Optional[str]]:
    """Split a mix/version descriptor off a track title.

    Returns ``(clean_title, version_or_None)``. When no version-like group is
    found the title is returned unchanged and the version is ``None``.
    """
    chosen = None
    for match in _GROUP_RE.finditer(title):
        if _looks_like_version(match.group(1)):
            chosen = match
            break

    version: Optional[str] = None
    if chosen is not None:
        version = chosen.group(1).strip()
        title = title[: chosen.start()] + title[chosen.end() :]

    cleaned = re.sub(r"\s{2,}", " ", title).strip().strip("-").strip()
    return cleaned, version
