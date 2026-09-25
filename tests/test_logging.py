"""Tests for DevToolkit centralized, co-located logging system."""

import logging
from pathlib import Path
import pytest

from devtoolkit.core.logging import (
    get_client_log_path,
    get_daemon_log_path,
    get_log_dir,
    setup_client_logging,
    setup_daemon_logging,
)


def test_log_paths_beside_config(tmp_path, monkeypatch):
    """Verify log paths are co-located with devtoolkit.config.yaml."""
    cfg_file = tmp_path / "devtoolkit.config.yaml"
    monkeypatch.setenv("DEVTOOLKIT_CONFIG", str(cfg_file))

    log_dir = get_log_dir()
    assert log_dir == tmp_path

    daemon_log = get_daemon_log_path()
    assert daemon_log == tmp_path / "daemon.log"

    client_log = get_client_log_path()
    assert client_log == tmp_path / "client.log"


def test_setup_daemon_logging(tmp_path, monkeypatch):
    """Verify daemon logging configures rotating handler and writes to daemon.log."""
    cfg_file = tmp_path / "devtoolkit.config.yaml"
    monkeypatch.setenv("DEVTOOLKIT_CONFIG", str(cfg_file))

    log_file = setup_daemon_logging()
    assert log_file.exists()

    logger = logging.getLogger("devtoolkit.daemon.test")
    logger.info("Test daemon message 12345")

    content = log_file.read_text(encoding="utf-8")
    assert "Test daemon message 12345" in content


def test_setup_client_logging(tmp_path, monkeypatch):
    """Verify client logging configures rotating handler and writes to client.log."""
    cfg_file = tmp_path / "devtoolkit.config.yaml"
    monkeypatch.setenv("DEVTOOLKIT_CONFIG", str(cfg_file))

    log_file = setup_client_logging()
    assert log_file.exists()

    logger = logging.getLogger("devtoolkit.client.test")
    logger.info("Test client message 67890")

    content = log_file.read_text(encoding="utf-8")
    assert "Test client message 67890" in content

