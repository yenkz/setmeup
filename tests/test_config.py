from pathlib import Path

import pytest

from setmeup.config import Config, DEFAULT_CONFIG_TOML


def test_from_toml_parses_paths_and_quality(tmp_path, monkeypatch):
    monkeypatch.setenv("ACOUSTID_API_KEY", "secret-key")
    cfg_file = tmp_path / "setmeup.toml"
    cfg_file.write_text(
        '[paths]\n'
        f'complete = "{tmp_path}/Complete"\n'
        f'library = "{tmp_path}/Library"\n'
        f'trash = "{tmp_path}/Trash"\n'
        f'db = "{tmp_path}/setmeup.db"\n'
        '[quality]\n'
        'format_priority = ["wav", "flac", "mp3"]\n'
        'min_mp3_bitrate = 320\n'
    )

    cfg = Config.from_toml(cfg_file)

    assert cfg.complete_dir == tmp_path / "Complete"
    assert cfg.library_dir == tmp_path / "Library"
    assert cfg.format_priority == ["wav", "flac", "mp3"]
    assert cfg.min_mp3_bitrate == 320
    assert cfg.acoustid_api_key == "secret-key"


def test_defaults_applied_when_sections_missing(tmp_path):
    cfg_file = tmp_path / "setmeup.toml"
    cfg_file.write_text(
        '[paths]\n'
        f'complete = "{tmp_path}/Complete"\n'
        f'library = "{tmp_path}/Library"\n'
        f'trash = "{tmp_path}/Trash"\n'
        f'db = "{tmp_path}/setmeup.db"\n'
    )

    cfg = Config.from_toml(cfg_file)

    assert cfg.format_priority == ["wav", "aiff", "aif", "flac", "mp3"]
    assert cfg.min_mp3_bitrate == 320
    assert "[paths]" in DEFAULT_CONFIG_TOML


def test_loads_acquisition_config(tmp_path, monkeypatch):
    monkeypatch.setenv("SLSKD_API_KEY", "slskd-secret")
    monkeypatch.setenv("SPOTIFY_CLIENT_ID", "cid")
    monkeypatch.setenv("SPOTIFY_CLIENT_SECRET", "csecret")
    cfg_file = tmp_path / "setmeup.toml"
    cfg_file.write_text(
        '[paths]\n'
        f'complete = "{tmp_path}/Complete"\n'
        f'library = "{tmp_path}/Library"\n'
        f'trash = "{tmp_path}/Trash"\n'
        f'db = "{tmp_path}/setmeup.db"\n'
        '[slskd]\n'
        'base_url = "http://localhost:5030"\n'
        '[spotify]\n'
        'redirect_uri = "http://127.0.0.1:8888/callback"\n'
        '[acquire]\n'
        'search_timeout_seconds = 7\n'
        'download_attempts = 2\n'
    )
    from setmeup.config import Config

    cfg = Config.from_toml(cfg_file)

    assert cfg.slskd_base_url == "http://localhost:5030"
    assert cfg.slskd_api_key == "slskd-secret"
    assert cfg.spotify_client_id == "cid"
    assert cfg.spotify_client_secret == "csecret"
    assert cfg.spotify_redirect_uri == "http://127.0.0.1:8888/callback"
    assert cfg.search_timeout_seconds == 7
    assert cfg.download_attempts == 2
    assert cfg.duration_tolerance_seconds == 20  # default


def test_missing_paths_key_raises_clear_error(tmp_path):
    cfg_file = tmp_path / "setmeup.toml"
    cfg_file.write_text(
        '[paths]\n'
        f'complete = "{tmp_path}/Complete"\n'
        f'library = "{tmp_path}/Library"\n'
        f'trash = "{tmp_path}/Trash"\n'
        # db deliberately omitted
    )
    with pytest.raises(ValueError) as excinfo:
        Config.from_toml(cfg_file)
    message = str(excinfo.value)
    assert "[paths]" in message
    assert "db" in message


def test_missing_paths_section_raises_clear_error(tmp_path):
    cfg_file = tmp_path / "setmeup.toml"
    cfg_file.write_text('[quality]\nmin_mp3_bitrate = 320\n')
    with pytest.raises(ValueError) as excinfo:
        Config.from_toml(cfg_file)
    assert "[paths]" in str(excinfo.value)
