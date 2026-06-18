from __future__ import annotations

import re

_PUNCT = re.compile(r"[^\w\s]", flags=re.UNICODE)
_WS = re.compile(r"\s+")


def normalize(text: str) -> str:
    text = _PUNCT.sub(" ", text.lower())
    return _WS.sub(" ", text).strip()


def normalize_key(artist: str, title: str, version: str | None) -> str:
    return f"{normalize(artist)}|{normalize(title)}|{normalize(version or '')}"
