import shutil
import subprocess

import pytest


def _require(binary: str) -> None:
    if shutil.which(binary) is None:
        pytest.skip(f"{binary} not installed")


@pytest.fixture()
def make_audio(tmp_path):
    """Synthesize a short tone file with ffmpeg. Returns a factory."""

    def _make(filename: str, freq: int = 440, seconds: float = 3.0, extra=None):
        _require("ffmpeg")
        out = tmp_path / filename
        cmd = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency={freq}:duration={seconds}",
        ]
        if extra:
            cmd += extra
        cmd.append(str(out))
        subprocess.run(cmd, check=True)
        return out

    return _make
