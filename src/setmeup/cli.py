from __future__ import annotations

from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from setmeup import organize as organize_mod
from setmeup import process as process_mod
from setmeup.config import Config, DEFAULT_CONFIG_TOML
from setmeup.state import repository as repo
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


if __name__ == "__main__":
    app()
