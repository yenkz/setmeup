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


@pytest.fixture()
def make_config(tmp_path):
    """Factory for a fully-populated Config pointing at tmp_path."""
    from setmeup.config import Config

    def _make(**overrides):
        defaults = dict(
            complete_dir=tmp_path / "Complete",
            library_dir=tmp_path / "Library",
            trash_dir=tmp_path / "Trash",
            db_path=tmp_path / "setmeup.db",
            acoustid_api_key=None,
            format_priority=["wav", "aiff", "aif", "flac", "mp3"],
            min_mp3_bitrate=320,
            match_threshold=0.8,
            slskd_base_url="http://localhost:5030",
            slskd_api_key=None,
            spotify_client_id=None,
            spotify_client_secret=None,
            spotify_redirect_uri="http://127.0.0.1:8888/callback",
            search_timeout_seconds=10,
            download_timeout_seconds=300,
            search_concurrency=4,
            download_attempts=3,
            duration_tolerance_seconds=20,
        )
        defaults.update(overrides)
        return Config(**defaults)

    return _make
