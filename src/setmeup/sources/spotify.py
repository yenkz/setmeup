from __future__ import annotations

from pathlib import Path
from typing import Iterator

import spotipy
from spotipy.oauth2 import SpotifyOAuth

from setmeup.sources.base import WantlistEntry

_SCOPE = "playlist-read-private playlist-read-collaborative"


def _token_path() -> Path:
    path = Path.home() / ".config" / "setmeup" / "spotify-token.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def build_client(config) -> spotipy.Spotify:
    auth = SpotifyOAuth(
        client_id=config.spotify_client_id,
        client_secret=config.spotify_client_secret,
        redirect_uri=config.spotify_redirect_uri,
        scope=_SCOPE,
        cache_path=str(_token_path()),
        open_browser=True,
    )
    return spotipy.Spotify(auth_manager=auth)


def list_playlists(sp) -> list[tuple[str, str, int]]:
    me = sp.current_user()["id"]
    out: list[tuple[str, str, int]] = []
    results = sp.current_user_playlists(limit=50)
    while results:
        for pl in results["items"]:
            if pl and pl["owner"]["id"] == me:
                out.append((pl["id"], pl["name"], pl["tracks"]["total"]))
        results = sp.next(results) if results.get("next") else None
    return out


class SpotifySource:
    def __init__(self, sp, ref: str):
        self.sp = sp
        self.ref = ref

    def _resolve(self) -> str:
        for pid, name, _ in list_playlists(self.sp):
            if self.ref == pid or self.ref.lower() == name.lower():
                return pid
        raise ValueError(f"playlist not found: {self.ref}")

    def entries(self) -> Iterator[WantlistEntry]:
        results = self.sp.playlist_items(self._resolve(), additional_types=("track",))
        while results:
            for item in results["items"]:
                track = item.get("track")
                if not track or track.get("is_local") or not track.get("id"):
                    continue
                artists = track.get("artists") or []
                if not artists:
                    continue
                yield WantlistEntry(
                    artist=artists[0]["name"],
                    title=track["name"],
                    album=(track.get("album") or {}).get("name"),
                    duration_ms=track.get("duration_ms"),
                    spotify_uri=track.get("uri"),
                )
            results = self.sp.next(results) if results.get("next") else None
