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
from setmeup.sources.wantlist import WantlistSource
from setmeup.state import repository as repo
from setmeup.state import wants as wants_repo
from setmeup.state.db import connect, init_schema

app = typer.Typer(help="setmeup - DJ music library pipeline")
console = Console()

ConfigOption = typer.Option(Path("setmeup.toml"), "--config", help="Path to config TOML")


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


@app.command("import")
def import_(
    config: Path = ConfigOption,
    wantlist: Optional[Path] = typer.Option(None, "--wantlist", help="Wantlist .txt"),
    csv: Optional[Path] = typer.Option(None, "--csv", help="exportify CSV"),
):
    """Import a source into the wants table."""
    if sum(x is not None for x in (wantlist, csv)) != 1:
        console.print("[red]Specify exactly one of --wantlist / --csv[/]")
        raise typer.Exit(2)
    cfg, conn = _open(config)
    if wantlist is not None:
        source, ref = WantlistSource(wantlist), str(wantlist)
        name = "wantlist"
    else:
        source, ref = CsvSource(csv), str(csv)
        name = "csv"
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
