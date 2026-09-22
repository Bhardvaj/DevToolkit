"""Portable configuration management for DevToolkit."""

import os
from pathlib import Path
import sys
from typing import Dict, List, Optional
import yaml
from pydantic import BaseModel, Field

CONFIG_FILENAME = "devtoolkit.config.yaml"


class DevToolkitConfig(BaseModel):
    """User preferences, monitored search directories, and custom settings."""

    search_paths: List[str] = Field(default_factory=list)
    enabled_categories: Optional[List[str]] = None
    custom_env: Dict[str, str] = Field(default_factory=dict)
    realtime_search: bool = True


def get_app_dir() -> Path:
    """Return the application directory: executable directory if frozen, else current working directory."""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path.cwd().resolve()


def get_config_path() -> Path:
    """Return path to portable config file located beside the executable (or cwd in dev)."""
    env_override = os.environ.get("DEVTOOLKIT_CONFIG")
    if env_override:
        return Path(env_override).resolve()

    app_dir = get_app_dir()
    primary_cfg = app_dir / CONFIG_FILENAME
    alt_cfg = app_dir / ".devtoolkit.yaml"
    if not primary_cfg.exists() and alt_cfg.exists():
        return alt_cfg
    return primary_cfg


def load_config() -> DevToolkitConfig:
    """Load configuration from disk, or return defaults if not found."""
    cfg_file = get_config_path()
    if not cfg_file.exists():
        return DevToolkitConfig()

    try:
        data = yaml.safe_load(cfg_file.read_text(encoding="utf-8")) or {}
        return DevToolkitConfig(**data)
    except Exception:
        return DevToolkitConfig()


def save_config(config: DevToolkitConfig) -> Path:
    """Save configuration to disk."""
    cfg_file = get_config_path()
    cfg_file.parent.mkdir(parents=True, exist_ok=True)
    data = config.model_dump(mode="json")
    cfg_file.write_text(yaml.dump(data, sort_keys=False, default_flow_style=False), encoding="utf-8")
    return cfg_file


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

