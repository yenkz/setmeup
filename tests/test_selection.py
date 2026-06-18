from setmeup.slskd.selection import (
    Candidate, SelectionTarget, candidates_from_responses, rank,
)


def _cand(filename, bitrate=None, length=None, free=True, speed=100, queue=0):
    return Candidate(username="bob", filename=filename, size=1000, bitrate=bitrate,
                     length=length, free_slot=free, upload_speed=speed, queue_length=queue)


def test_candidates_from_responses_filters_non_audio():
    responses = [{
        "username": "bob", "hasFreeUploadSlot": True, "uploadSpeed": 50, "queueLength": 1,
        "files": [
            {"filename": "a.flac", "size": 10, "bitRate": 900, "length": 200},
            {"filename": "cover.jpg", "size": 5},
        ],
    }]
    cands = candidates_from_responses(responses)
    assert [c.filename for c in cands] == ["a.flac"]
    assert cands[0].free_slot is True


def test_rank_prefers_lossless_and_rejects_low_mp3(make_config):
    cfg = make_config()
    target = SelectionTarget("Daft Punk", "Around the World", None, None)
    cands = [
        _cand("Daft Punk - Around the World.flac", bitrate=900),
        _cand("Daft Punk - Around the World.mp3", bitrate=128),  # below 320 -> reject
        _cand("Daft Punk - Around the World.wav", bitrate=1411),
    ]
    ranked = rank(target, cands, cfg)
    assert [c.filename for c in ranked] == [
        "Daft Punk - Around the World.wav",
        "Daft Punk - Around the World.flac",
    ]


def test_rank_rejects_low_confidence_filename(make_config):
    cfg = make_config()
    target = SelectionTarget("Daft Punk", "Around the World", None, None)
    cands = [_cand("Some Other Artist - Totally Different Song.flac", bitrate=900)]
    assert rank(target, cands, cfg) == []


def test_rank_duration_sanity(make_config):
    cfg = make_config(duration_tolerance_seconds=20)
    target = SelectionTarget("Daft Punk", "Around the World", None, duration_ms=420000)  # 420s
    good = _cand("Daft Punk - Around the World.flac", bitrate=900, length=419)
    preview = _cand("Daft Punk - Around the World (preview).flac", bitrate=900, length=30)
    ranked = rank(target, [good, preview], cfg)
    assert [c.filename for c in ranked] == ["Daft Punk - Around the World.flac"]


def test_rank_duration_check_rejects_zero_length(make_config):
    cfg = make_config()
    target = SelectionTarget("Daft Punk", "Around the World", None, duration_ms=420000)
    zero_len = _cand("Daft Punk - Around the World.flac", bitrate=900, length=0)
    # length=0 is "known" (not None) and far from 420s, so it must be rejected.
    assert rank(target, [zero_len], cfg) == []
