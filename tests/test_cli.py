from typer.testing import CliRunner

from setmeup.cli import app

runner = CliRunner()


def test_init_writes_config(tmp_path):
    target = tmp_path / "setmeup.toml"
    result = runner.invoke(app, ["init", "--path", str(target)])
    assert result.exit_code == 0
    assert target.exists()
    assert "[paths]" in target.read_text()


def test_init_refuses_overwrite(tmp_path):
    target = tmp_path / "setmeup.toml"
    target.write_text("existing")
    result = runner.invoke(app, ["init", "--path", str(target)])
    assert result.exit_code == 1


def test_status_runs_on_fresh_db(tmp_path):
    config = tmp_path / "setmeup.toml"
    config.write_text(
        '[paths]\n'
        f'complete = "{tmp_path}/Complete"\n'
        f'library = "{tmp_path}/Library"\n'
        f'trash = "{tmp_path}/Trash"\n'
        f'db = "{tmp_path}/setmeup.db"\n'
    )
    result = runner.invoke(app, ["status", "--config", str(config)])
    assert result.exit_code == 0
    assert "Status" in result.stdout


def _write_config(tmp_path):
    config = tmp_path / "setmeup.toml"
    config.write_text(
        '[paths]\n'
        f'complete = "{tmp_path}/Complete"\n'
        f'library = "{tmp_path}/Library"\n'
        f'trash = "{tmp_path}/Trash"\n'
        f'db = "{tmp_path}/setmeup.db"\n'
    )
    return config


def test_import_wantlist_then_wants(tmp_path):
    config = _write_config(tmp_path)
    wl = tmp_path / "wl.txt"
    wl.write_text("Daft Punk - Around the World\nAphex Twin - Xtal\n")

    result = runner.invoke(app, ["import", "--config", str(config), "--wantlist", str(wl)])
    assert result.exit_code == 0
    assert "imported" in result.stdout.lower()

    status = runner.invoke(app, ["wants", "--config", str(config)])
    assert status.exit_code == 0
    assert "wanted" in status.stdout
