import shutil

import pytest

from setmeup.audio.fingerprint import fingerprint_file


@pytest.mark.skipif(shutil.which("fpcalc") is None, reason="fpcalc not installed")
def test_fingerprint_returns_duration_and_string(make_audio):
    path = make_audio("tone.wav", seconds=3.0)

    duration, fingerprint = fingerprint_file(path)

    assert 2.0 < duration < 4.0
    assert isinstance(fingerprint, str)
    assert len(fingerprint) > 0
