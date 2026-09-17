"""Tests for user configuration."""

from pathlib import Path
from devtoolkit.core.config import DevToolkitConfig, add_search_path, load_config, save_config


def test_config_serialization(tmp_path, monkeypatch):
    test_cfg_path = tmp_path / "config.yaml"
    monkeypatch.setattr("devtoolkit.core.config.get_config_path", lambda: test_cfg_path)

    cfg = DevToolkitConfig(search_paths=[str(tmp_path)])
    save_config(cfg)

    loaded = load_config()
    assert str(tmp_path) in loaded.search_paths


def test_add_search_path(tmp_path, monkeypatch):
    test_cfg_path = tmp_path / "config.yaml"
    monkeypatch.setattr("devtoolkit.core.config.get_config_path", lambda: test_cfg_path)

    new_dir = tmp_path / "my_tools"
    new_dir.mkdir()

    added = add_search_path(str(new_dir))
    assert added is True

    # Duplicate should return False
    assert add_search_path(str(new_dir)) is False
