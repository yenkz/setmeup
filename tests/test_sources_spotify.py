from setmeup.sources.spotify import SpotifySource, list_playlists


class FakeSpotify:
    def __init__(self, me, playlists, items):
        self._me = me
        self._playlists = playlists
        self._items = items

    def current_user(self):
        return {"id": self._me}

    def current_user_playlists(self, limit=50):
        return {"items": self._playlists, "next": None}

    def next(self, result):
        return None

    def playlist_items(self, pid, additional_types=("track",)):
        return {"items": self._items, "next": None}


def test_list_playlists_filters_to_owner():
    sp = FakeSpotify(
        me="yenkz",
        playlists=[
            {"id": "p1", "name": "Vinyl", "owner": {"id": "yenkz"}, "tracks": {"total": 12}},
            {"id": "p2", "name": "Someone Else", "owner": {"id": "other"}, "tracks": {"total": 3}},
        ],
        items=[],
    )
    assert list_playlists(sp) == [("p1", "Vinyl", 12)]


def test_source_yields_entries_and_skips_local_null():
    sp = FakeSpotify(
        me="yenkz",
        playlists=[{"id": "p1", "name": "Vinyl", "owner": {"id": "yenkz"}, "tracks": {"total": 2}}],
        items=[
            {"track": {"id": "t1", "name": "Xtal", "is_local": False,
                       "artists": [{"name": "Aphex Twin"}],
                       "album": {"name": "SAW 85-92"}, "duration_ms": 294000,
                       "uri": "spotify:track:t1"}},
            {"track": {"id": "t2", "name": "Local", "is_local": True, "artists": []}},
            {"track": None},
        ],
    )
    entries = list(SpotifySource(sp, "Vinyl").entries())
    assert len(entries) == 1
    assert entries[0].artist == "Aphex Twin"
    assert entries[0].title == "Xtal"
    assert entries[0].duration_ms == 294000
