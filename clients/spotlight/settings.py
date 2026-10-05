"""DevToolkit Spotlight configuration and settings coordinator."""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


def get_spotlight_config_path() -> Path:
    """Return the absolute path to spotlight.json co-located with executable or in dev root.
    
    Rule:
    - In compiled executable mode: ALWAYS use the exact same directory as the .exe. No other location ever.
    - In development mode: root json file is used.
    """
    env_override = os.environ.get("DEVTOOLKIT_SPOTLIGHT_CONFIG")
    if env_override:
        p = Path(env_override).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    # When running as compiled executable (.exe), ALWAYS use the exact same directory as the .exe
    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).parent
        exe_dir.mkdir(parents=True, exist_ok=True)
        return exe_dir / "spotlight.json"

    # In development mode, use root directory spotlight.json
    dev_dir = Path.cwd()
    dev_dir.mkdir(parents=True, exist_ok=True)
    return dev_dir / "spotlight.json"


# Built-in Theme Presets
BUILTIN_THEMES: Dict[str, Dict[str, Any]] = {
    "system": {
        "id": "system",
        "name": "Same as system",
        "accent_color": "#0078d4",
        "opacity": 0.65,
        "blur_radius": 36,
        "corner_radius": 8,
        "animation_speed": "normal",
        "is_builtin": True,
        "is_system": True,
    },
    "obsidian": {
        "id": "obsidian",
        "name": "Obsidian Dark",
        "accent_color": "#38bdf8",
        "opacity": 0.92,
        "blur_radius": 20,
        "corner_radius": 8,
        "animation_speed": "normal",
        "is_builtin": True,
    },
    "emerald": {
        "id": "emerald",
        "name": "Cyber Emerald",
        "accent_color": "#10b981",
        "opacity": 0.84,
        "blur_radius": 28,
        "corner_radius": 8,
        "animation_speed": "normal",
        "is_builtin": True,
    },
    "indigo": {
        "id": "indigo",
        "name": "Titanium Slate",
        "accent_color": "#8b5cf6",
        "opacity": 0.88,
        "blur_radius": 24,
        "corner_radius": 8,
        "animation_speed": "fast",
        "is_builtin": True,
    },
    "amber": {
        "id": "amber",
        "name": "macOS Vibrant",
        "accent_color": "#f59e0b",
        "opacity": 0.95,
        "blur_radius": 32,
        "corner_radius": 8,
        "animation_speed": "fast",
        "is_builtin": True,
    },
}


# Position Presets (Optical placement anchors matching Flow Launcher)
POSITION_PRESETS: Dict[str, Dict[str, Any]] = {
    "center": {
        "id": "center",
        "name": "Center",
        "x_mode": "center",
        "y_ratio": 0.22,
        "x_ratio": 0.50,
        "label": "X: 50% • Y: 22%",
    },
    "left_center": {
        "id": "left_center",
        "name": "Left Center",
        "x_mode": "left",
        "y_ratio": 0.22,
        "x_ratio": 0.05,
        "label": "X: 5% • Y: 22%",
    },
    "right_center": {
        "id": "right_center",
        "name": "Right Center",
        "x_mode": "right",
        "y_ratio": 0.22,
        "x_ratio": 0.95,
        "label": "X: 95% • Y: 22%",
    },
    "center_top": {
        "id": "center_top",
        "name": "Center Top",
        "x_mode": "center",
        "y_ratio": 0.05,
        "x_ratio": 0.50,
        "label": "X: 50% • Y: 5%",
    },
    "left_top": {
        "id": "left_top",
        "name": "Left Top",
        "x_mode": "left",
        "y_ratio": 0.05,
        "x_ratio": 0.05,
        "label": "X: 5% • Y: 5%",
    },
    "right_top": {
        "id": "right_top",
        "name": "Right Top",
        "x_mode": "right",
        "y_ratio": 0.05,
        "x_ratio": 0.95,
        "label": "X: 95% • Y: 5%",
    },
}


