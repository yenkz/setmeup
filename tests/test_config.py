from pathlib import Path

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
