"""User configuration management for DevToolkit."""

from pathlib import Path
from typing import Dict, List, Optional
import yaml
from pydantic import BaseModel, Field

DEFAULT_CONFIG_PATH = Path.home() / ".devtoolkit" / "config.yaml"


class DevToolkitConfig(BaseModel):
    """User preferences, monitored search directories, and custom settings."""

    search_paths: List[str] = Field(default_factory=list)
    enabled_categories: Optional[List[str]] = None
    custom_env: Dict[str, str] = Field(default_factory=dict)


def get_config_path() -> Path:
    """Return path to active config file (supports local .devtoolkit.yaml or global)."""
    local_cfg = Path(".devtoolkit.yaml")
    if local_cfg.exists():
        return local_cfg
    return DEFAULT_CONFIG_PATH


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