def get_windows_system_theme() -> Dict[str, Any]:
    """Inspect Windows registry to detect active system accent color and dark/light mode."""
    dark_mode = True
    accent_color = "#0078d4"

    if sys.platform == "win32":
        try:
            import winreg

            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER,
                    r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize",
                ) as key:
                    apps_light, _ = winreg.QueryValueEx(key, "AppsUseLightTheme")
                    dark_mode = apps_light == 0
            except Exception:
                pass

            try:
                with winreg.OpenKey(
                    winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM"
                ) as key:
                    color_val, _ = winreg.QueryValueEx(key, "AccentColor")
                    r = color_val & 0xFF
                    g = (color_val >> 8) & 0xFF
                    b = (color_val >> 16) & 0xFF
                    accent_color = f"#{r:02x}{g:02x}{b:02x}"
            except Exception:
                try:
                    with winreg.OpenKey(
                        winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\DWM"
                    ) as key:
                        color_val, _ = winreg.QueryValueEx(key, "ColorizationColor")
                        r = (color_val >> 16) & 0xFF
                        g = (color_val >> 8) & 0xFF
                        b = color_val & 0xFF
                        accent_color = f"#{r:02x}{g:02x}{b:02x}"
                except Exception:
                    pass
        except Exception as e:
            logger.debug(f"Error reading Windows system theme: {e}")

    return {
        "dark_mode": dark_mode,
        "accent_color": accent_color,
    }


@dataclass
class SpotlightSettings:
    """Configurable user preferences for DevToolkit Spotlight."""

    hotkey: str = "alt+space"
    fallback_hotkey: str = "alt+shift+space"
    monitor_mode: str = "cursor"  # "cursor", "focused", "fixed", "monitor_0", etc.
    fixed_monitor_index: int = 0
    position_preset: str = "center"  # "center", "left_center", "right_center", "center_top", "left_top", "right_top"
    accent_color: str = "#38bdf8"  # Obsidian Cyan
    opacity: float = 0.92          # 0.50 to 1.00
    blur_radius: int = 20          # 0 to 40 px
    corner_radius: int = 8          # Windows 11 native OS window radius (8px)
    dismiss_on_blur: bool = True
    show_details_panel: bool = True
    restore_window_on_esc: bool = True
    theme_preset: str = "obsidian"  # system, obsidian, emerald, indigo, amber, or custom id
    animation_speed: str = "normal"  # "fast", "normal", "relaxed", "off"
    enabled_scopes: List[str] = field(default_factory=lambda: ["app", "file", "port", "calc", "tool", "window", "project", "action"])
    custom_themes: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> SpotlightSettings:
        valid_keys = {f for f in cls.__dataclass_fields__}
        filtered = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered)


_cached_settings: SpotlightSettings | None = None


def load_spotlight_settings() -> SpotlightSettings:
    """Load settings from spotlight.json or create one with default values if it does not exist."""
    global _cached_settings
    path = get_spotlight_config_path()
    if not path.is_file():
        _cached_settings = SpotlightSettings()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(_cached_settings.to_dict(), indent=2), encoding="utf-8")
        except Exception as e:
            logger.debug(f"Failed creating default spotlight.json at {path}: {e}")
        return _cached_settings

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        _cached_settings = SpotlightSettings.from_dict(raw)
        return _cached_settings
    except Exception as e:
        logger.debug(f"Failed parsing {path}: {e}")
        _cached_settings = SpotlightSettings()
        return _cached_settings


def save_spotlight_settings(settings: SpotlightSettings) -> Path:
    """Persist settings strictly to spotlight.json at get_spotlight_config_path()."""
    global _cached_settings
    path = get_spotlight_config_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(settings.to_dict(), indent=2)
    path.write_text(content, encoding="utf-8")
    _cached_settings = settings
    return path


def update_spotlight_settings(**kwargs: Any) -> SpotlightSettings:
    """Update specific settings fields and save to disk."""
    current = load_spotlight_settings()
    curr_dict = current.to_dict()
    valid_fields = set(SpotlightSettings.__dataclass_fields__)
    for k, v in kwargs.items():
        if k in valid_fields:
            curr_dict[k] = v
    new_settings = SpotlightSettings.from_dict(curr_dict)
    save_spotlight_settings(new_settings)
    return new_settings


def get_effective_theme(settings: Optional[SpotlightSettings] = None) -> Dict[str, Any]:
    """Resolve the active theme configuration including system dynamic detection."""
    if settings is None:
        settings = load_spotlight_settings()

    preset_id = settings.theme_preset or "obsidian"

    if preset_id == "system":
        sys_theme = get_windows_system_theme()
        base = dict(BUILTIN_THEMES["system"])
        base["accent_color"] = sys_theme["accent_color"]
        base["dark_mode"] = sys_theme["dark_mode"]
        return base

    # Check custom themes
    for ct in settings.custom_themes:
        if ct.get("id") == preset_id:
            return ct

    # Check built-in themes
    if preset_id in BUILTIN_THEMES:
        return BUILTIN_THEMES[preset_id]

    return BUILTIN_THEMES["obsidian"]

