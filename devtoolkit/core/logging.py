"""Centralized, co-located logging system for DevToolkit Daemon and Clients.

Logs are written beside devtoolkit.config.yaml (or executable directory when frozen):
- daemon.log: Captures background server, uvicorn, search engine, indexing, and tray events.
- client.log: Captures embedded desktop UI, PyWebView lifecycle, and client actions.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
import os
from pathlib import Path
import sys
from typing import Optional

from devtoolkit.core.config import get_config_path

LOG_FORMAT = "%(asctime)s [%(levelname)s] [%(name)s]: %(message)s"
MAX_LOG_BYTES = 5 * 1024 * 1024  # 5 MB
BACKUP_COUNT = 3


def get_log_dir() -> Path:
    """Return directory where log files should reside (beside devtoolkit.config.yaml)."""
    cfg_path = get_config_path()
    log_dir = cfg_path.parent
    log_dir.mkdir(parents=True, exist_ok=True)
    return log_dir


def get_daemon_log_path() -> Path:
    """Return path to daemon.log."""
    return get_log_dir() / "daemon.log"


def get_client_log_path() -> Path:
    """Return path to client.log."""
    return get_log_dir() / "client.log"


def setup_daemon_logging(level: int = logging.INFO) -> Path:
    """Configure logging for the background daemon service and uvicorn."""
    log_file = get_daemon_log_path()
    handler = RotatingFileHandler(
        log_file,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT))

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Avoid duplicate handlers if called multiple times
    for h in list(root_logger.handlers):
        if isinstance(h, RotatingFileHandler) and Path(h.baseFilename) == log_file.resolve():
            root_logger.removeHandler(h)
    root_logger.addHandler(handler)

    # Also route uvicorn loggers to daemon log
    for uvi in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        u_logger = logging.getLogger(uvi)
        u_logger.setLevel(level)
        u_logger.addHandler(handler)

    logging.getLogger("devtoolkit.daemon").info(f"=== DevToolkit Daemon Logging Initialized -> {log_file} ===")
    return log_file


def setup_client_logging(level: int = logging.INFO) -> Path:
    """Configure logging for the embedded desktop or browser client."""
    log_file = get_client_log_path()
    handler = RotatingFileHandler(
        log_file,
        maxBytes=MAX_LOG_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(LOG_FORMAT))

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    for h in list(root_logger.handlers):
        if isinstance(h, RotatingFileHandler) and Path(h.baseFilename) == log_file.resolve():
            root_logger.removeHandler(h)
    root_logger.addHandler(handler)

    logging.getLogger("devtoolkit.client").info(f"=== DevToolkit Client Logging Initialized -> {log_file} ===")
    return log_file

