from setmeup.audio.quality import AudioInfo, score_audio

PRIORITY = ["wav", "aiff", "aif", "flac", "mp3"]


def test_higher_tier_format_scores_higher():
    wav = AudioInfo(ext="wav", bitrate=1411, sample_rate=44100, duration=180.0)
    flac = AudioInfo(ext="flac", bitrate=900, sample_rate=44100, duration=180.0)
    assert score_audio(wav, PRIORITY, 320) > score_audio(flac, PRIORITY, 320)


def test_mp3_below_min_bitrate_is_rejected():
    low = AudioInfo(ext="mp3", bitrate=256, sample_rate=44100, duration=180.0)
    assert score_audio(low, PRIORITY, 320) == -1


def test_mp3_at_min_bitrate_is_accepted():
    ok = AudioInfo(ext="mp3", bitrate=320, sample_rate=44100, duration=180.0)
    assert score_audio(ok, PRIORITY, 320) >= 0


def test_unknown_format_scores_lowest_but_acceptable():
    weird = AudioInfo(ext="ogg", bitrate=500, sample_rate=44100, duration=180.0)
    flac = AudioInfo(ext="flac", bitrate=900, sample_rate=44100, duration=180.0)
    assert 0 <= score_audio(weird, PRIORITY, 320) < score_audio(flac, PRIORITY, 320)
