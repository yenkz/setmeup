from __future__ import annotations

from pathlib import Path
from typing import Optional

import typer
from rich.console import Console
from rich.table import Table

from setmeup import organize as organize_mod
from setmeup import process as process_mod
from setmeup.acquire import fetch as fetch_mod
from setmeup.acquire.importer import import_entries
from setmeup.slskd.client import SlskdClient
from setmeup.config import Config, DEFAULT_CONFIG_TOML
from setmeup.sources.csv_source import CsvSource
from setmeup.sources.rekordbox import RekordboxSource, list_playlists as list_rkb_playlists
from setmeup.sources.spotify import SpotifySource, build_client, list_playlists
from setmeup.sources.wantlist import WantlistSource
from setmeup.state import repository as repo
from setmeup.state import wants as wants_repo
from setmeup.state.db import connect, init_schema

app = typer.Typer(help="setmeup - DJ music library pipeline")
console = Console()

ConfigOption = typer.Option(Path("setmeup.toml"), "--config", help="Path to config TOML")

spotify_app = typer.Typer(help="Spotify auth and playlist listing")
app.add_typer(spotify_app, name="spotify")

rekordbox_app = typer.Typer(help="Rekordbox collection helpers")
app.add_typer(rekordbox_app, name="rekordbox")


@rekordbox_app.command("playlists")
def rekordbox_playlists(
    collection: Path = typer.Argument(..., help="Rekordbox collection.xml"),
):
    """List playlists (name + track count) in a Rekordbox collection.xml."""
    table = Table("name", "tracks", title="Rekordbox playlists")
    for name, count in list_rkb_playlists(collection):
        table.add_row(name, str(count))
    console.print(table)


@spotify_app.command("auth")
def spotify_auth(config: Path = ConfigOption):
    """Run the one-time Spotify OAuth flow and cache the token."""
    cfg = Config.from_toml(config)
    build_client(cfg).current_user()
    console.print("[green]Spotify authenticated.[/]")


@spotify_app.command("playlists")
def spotify_playlists(config: Path = ConfigOption):
    """List your Spotify playlists."""
    cfg = Config.from_toml(config)
    table = Table("id", "name", "tracks", title="Spotify playlists")
    for pid, name, total in list_playlists(build_client(cfg)):
        table.add_row(pid, name, str(total))
    console.print(table)


def _open(config_path: Path):
    cfg = Config.from_toml(config_path)
    conn = connect(cfg.db_path)
    init_schema(conn)
    return cfg, conn


def _print_status(conn) -> None:
    counts = repo.count_by_status(conn)
    table = Table("Status", "Count", title="setmeup")
    for status, count in sorted(counts.items()):
        table.add_row(status, str(count))
    if not counts:
        table.add_row("(none)", "0")
    console.print(table)


@app.command()
def init(path: Path = typer.Option(Path("setmeup.toml"), "--path", help="Where to write the config")):
    """Write a starter config file."""
    if path.exists():
        console.print(f"[yellow]{path} already exists; not overwriting.[/]")
        raise typer.Exit(1)
    path.write_text(DEFAULT_CONFIG_TOML)
    console.print(f"[green]Wrote {path}[/]")


@app.command()
def process(config: Path = ConfigOption):
    """Fingerprint, resolve, and dedupe files in the Complete folder."""
    cfg, conn = _open(config)
    process_mod.process_folder(conn, cfg)
    _print_status(conn)


@app.command()
def organize(config: Path = ConfigOption):
    """Copy dedupe winners into the Library."""
    cfg, conn = _open(config)
    organize_mod.organize(conn, cfg)
    _print_status(conn)


@app.command()
def status(config: Path = ConfigOption):
    """Show track counts by pipeline state."""
    _, conn = _open(config)
    _print_status(conn)


def _parse_remap(remap: list[str]) -> list[tuple[str, str]]:
    pairs: list[tuple[str, str]] = []
    for item in remap:
        if "=" not in item:
            console.print(f"[red]--remap must be OLD=NEW, got: {item!r}[/]")
            raise typer.Exit(2)
        old, new = item.split("=", 1)
        pairs.append((old, new))
    return pairs


