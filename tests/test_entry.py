"""Tests for DevToolkit entrypoint application dispatcher."""

import sys
from unittest.mock import patch
import pytest

from devtoolkit.entry import ensure_safe_stdio, main


def test_ensure_safe_stdio():
    """Verify safe stdio initialization replaces None streams."""
    with patch.object(sys, "stdout", None), patch.object(sys, "stderr", None):
        ensure_safe_stdio()
        assert sys.stdout is not None
        assert sys.stderr is not None


def test_entry_dispatch_daemon():
    """Verify --daemon flag routes to run_daemon_server."""
    with patch("sys.argv", ["DevToolkit", "--daemon", "--port", "5000", "--host", "0.0.0.0"]), \
         patch("devtoolkit.daemon.server.run_daemon_server") as mock_server:
        main()
        mock_server.assert_called_once_with(host="0.0.0.0", port=5000, with_tray=True)


def test_entry_dispatch_web():
    """Verify --web flag routes to launch_desktop_window with web_only=True."""
    with patch("sys.argv", ["DevToolkit", "--web", "--port", "4321"]), \
         patch("devtoolkit.client.desktop.launch_desktop_window") as mock_launch:
        main()
        mock_launch.assert_called_once_with(port=4321, web_only=True, dev=False)


def test_entry_dispatch_default_gui():
    """Verify default invocation without args launches native desktop window."""
    with patch("sys.argv", ["DevToolkit"]), \
         patch("devtoolkit.client.desktop.launch_desktop_window") as mock_launch:
        main()
        mock_launch.assert_called_once_with(port=4321, web_only=False, dev=False)


def test_entry_dispatch_subcommand_daemon_run():
    """Verify legacy `daemon run` syntax routes cleanly to run_daemon_server."""
    with patch("sys.argv", ["DevToolkit", "daemon", "run", "--port", "4321"]), \
         patch("devtoolkit.daemon.server.run_daemon_server") as mock_server:
        main()
        mock_server.assert_called_once_with(host="127.0.0.1", port=4321, with_tray=True)

