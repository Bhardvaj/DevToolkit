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


def test_remove_search_path(tmp_path, monkeypatch):
    test_cfg_path = tmp_path / "config.yaml"
    monkeypatch.setattr("devtoolkit.core.config.get_config_path", lambda: test_cfg_path)

    from devtoolkit.core.config import remove_search_path, remove_search_path_by_index

    dir1 = tmp_path / "dir1"
    dir2 = tmp_path / "dir2"
    dir1.mkdir()
    dir2.mkdir()

    add_search_path(str(dir1))
    add_search_path(str(dir2))
    assert len(load_config().search_paths) == 2

    # Remove by exact string
    assert remove_search_path(str(dir1)) is True
    assert str(dir1) not in load_config().search_paths
    assert len(load_config().search_paths) == 1

    # Remove non-existent returns False
    assert remove_search_path(str(tmp_path / "non_existent")) is False

    # Remove by index
    assert remove_search_path_by_index(0) is True
    assert len(load_config().search_paths) == 0
    assert remove_search_path_by_index(0) is False


def test_remove_search_path_normalization(tmp_path, monkeypatch):
    test_cfg_path = tmp_path / "config.yaml"
    monkeypatch.setattr("devtoolkit.core.config.get_config_path", lambda: test_cfg_path)

    from devtoolkit.core.config import remove_search_path

    test_dir = tmp_path / "ToolsFolder"
    test_dir.mkdir()
    add_search_path(str(test_dir))

    # Test removing with trailing slash and case differences
    variant = str(test_dir).lower() + ("/" if not str(test_dir).endswith(("/", "\\")) else "")
    assert remove_search_path(variant) is True
    assert len(load_config().search_paths) == 0