def _import_rekordbox(conn, path: Path, playlist: list[str],
                      remap: list[str], force: bool) -> None:
    if not playlist:
        console.print("[red]--rekordbox requires at least one --playlist[/]")
        raise typer.Exit(2)
    try:
        source = RekordboxSource(path, playlist, remap=_parse_remap(remap))
    except ValueError as exc:
        console.print(f"[red]{exc}[/]")
        raise typer.Exit(2)
    scan = source.scan
    if scan.guard_tripped and not force:
        in_scope = scan.present + scan.missing
        console.print(
            f"[red]{scan.missing}/{in_scope} in-scope tracks missing — paths likely "
            f"don't match this machine; use --remap or --force[/]"
        )
        raise typer.Exit(2)
    console.print(
        f"scanned {scan.total} · present {scan.present} · "
        f"missing {scan.missing} (queued) · skipped {scan.skipped_non_audio} non-audio"
    )
    result = import_entries(conn, "rekordbox", str(path), source.entries())
    console.print(
        f"[green]imported {result.imported}[/], "
        f"already_have {result.already_have}, duplicates {result.duplicates}"
    )


@app.command("import")
def import_(
    config: Path = ConfigOption,
    wantlist: Optional[Path] = typer.Option(None, "--wantlist", help="Wantlist .txt"),
    csv: Optional[Path] = typer.Option(None, "--csv", help="exportify CSV"),
    spotify: Optional[str] = typer.Option(None, "--spotify", help="Spotify playlist name or id"),
    rekordbox: Optional[Path] = typer.Option(None, "--rekordbox", help="Rekordbox collection.xml"),
    playlist: list[str] = typer.Option([], "--playlist", help="Playlist name (repeatable; required with --rekordbox)"),
    remap: list[str] = typer.Option([], "--remap", help='Path remap "OLD=NEW" (repeatable)'),
    force: bool = typer.Option(False, "--force", help="Override the missing-tracks safety guard"),
):
    """Import a source into the wants table."""
    if sum(x is not None for x in (wantlist, csv, spotify, rekordbox)) != 1:
        console.print("[red]Specify exactly one of --wantlist / --csv / --spotify / --rekordbox[/]")
        raise typer.Exit(2)
    cfg, conn = _open(config)
    if rekordbox is not None:
        _import_rekordbox(conn, rekordbox, playlist, remap, force)
        return
    if wantlist is not None:
        source, ref, name = WantlistSource(wantlist), str(wantlist), "wantlist"
    elif csv is not None:
        source, ref, name = CsvSource(csv), str(csv), "csv"
    else:
        source, ref, name = SpotifySource(build_client(cfg), spotify), spotify, "spotify"
    result = import_entries(conn, name, ref, source.entries())
    console.print(
        f"[green]imported {result.imported}[/], "
        f"already_have {result.already_have}, duplicates {result.duplicates}"
    )


@app.command()
def wants(config: Path = ConfigOption):
    """Show want counts by status."""
    _, conn = _open(config)
    counts = wants_repo.count_wants_by_status(conn)
    table = Table("Want status", "Count", title="setmeup wants")
    for status, count in sorted(counts.items()):
        table.add_row(status, str(count))
    if not counts:
        table.add_row("(none)", "0")
    console.print(table)


@app.command()
def fetch(
    config: Path = ConfigOption,
    retry: bool = typer.Option(False, "--retry", help="Also re-attempt failed/no_match wants"),
    limit: int = typer.Option(0, "--limit", help="Max wants to process (0 = all)"),
):
    """Search slskd and download pending wants into Complete/."""
    cfg, conn = _open(config)
    client = SlskdClient(cfg.slskd_base_url, cfg.slskd_api_key)
    statuses = ("wanted",) + (("failed", "no_match") if retry else ())
    counts = fetch_mod.fetch(conn, cfg, client, statuses=statuses, limit=limit)
    table = Table("Want status", "Count", title="setmeup fetch")
    for status, count in sorted(counts.items()):
        table.add_row(status, str(count))
    if not counts:
        table.add_row("(none)", "0")
    console.print(table)


if __name__ == "__main__":
    app()
