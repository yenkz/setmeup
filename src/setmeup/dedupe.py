from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class DedupeCandidate:
    track_id: int
    dedupe_key: str
    quality_score: int


@dataclass
class DedupeResult:
    winners: list[int] = field(default_factory=list)
    losers: list[int] = field(default_factory=list)


def resolve_duplicates(
    candidates: list[DedupeCandidate], existing: dict[str, int]
) -> DedupeResult:
    """Keep-best deduplication.

    Within ``candidates``, the highest-scoring track per ``dedupe_key`` wins;
    the rest are losers. A per-key winner only stays a winner if it strictly
    beats any ``existing`` Library quality for that key.
    """
    result = DedupeResult()
    best: dict[str, DedupeCandidate] = {}

    for candidate in candidates:
        current = best.get(candidate.dedupe_key)
        if current is None or candidate.quality_score > current.quality_score:
            if current is not None:
                result.losers.append(current.track_id)
            best[candidate.dedupe_key] = candidate
        else:
            result.losers.append(candidate.track_id)

    for key, candidate in best.items():
        prior = existing.get(key)
        if prior is not None and prior >= candidate.quality_score:
            result.losers.append(candidate.track_id)
        else:
            result.winners.append(candidate.track_id)

    return result
