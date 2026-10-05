"""Portable configuration management for DevToolkit.

Uses devtoolkit.json co-located beside the executable or in dev root.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
import sys
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

CONFIG_FILENAME = "devtoolkit.json"


class DevToolkitConfig(BaseModel):
    """User preferences, monitored search directories, and custom settings."""

    search_paths: List[str] = Field(default_factory=list)
    enabled_categories: Optional[List[str]] = None
    custom_env: Dict[str, str] = Field(default_factory=dict)
    realtime_search: bool = True
    close_action: str = Field(default="ask")  # "ask" | "minimize" | "exit"
    config_path: Optional[str] = None


def get_app_dir() -> Path:
    """Return the application directory: executable directory if frozen, else current working directory."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def get_config_path() -> Path:
    """Return path to portable devtoolkit.json located beside the executable (or cwd in dev).

    Rule:
    - In compiled executable mode: ALWAYS use the exact same directory as the .exe. No other location ever.
    - In development mode: root devtoolkit.json is used.
    """
    env_override = os.environ.get("DEVTOOLKIT_CONFIG")
    if env_override:
        p = Path(env_override).resolve()
        p.parent.mkdir(parents=True, exist_ok=True)
        return p

    if getattr(sys, "frozen", False):
        exe_dir = Path(sys.executable).resolve().parent
        exe_dir.mkdir(parents=True, exist_ok=True)
        return exe_dir / CONFIG_FILENAME

    dev_dir = Path.cwd().resolve()
    dev_dir.mkdir(parents=True, exist_ok=True)
    return dev_dir / CONFIG_FILENAME


def load_config() -> DevToolkitConfig:
    """Load configuration from disk, or create one with default values if it does not exist."""
    cfg_file = get_config_path()
    if not cfg_file.is_file():
        cfg = DevToolkitConfig()
        try:
            save_config(cfg)
        except Exception as e:
            logger.debug(f"Failed to create default {CONFIG_FILENAME}: {e}")
        cfg.config_path = str(cfg_file)
        return cfg

    try:
        data = json.loads(cfg_file.read_text(encoding="utf-8")) or {}
        cfg = DevToolkitConfig(**data)
        cfg.config_path = str(cfg_file)
        return cfg
    except Exception as e:
        logger.debug(f"Failed to parse {cfg_file}: {e}")
        cfg = DevToolkitConfig()
        cfg.config_path = str(cfg_file)
        return cfg


def save_config(config: DevToolkitConfig) -> Path:
    """Save configuration to devtoolkit.json."""
    cfg_file = get_config_path()
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(mode="json", exclude={"config_path"})
    cfg_file.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return cfg_file


def open_config_file() -> bool:
    """Open devtoolkit.json in the system default text editor or notepad."""
    cfg = get_config_path()
    if not cfg.exists():
        load_config()

    if sys.platform == "win32":
        try:
            import ctypes
            shell32 = ctypes.windll.shell32
            res = shell32.ShellExecuteW(None, "open", str(cfg), None, None, 1)
            if int(res) <= 32:
                import subprocess
                subprocess.Popen(["notepad.exe", str(cfg)])
            return True
        except Exception:
            return False
    else:
        try:
            import subprocess
            subprocess.Popen(["xdg-open", str(cfg)])
            return True
        except Exception:
            return False


def add_search_path(path_str: str) -> bool:
    """Add a custom search path to user configuration if not already present."""
    p = Path(path_str).expanduser().resolve()
    if not p.exists() or not p.is_dir():
        return False

    config = load_config()
    str_path = str(p)
    if str_path not in config.search_paths:
        config.search_paths.append(str_path)
        save_config(config)
        return True
    return False


def remove_search_path_by_index(index: int) -> bool:
    """Remove a custom search path by its numeric index in search_paths."""
    config = load_config()
    if 0 <= index < len(config.search_paths):
        config.search_paths.pop(index)
        save_config(config)
        return True
    return False


def remove_search_path(path_str: str) -> bool:
    """Remove a custom search path from user configuration."""
    config = load_config()
    target_clean = path_str.strip()
    target_norm = os.path.normcase(os.path.normpath(target_clean))
    try:
        target_resolved = os.path.normcase(str(Path(target_clean).expanduser().resolve()))
    except Exception:
        target_resolved = target_norm

    for sp in list(config.search_paths):
        sp_clean = sp.strip()
        sp_norm = os.path.normcase(os.path.normpath(sp_clean))
        try:
            sp_resolved = os.path.normcase(str(Path(sp_clean).expanduser().resolve()))
        except Exception:
            sp_resolved = sp_norm

        if (
            sp == path_str
            or sp_clean == target_clean
            or sp_norm == target_norm
            or sp_resolved == target_resolved
        ):
            config.search_paths.remove(sp)
            save_config(config)
            return True

    # Fallback: if a numeric index was provided as string
    if target_clean.isdigit():
        idx = int(target_clean)
        return remove_search_path_by_index(idx)

    return False


def set_realtime_search(enabled: bool) -> bool:
    """Set realtime_search enabled flag in persistent configuration."""
    config = load_config()
    config.realtime_search = bool(enabled)
    save_config(config)
    return True


def set_close_action(action: str) -> bool:
    """Set close_action preference ('ask', 'minimize', 'exit') in persistent configuration."""
    action_clean = action.strip().lower()
    if action_clean not in ("ask", "minimize", "exit"):
        return False
    config = load_config()
    config.close_action = action_clean
    save_config(config)
    return True

