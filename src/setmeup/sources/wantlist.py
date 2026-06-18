from __future__ import annotations

import logging
from pathlib import Path
from typing import Iterator

from setmeup.sources.base import WantlistEntry

logger = logging.getLogger(__name__)


class WantlistSource:
    def __init__(self, path: Path):
        self.path = Path(path)

    def entries(self) -> Iterator[WantlistEntry]:
        for raw in self.path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = [p.strip() for p in line.split(" - ", 1)]
            if len(parts) < 2 or not parts[0] or not parts[1]:
                logger.warning("skipping malformed wantlist line: %r", raw)
                continue
            yield WantlistEntry(artist=parts[0], title=parts[1])
