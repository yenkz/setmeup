from pathlib import Path

from setmeup.audio import metadata
from setmeup.audio.metadata import ResolvedMetadata, resolve_metadata


def test_acoustid_wins_and_version_is_split(monkeypatch):
    monkeypatch.setattr(
        metadata,
        "_from_acoustid",
        lambda fp, dur, key: ("Daft Punk", "Around the World (Extended Mix)", "rec-1"),
    )

    result = resolve_metadata(Path("/x/file.wav"), "FP", 200.0, "key")

    assert result == ResolvedMetadata(
        artist="Daft Punk",
        title="Around the World",
        version="Extended Mix",
        acoustid="rec-1",
        source="acoustid",
    )


def test_falls_back_to_tags_then_filename(monkeypatch):
    monkeypatch.setattr(metadata, "_from_acoustid", lambda fp, dur, key: None)
    monkeypatch.setattr(metadata, "_from_tags", lambda path: None)

    result = resolve_metadata(Path("/x/Aphex Twin - Xtal.flac"), "FP", 200.0, None)

    assert result.artist == "Aphex Twin"
    assert result.title == "Xtal"
    assert result.source == "filename"


def test_unresolvable_returns_nones(monkeypatch):
    monkeypatch.setattr(metadata, "_from_acoustid", lambda fp, dur, key: None)
    monkeypatch.setattr(metadata, "_from_tags", lambda path: None)

    result = resolve_metadata(Path("/x/blob.wav"), "FP", 200.0, None)

    assert result.artist is None
    assert result.title is None
    assert result.source == "none"
