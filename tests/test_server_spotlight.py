"""Tests for DevSpotlight server routes and embedded UI integration."""

from pathlib import Path
from devtoolkit.server.routes.spotlight import (
    get_spotlight_status,
    get_spotlight_settings,
    post_spotlight_settings,
    post_spotlight_theme,
    delete_spotlight_theme,
    SpotlightSettingsUpdateRequest,
    CustomThemeCreateRequest,
    get_running_spotlight_pids,
    get_spotlight_binary_path,
)
from devtoolkit.server.ui import get_dashboard_html


def test_spotlight_status_route():
    status = get_spotlight_status()
    assert isinstance(status, dict)
    assert "running" in status
    assert "pids" in status
    assert "executable_exists" in status
    assert "settings" in status
    assert "system_theme" in status
    assert "builtin_themes" in status
    assert "effective_theme" in status
    assert status["version"] == "v0.6.0"


def test_spotlight_settings_crud():
    # 1. Get Settings
    settings = get_spotlight_settings()
    assert isinstance(settings, dict)
    assert "hotkey" in settings
    assert "fallback_hotkey" in settings
    assert "monitor_mode" in settings
    assert "theme_preset" in settings
    assert "dismiss_on_blur" in settings
    assert "show_details_panel" in settings
    assert "restore_window_on_esc" in settings
    assert "corner_radius" in settings
    assert "enabled_scopes" in settings

    # 2. Update Settings
    req = SpotlightSettingsUpdateRequest(
        hotkey="alt+space",
        fallback_hotkey="alt+shift+space",
        monitor_mode="cursor",
        theme_preset="obsidian",
        opacity=0.95,
        blur_radius=25,
        corner_radius=16,
        dismiss_on_blur=True,
        show_details_panel=False,
        restore_window_on_esc=True,
        enabled_scopes=["app", "port", "calc"],
    )
    updated = post_spotlight_settings(req)
    assert updated["hotkey"] == "alt+space"
    assert updated["fallback_hotkey"] == "alt+shift+space"
    assert updated["monitor_mode"] == "cursor"
    assert updated["theme_preset"] == "obsidian"
    assert updated["opacity"] == 0.95
    assert updated["blur_radius"] == 25
    assert updated["corner_radius"] == 16
    assert updated["show_details_panel"] is False
    assert updated["restore_window_on_esc"] is True
    assert updated["enabled_scopes"] == ["app", "port", "calc"]


def test_spotlight_theme_endpoints():
    # 1. Create a custom theme
    req = CustomThemeCreateRequest(
        name="Cyber Matrix",
        accent_color="#00FF66",
        opacity=0.88,
        blur_radius=30,
        corner_radius=18,
        animation_speed="snappy",
    )
    res = post_spotlight_theme(req)
    assert res["status"] == "ok"
    assert "theme" in res
    theme_id = res["theme"]["id"]
    assert res["theme"]["name"] == "Cyber Matrix"
    assert res["theme"]["accent_color"] == "#00FF66"
    assert res["settings"]["theme_preset"] == theme_id

    # 2. Check settings reflect new theme
    settings = get_spotlight_settings()
    custom_themes = settings.get("custom_themes", [])
    matching = [t for t in custom_themes if t.get("id") == theme_id]
    assert len(matching) == 1
    assert matching[0]["name"] == "Cyber Matrix"

    # 3. Delete the custom theme
    del_res = delete_spotlight_theme(theme_id)
    assert del_res["status"] == "ok"
    assert del_res["deleted_id"] == theme_id

    # 4. Verify deleted
    settings_after = get_spotlight_settings()
    matching_after = [t for t in settings_after.get("custom_themes", []) if t.get("id") == theme_id]
    assert len(matching_after) == 0


def test_spotlight_binary_detection():
    bin_path = get_spotlight_binary_path()
    assert bin_path is not None
    assert bin_path.exists()


def test_embedded_ui_contains_spotlight_elements():
    html = get_dashboard_html()
    assert "nav-btn-spotlight" in html
    assert "view-spotlight" in html
    assert "sp-input-hotkey" in html
    assert "sp-select-monitor" in html
    assert "sp-select-theme" in html
    assert "sp-slider-opacity" in html
    assert "sp-slider-blur" in html
    assert "sp-toggle-dismiss" in html
    assert "sp-toggle-details" in html
    assert "sp-toggle-restore" in html
    assert "sp-btn-edit-primary" in html
    assert "sp-btn-edit-fallback" in html
    assert "hotkey-modal" in html
    assert "openHotkeyModal" in html
    assert "fetchSpotlightStatus" in html
    assert "launchSpotlight" in html
    assert "saveSpotlightSettingsForm" in html
    assert "mod-toggle-win" in html
    assert "mod-toggle-alt" in html
    assert "mod-toggle-ctrl" in html
    assert "mod-toggle-shift" in html
    assert "toggleModalModifier" in html
    assert "applyPresetShortcut" in html
    assert "normalizeKeyCode" in html
    # Comprehensive Theming UI
    assert "preset-system" in html
    assert "theme-presets-grid" in html
    assert "theme-preset-modal" in html
    assert "sp-system-theme-banner" in html
    assert "sp-theming-controls" in html
    assert "openThemePresetModal" in html
    assert "selectThemePreset" in html


def test_parse_hotkey_string_combinations():
    from clients.spotlight.hotkey import (
        parse_hotkey_string,
        MOD_ALT,
        MOD_CONTROL,
        MOD_SHIFT,
        MOD_WIN,
        MOD_NOREPEAT,
        VK_SPACE,
    )

    # 1. Standard Alt+Space
    mods, vk = parse_hotkey_string("alt+space")
    assert mods == (MOD_ALT | MOD_NOREPEAT)
    assert vk == VK_SPACE

    # 2. Ctrl+Shift+K
    mods, vk = parse_hotkey_string("ctrl+shift+k")
    assert mods == (MOD_CONTROL | MOD_SHIFT | MOD_NOREPEAT)
    assert vk == ord("K")

    # 3. Win+Alt+Space
    mods, vk = parse_hotkey_string("win+alt+space")
    assert mods == (MOD_WIN | MOD_ALT | MOD_NOREPEAT)
    assert vk == VK_SPACE

    # 4. Function key F12 (standalone)
    mods, vk = parse_hotkey_string("f12")
    assert mods == MOD_NOREPEAT
    assert vk == 0x6F + 12  # VK_F12 = 0x7B

    # 5. Alt+Tab
    mods, vk = parse_hotkey_string("alt+tab")
    assert mods == (MOD_ALT | MOD_NOREPEAT)
    assert vk == 0x09  # VK_TAB

    # 6. Ctrl+Enter
    mods, vk = parse_hotkey_string("ctrl+enter")
    assert mods == (MOD_CONTROL | MOD_NOREPEAT)
    assert vk == 0x0D  # VK_RETURN

    # 7. Alt+` (grave/tilde)
    mods, vk = parse_hotkey_string("alt+`")
    assert mods == (MOD_ALT | MOD_NOREPEAT)
    assert vk == 0xC0  # VK_OEM_3


def test_global_hotkey_listener_initialization():
    from clients.spotlight.hotkey import GlobalHotkeyListener

    called = []
    listener = GlobalHotkeyListener(
        hotkey_str="ctrl+shift+k",
        fallback_hotkey_str="alt+shift+space",
        on_hotkey=lambda: called.append(True),
    )
    assert listener.hotkey_str == "ctrl+shift+k"
    assert listener.fallback_hotkey_str == "alt+shift+space"
    assert listener.on_hotkey is not None


