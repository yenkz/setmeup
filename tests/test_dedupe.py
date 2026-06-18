from setmeup.dedupe import DedupeCandidate, resolve_duplicates


def test_keeps_best_within_batch():
    candidates = [
        DedupeCandidate(track_id=1, dedupe_key="rec-1", quality_score=10),
        DedupeCandidate(track_id=2, dedupe_key="rec-1", quality_score=20),
    ]
    result = resolve_duplicates(candidates, existing={})
    assert result.winners == [2]
    assert result.losers == [1]


def test_distinct_keys_all_win():
    candidates = [
        DedupeCandidate(track_id=1, dedupe_key="rec-1", quality_score=10),
        DedupeCandidate(track_id=2, dedupe_key="rec-2", quality_score=10),
    ]
    result = resolve_duplicates(candidates, existing={})
    assert sorted(result.winners) == [1, 2]
    assert result.losers == []


def test_existing_better_makes_candidate_a_loser():
    candidates = [DedupeCandidate(track_id=1, dedupe_key="rec-1", quality_score=5)]
    result = resolve_duplicates(candidates, existing={"rec-1": 9})
    assert result.winners == []
    assert result.losers == [1]


def test_candidate_beats_existing_and_wins():
    candidates = [DedupeCandidate(track_id=1, dedupe_key="rec-1", quality_score=15)]
    result = resolve_duplicates(candidates, existing={"rec-1": 9})
    assert result.winners == [1]
    assert result.losers == []
