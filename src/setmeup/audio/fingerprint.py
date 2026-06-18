from __future__ import annotations

from pathlib import Path

import acoustid


def fingerprint_file(path: Path) -> tuple[float, str]:
    """Return ``(duration_seconds, chromaprint_fingerprint)`` for an audio file.

    Uses the ``fpcalc`` binary via pyacoustid. The fingerprint is normalized to
    an ASCII ``str``.
    """
    duration, fingerprint = acoustid.fingerprint_file(str(path))
    if isinstance(fingerprint, bytes):
        fingerprint = fingerprint.decode("ascii")
    return float(duration), fingerprint
