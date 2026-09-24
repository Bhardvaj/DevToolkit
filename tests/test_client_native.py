"""Tests for Python Native UI Theme, Window Shell, and CLI Launchers."""

import tkinter as tk
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from devtoolkit.cli.main import app as cli_app
from devtoolkit.client.api import DevToolkitClient
from devtoolkit.client.app import DevToolkitApp, WINDOW_TITLE, launch_native_ui
from devtoolkit.client.state import ClientState
from devtoolkit.client.theme import Colors, Fonts, apply_theme

runner = CliRunner()


def test_theme_colors_and_fonts():
    """Verify theme design tokens."""
    assert Colors.BG_MAIN.startswith("#")
    assert Colors.BG_SIDEBAR.startswith("#")
    assert Colors.ACCENT.startswith("#")
    assert Colors.SUCCESS == "#10B981"
    assert Colors.ERROR == "#EF4444"

    assert Fonts.TITLE[0] == "Segoe UI"
    assert Fonts.TITLE[1] == 16


def test_apply_theme_headless(tk_root):
    """Verify apply_theme runs cleanly on Tk root."""
    style = apply_theme(tk_root)
    assert style is not None
    assert tk_root.cget("bg") == Colors.BG_MAIN


def test_devtoolkit_app_shell_views(tk_root):
    """Verify DevToolkitApp builds layout and navigates across views."""
    client = MagicMock(spec=DevToolkitClient)
    client.port = 4321
    client.host = "127.0.0.1"
    client.base_url = "http://127.0.0.1:4321"
    client.get_ports.return_value = []
    client.get_config.return_value = {}
    client.get_tools.return_value = []
    client.get_system.return_value = {}
    state = ClientState()

    app = DevToolkitApp(root=tk_root, client=client, state=state)
    assert tk_root.title() == WINDOW_TITLE
    assert app.sidebar is not None
    assert len(app._nav_buttons) == 5

    # Navigate views
    for view_name in ["ports", "projects", "search", "settings", "environment"]:
        app._switch_view(view_name)
        assert app._active_view_frame is not None

    # Verify close action 'minimize'
    state.set_config({"close_action": "minimize"})
    with patch.object(client, "send_notification") as mock_notif:
        app._on_window_closing()
        mock_notif.assert_called_once()


def test_launch_native_ui_mocked():
    """Verify launch_native_ui auto-starts daemon if stopped and launches app."""
    with patch("devtoolkit.daemon.manager.is_daemon_alive", return_value=False) as mock_alive:
        with patch("devtoolkit.daemon.manager.start_daemon") as mock_start:
            with patch("tkinter.Tk") as mock_tk_cls:
                mock_root = MagicMock()
                mock_tk_cls.return_value = mock_root
                with patch("devtoolkit.client.app.DevToolkitApp") as mock_app_cls:
                    launch_native_ui(port=4321, host="127.0.0.1")
                    mock_alive.assert_called_once_with(host="127.0.0.1", port=4321)
                    mock_start.assert_called_once_with(port=4321, host="127.0.0.1")
                    mock_root.mainloop.assert_called_once()


def test_cli_native_command():
    """Test 'devtoolkit native --help' CLI command output."""
    res = runner.invoke(cli_app, ["native", "--help"])
    assert res.exit_code == 0
    import re

    clean_stdout = re.sub(r"\x1b\[[0-9;]*[a-zA-Z]", "", res.stdout)
    assert "Launch the Python Native desktop workstation inspector UI." in clean_stdout
    assert "--port" in clean_stdout
    assert "--host" in clean_stdout


def test_cli_native_flag():
    """Test 'devtoolkit --native' invokes launch_native_ui."""
    with patch("devtoolkit.client.app.launch_native_ui") as mock_launch:
        res = runner.invoke(cli_app, ["--native", "--port", "5000"])
        assert res.exit_code == 0
        mock_launch.assert_called_once_with(port=5000)
