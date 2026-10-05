"""Unit tests for DevToolkit Spotlight configuration and settings."""

from __future__ import annotations

import json
from pathlib import Path
import pytest
from clients.spotlight.settings import (
    SpotlightSettings,
    load_spotlight_settings,
    save_spotlight_settings,
    update_spotlight_settings,
)


def test_spotlight_settings_defaults(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg_file = tmp_path / "spotlight.json"
    monkeypatch.setenv("DEVTOOLKIT_SPOTLIGHT_CONFIG", str(cfg_file))

    settings = load_spotlight_settings()
    assert settings.hotkey == "alt+space"
    assert settings.monitor_mode == "cursor"
    assert settings.accent_color == "#38bdf8"
    assert settings.opacity == 0.92
    assert settings.blur_radius == 20
    assert settings.theme_preset == "obsidian"
    assert settings.corner_radius == 8
    assert settings.animation_speed == "normal"
    assert settings.show_details_panel is True


def test_spotlight_settings_save_and_reload(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg_file = tmp_path / "spotlight.json"
    monkeypatch.setenv("DEVTOOLKIT_SPOTLIGHT_CONFIG", str(cfg_file))

    new_cfg = SpotlightSettings(
        hotkey="ctrl+space",
        monitor_mode="focused",
        accent_color="#10b981",
        opacity=0.85,
        blur_radius=25,
        theme_preset="emerald",
        animation_speed="fast",
        show_details_panel=False,
    )
    save_spotlight_settings(new_cfg)
    assert cfg_file.is_file()

    loaded = load_spotlight_settings()
    assert loaded.hotkey == "ctrl+space"
    assert loaded.monitor_mode == "focused"
    assert loaded.accent_color == "#10b981"
    assert loaded.opacity == 0.85
    assert loaded.blur_radius == 25
    assert loaded.theme_preset == "emerald"
    assert loaded.animation_speed == "fast"
    assert loaded.show_details_panel is False


def test_spotlight_settings_update(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg_file = tmp_path / "spotlight.json"
    monkeypatch.setenv("DEVTOOLKIT_SPOTLIGHT_CONFIG", str(cfg_file))

    updated = update_spotlight_settings(accent_color="#818cf8", opacity=0.99, animation_speed="relaxed", show_details_panel=False)
    assert updated.accent_color == "#818cf8"
    assert updated.opacity == 0.99
    assert updated.animation_speed == "relaxed"
    assert updated.show_details_panel is False
    # Other defaults preserved
    assert updated.hotkey == "alt+space"

    # Verify persisted on disk
    data = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert data["accent_color"] == "#818cf8"
    assert data["opacity"] == 0.99
    assert data["animation_speed"] == "relaxed"
    assert data["show_details_panel"] is False


def test_builtin_themes_catalog():
    from clients.spotlight.settings import BUILTIN_THEMES

    assert "system" in BUILTIN_THEMES
    assert "obsidian" in BUILTIN_THEMES
    assert "emerald" in BUILTIN_THEMES
    assert "indigo" in BUILTIN_THEMES
    assert "amber" in BUILTIN_THEMES

    for key, theme in BUILTIN_THEMES.items():
        assert "id" in theme
        assert "name" in theme
        assert "accent_color" in theme
        assert "opacity" in theme
        assert "blur_radius" in theme
        assert "corner_radius" in theme
        assert theme["corner_radius"] == 8
        assert "animation_speed" in theme


def test_get_windows_system_theme():
    from clients.spotlight.settings import get_windows_system_theme

    theme = get_windows_system_theme()
    assert isinstance(theme, dict)
    assert "dark_mode" in theme
    assert isinstance(theme["dark_mode"], bool)
    assert "accent_color" in theme
    assert theme["accent_color"].startswith("#")
    assert len(theme["accent_color"]) == 7


def test_get_effective_theme():
    from clients.spotlight.settings import get_effective_theme, SpotlightSettings

    # 1. Builtin Emerald
    s_emerald = SpotlightSettings(theme_preset="emerald")
    eff_emerald = get_effective_theme(s_emerald)
    assert eff_emerald["id"] == "emerald"
    assert eff_emerald["accent_color"].lower() == "#10b981"
    assert eff_emerald["opacity"] == 0.84
    assert eff_emerald["blur_radius"] == 28

    # 2. System Theme
    s_sys = SpotlightSettings(theme_preset="system")
    eff_sys = get_effective_theme(s_sys)
    assert eff_sys["id"] == "system"
    assert "accent_color" in eff_sys
    assert eff_sys["accent_color"].startswith("#")
    assert "dark_mode" in eff_sys

    # 3. Custom Theme
    custom = {
        "id": "custom_neon",
        "name": "Neon Cyber",
        "accent_color": "#FF007F",
        "opacity": 0.75,
        "blur_radius": 36,
        "corner_radius": 20,
        "animation_speed": "snappy",
    }
    s_custom = SpotlightSettings(theme_preset="custom_neon", custom_themes=[custom])
    eff_custom = get_effective_theme(s_custom)
    assert eff_custom["id"] == "custom_neon"
    assert eff_custom["name"] == "Neon Cyber"
    assert eff_custom["accent_color"] == "#FF007F"
    assert eff_custom["opacity"] == 0.75
    assert eff_custom["blur_radius"] == 36
    assert eff_custom["corner_radius"] == 20
    assert eff_custom["animation_speed"] == "snappy"


def test_custom_themes_persistence(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg_file = tmp_path / "spotlight.json"
    monkeypatch.setenv("DEVTOOLKIT_SPOTLIGHT_CONFIG", str(cfg_file))

    custom_theme = {
        "id": "custom_123",
        "name": "Midnight Blue",
        "accent_color": "#0055FF",
        "opacity": 0.89,
        "blur_radius": 22,
        "corner_radius": 15,
        "animation_speed": "fast",
    }

    updated = update_spotlight_settings(
        custom_themes=[custom_theme],
        theme_preset="custom_123",
    )
    assert updated.theme_preset == "custom_123"
    assert len(updated.custom_themes) == 1
    assert updated.custom_themes[0]["name"] == "Midnight Blue"

    loaded = load_spotlight_settings()
    assert loaded.theme_preset == "custom_123"
    assert len(loaded.custom_themes) == 1
    assert loaded.custom_themes[0]["accent_color"] == "#0055FF"


def test_spotlight_position_presets_catalog():
    from clients.spotlight.settings import POSITION_PRESETS

    expected_keys = ["center", "left_center", "right_center", "center_top", "left_top", "right_top"]
    for k in expected_keys:
        assert k in POSITION_PRESETS
        preset = POSITION_PRESETS[k]
        assert "id" in preset
        assert "name" in preset
        assert "y_ratio" in preset
        assert "x_ratio" in preset
        assert "label" in preset


def test_spotlight_position_preset_update(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg_file = tmp_path / "spotlight.json"
    monkeypatch.setenv("DEVTOOLKIT_SPOTLIGHT_CONFIG", str(cfg_file))

    settings = load_spotlight_settings()
    assert settings.position_preset == "center"

    updated = update_spotlight_settings(position_preset="left_center")
    assert updated.position_preset == "left_center"

    loaded = load_spotlight_settings()
    assert loaded.position_preset == "left_center"


def test_calculate_window_position_presets(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    from clients.spotlight.window import SpotlightWindowManager
    cfg_file = tmp_path / "spotlight.json"
    monkeypatch.setenv("DEVTOOLKIT_SPOTLIGHT_CONFIG", str(cfg_file))

    wm = SpotlightWindowManager(client=None)
    monkeypatch.setattr(wm, "get_target_monitor_rect", lambda: (0, 0, 1920, 1080))
    monkeypatch.setattr(wm, "get_dpi_scale", lambda: 1.0)

    # 1. Center (X: Centered, Y: 22%)
    update_spotlight_settings(position_preset="center")
    x, y = wm.calculate_window_position()
    assert x == (1920 - 840) // 2
    assert y == int(1080 * 0.22)

    # 2. Left Center (X: 5%, Y: 22%)
    update_spotlight_settings(position_preset="left_center")
    x, y = wm.calculate_window_position()
    assert x == int(1920 * 0.05)
    assert y == int(1080 * 0.22)

    # 3. Right Center (X: 95%, Y: 22%)
    update_spotlight_settings(position_preset="right_center")
    x, y = wm.calculate_window_position()
    assert x == 1920 - 840 - int(1920 * 0.05)
    assert y == int(1080 * 0.22)

    # 4. Center Top (X: Centered, Y: 5%)
    update_spotlight_settings(position_preset="center_top")
    x, y = wm.calculate_window_position()
    assert x == (1920 - 840) // 2
    assert y == int(1080 * 0.05)

    # 5. Left Top (X: 5%, Y: 5%)
    update_spotlight_settings(position_preset="left_top")
    x, y = wm.calculate_window_position()
    assert x == int(1920 * 0.05)
    assert y == int(1080 * 0.05)

    # 6. Right Top (X: 95%, Y: 5%)
    update_spotlight_settings(position_preset="right_top")
    x, y = wm.calculate_window_position()
    assert x == 1920 - 840 - int(1920 * 0.05)
    assert y == int(1080 * 0.05)


def test_spotlight_load_creates_default_file_when_missing(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cfg_file = tmp_path / "spotlight.json"
    monkeypatch.setenv("DEVTOOLKIT_SPOTLIGHT_CONFIG", str(cfg_file))
    assert not cfg_file.exists()

    settings = load_spotlight_settings()
    assert cfg_file.is_file()
    data = json.loads(cfg_file.read_text(encoding="utf-8"))
    assert data["position_preset"] == "center"
    assert data["hotkey"] == "alt+space"


def test_get_spotlight_config_path_modes(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import sys
    from clients.spotlight.settings import get_spotlight_config_path

    monkeypatch.delenv("DEVTOOLKIT_SPOTLIGHT_CONFIG", raising=False)

    # 1. Dev mode: returns Path.cwd() / "spotlight.json"
    monkeypatch.delattr(sys, "frozen", raising=False)
    dev_path = get_spotlight_config_path()
    assert dev_path == Path.cwd() / "spotlight.json"

    # 2. Frozen .exe mode: strictly returns Path(sys.executable).parent / "spotlight.json"
    fake_exe = tmp_path / "bin" / "DevToolkitSpotlight.exe"
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(fake_exe))
    frozen_path = get_spotlight_config_path()
    assert frozen_path == fake_exe.parent / "spotlight.json"



